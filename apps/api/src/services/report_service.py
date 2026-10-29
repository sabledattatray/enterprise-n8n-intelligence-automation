import hashlib
import logging
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from apps.api.src.config import settings
from apps.api.src.models.entities import AISummary, AnomalyEvent, KPISnapshot, ReportDispatch
from apps.api.src.schemas.ai import AIInsightGenerationRequest
from apps.api.src.schemas.kpi import KPIComputeRequest
from apps.api.src.schemas.reports import ReportDispatchRequest, ReportDispatchResponse
from apps.api.src.services.ai_service import AIService
from apps.api.src.services.kpi_service import KPIService

logger = logging.getLogger("eiap.report_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def dispatch_report(
        self,
        req: ReportDispatchRequest,
        correlation_id: str,
    ) -> ReportDispatchResponse:
        """
        Generates and dispatches the executive HTML email report to Mailpit.
        Enforces idempotency to prevent duplicate dispatches.
        """
        # 1. Retrieve Target Snapshot
        if req.snapshot_id:
            snapshot = self.db.query(KPISnapshot).filter(KPISnapshot.snapshot_id == req.snapshot_id).first()
        else:
            snapshot = self.db.query(KPISnapshot).order_by(KPISnapshot.computed_at.desc()).first()

        if not snapshot:
            raise KeyError("No KPI snapshot available for report generation.")

        # 2. Idempotency Check (report_id + recipient_hash) immediately
        report_id = f"rep_{str(snapshot.snapshot_id)[:8]}_{snapshot.period_end.strftime('%Y%m%d')}"
        recipient_clean = req.recipient_email.strip().lower()
        recipient_hash = hashlib.sha256(recipient_clean.encode()).hexdigest()[:16]

        existing = (
            self.db.query(ReportDispatch)
            .filter(
                ReportDispatch.report_id == report_id,
                ReportDispatch.recipient_hash == recipient_hash,
            )
            .first()
        )

        if existing and not req.force_resend:
            logger.info(
                f"Idempotent report dispatch requested: {report_id} for recipient {recipient_clean}; returning existing dispatch."
            )
            return ReportDispatchResponse(
                dispatch_id=existing.dispatch_id,
                report_id=existing.report_id,
                recipient=recipient_clean,
                recipient_hash=existing.recipient_hash,
                channel=existing.channel,
                subject=existing.subject or f"[EIAP Report] Commercial Performance ({snapshot.currency_code})",
                status=existing.status,
                idempotent_replay=True,
                attempts=existing.attempts,
                sent_at=existing.sent_at,
                smtp_target="Mailpit Local Catcher (Cached)",
            )

        # 3. Retrieve AI Summary (or generate if none exists)
        ai_summary = (
            self.db.query(AISummary)
            .filter(AISummary.snapshot_id == snapshot.snapshot_id)
            .order_by(AISummary.created_at.desc())
            .first()
        )
        if not ai_summary:
            ai_service = AIService(self.db)
            ai_resp = ai_service.generate_summary(AIInsightGenerationRequest(snapshot_id=snapshot.snapshot_id))
            summary_content = ai_resp.sections.model_dump()
        else:
            summary_content = ai_summary.content_json

        # 4. Retrieve Anomalies
        anomalies = (
            self.db.query(AnomalyEvent)
            .filter(AnomalyEvent.snapshot_id == snapshot.snapshot_id)
            .order_by(AnomalyEvent.created_at.desc())
            .all()
        )

        # 5. Retrieve Detailed Breakdowns (without re-materializing snapshot)
        kpi_service = KPIService(self.db)
        kpi_details = kpi_service.compute_kpis(
            KPIComputeRequest(
                period_start=snapshot.period_start,
                period_end=snapshot.period_end,
                currency_code=snapshot.currency_code,
                source_run_id=snapshot.source_run_id,
            ),
            materialize=False,
        )

        # 6. Render Responsive HTML Email Body
        subject = f"[EIAP Executive Briefing] Commercial Performance ({snapshot.currency_code}) - {snapshot.period_end.strftime('%b %Y')}"
        html_body = self._render_html_report(snapshot, summary_content, kpi_details, anomalies, report_id)

        # 7. Deliver to Mailpit via SMTP
        smtp_host = settings.SMTP_HOST if settings.RUNNING_IN_DOCKER else settings.LOCAL_SMTP_HOST
        smtp_port = settings.SMTP_PORT if settings.RUNNING_IN_DOCKER else settings.LOCAL_SMTP_PORT

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient_clean
        msg["X-Correlation-ID"] = correlation_id
        msg["X-EIAP-Report-ID"] = report_id
        msg.set_content(html_body, subtype="html")

        now = utc_now()
        dispatch_status = "SENT"
        attempts = (existing.attempts + 1) if existing else 1

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.send_message(msg)
            logger.info(f"Dispatched executive report {report_id} to {recipient_clean} via Mailpit ({smtp_host}:{smtp_port})")
        except Exception as exc:
            logger.error(f"Failed to dispatch email via SMTP ({smtp_host}:{smtp_port}): {exc}")
            dispatch_status = "FAILED"

        # 8. Record Dispatch in PostgreSQL report_dispatches table
        dispatch_id = existing.dispatch_id if existing else uuid.uuid4()
        if existing:
            existing.status = dispatch_status
            existing.attempts = attempts
            existing.sent_at = now if dispatch_status == "SENT" else existing.sent_at
            existing.subject = subject
            existing.metadata_json = {
                "correlation_id": correlation_id,
                "snapshot_id": str(snapshot.snapshot_id),
                "resend": True,
            }
            self.db.commit()
        else:
            dispatch_record = ReportDispatch(
                dispatch_id=dispatch_id,
                report_id=report_id,
                recipient_hash=recipient_hash,
                channel=req.channel,
                subject=subject,
                status=dispatch_status,
                attempts=1,
                metadata_json={
                    "correlation_id": correlation_id,
                    "snapshot_id": str(snapshot.snapshot_id),
                    "recipient": recipient_clean,
                },
                created_at=now,
                sent_at=now if dispatch_status == "SENT" else None,
            )
            self.db.add(dispatch_record)
            self.db.commit()

        return ReportDispatchResponse(
            dispatch_id=dispatch_id,
            report_id=report_id,
            recipient=recipient_clean,
            recipient_hash=recipient_hash,
            channel=req.channel,
            subject=subject,
            status=dispatch_status,
            idempotent_replay=False,
            attempts=attempts,
            sent_at=now if dispatch_status == "SENT" else None,
            smtp_target=f"Mailpit ({smtp_host}:{smtp_port})",
        )

    def _render_html_report(
        self,
        snapshot: KPISnapshot,
        summary: Dict[str, Any],
        details: Any,
        anomalies: List[AnomalyEvent],
        report_id: str,
    ) -> str:
        """
        Renders an enterprise-grade responsive HTML email template
        aligned with the Power BI theme palette (Dark Slate, Blue, Teal).
        """
        curr = snapshot.currency_code
        rev = float(snapshot.revenue)
        cost = float(snapshot.cost)
        profit = float(snapshot.profit)
        margin = float(snapshot.margin_pct)
        orders = snapshot.orders
        aov = round(rev / orders, 2) if orders > 0 else 0.0

        # Anomaly HTML rows
        if anomalies:
            anomaly_rows = "".join([
                f"""
                <tr>
                    <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; font-weight: 600; color: #DC2626;">{a.severity}</td>
                    <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; color: #0F172A;">{a.rule_id}</td>
                    <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; color: #475569;">{a.metric}</td>
                    <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: right; color: #0F172A;">${float(a.observed_value):,.2f}</td>
                    <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: right; color: #64748B;">${float(a.baseline_value):,.2f}</td>
                </tr>
                """
                for a in anomalies
            ])
            anomaly_section = f"""
            <div style="margin-top: 24px; background: #FEF2F2; border-left: 4px solid #DC2626; padding: 16px; border-radius: 4px;">
                <h3 style="margin: 0 0 10px 0; color: #991B1B; font-size: 15px;">Operational Anomaly Alerts ({len(anomalies)})</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; background: #FFFFFF; border: 1px solid #FEE2E2;">
                    <thead>
                        <tr style="background: #FEE2E2; text-align: left; color: #991B1B;">
                            <th style="padding: 8px 12px;">Severity</th>
                            <th style="padding: 8px 12px;">Rule</th>
                            <th style="padding: 8px 12px;">Metric</th>
                            <th style="padding: 8px 12px; text-align: right;">Observed</th>
                            <th style="padding: 8px 12px; text-align: right;">Baseline</th>
                        </tr>
                    </thead>
                    <tbody>
                        {anomaly_rows}
                    </tbody>
                </table>
            </div>
            """
        else:
            anomaly_section = """
            <div style="margin-top: 24px; background: #F0FDF4; border-left: 4px solid #059669; padding: 16px; border-radius: 4px;">
                <p style="margin: 0; color: #065F46; font-size: 14px; font-weight: 500;">
                    ✓ All operational metrics operating within standard baseline tolerances. Zero anomalies detected.
                </p>
            </div>
            """

        # Product breakdown rows
        top_cats = details.breakdowns.by_category[:5]
        cat_rows = "".join([
            f"""
            <tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #F1F5F9; color: #0F172A; font-weight: 500;">{c.category}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #F1F5F9; text-align: right; color: #0F172A;">${c.revenue:,.2f}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #F1F5F9; text-align: right; color: #0D9488;">{c.margin_pct:.1f}%</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #F1F5F9; text-align: right; color: #64748B;">{c.order_count:,}</td>
            </tr>
            """
            for c in top_cats
        ])

        overview_text = summary.get("business_overview", "Commercial overview generated by EIAP AI service.")
        priorities = summary.get("investigation_priorities", [])
        priority_bullets = "".join([f"<li style='margin-bottom: 6px;'>{p}</li>" for p in priorities])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>EIAP Executive Performance Briefing</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; color: #0F172A;">
            <div style="max-width: 680px; margin: 30px auto; background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                
                <!-- Header Banner -->
                <div style="background-color: #0F172A; padding: 24px 32px; color: #FFFFFF;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h1 style="margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.5px;">Enterprise Intelligence Automation Platform</h1>
                        <span style="background-color: #D97706; color: #FFFFFF; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">
                            Demo • Synthetic Data
                        </span>
                    </div>
                    <p style="margin: 6px 0 0 0; color: #94A3B8; font-size: 13px;">
                        Executive Commercial Briefing | Period: {snapshot.period_start.strftime('%b %d, %Y')} – {snapshot.period_end.strftime('%b %d, %Y')}
                    </p>
                </div>

                <!-- Content Area -->
                <div style="padding: 32px;">
                    
                    <!-- KPI Cards Grid -->
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                        <tr>
                            <td style="width: 32%; background-color: #F1F5F9; padding: 16px; border-radius: 6px; text-align: center; border: 1px solid #E2E8F0;">
                                <div style="font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase;">Net Revenue</div>
                                <div style="font-size: 22px; font-weight: 700; color: #0F172A; margin-top: 4px;">${rev:,.2f}</div>
                                <div style="font-size: 11px; color: #059669; margin-top: 2px;">{curr} Base</div>
                            </td>
                            <td style="width: 2%;"></td>
                            <td style="width: 32%; background-color: #F1F5F9; padding: 16px; border-radius: 6px; text-align: center; border: 1px solid #E2E8F0;">
                                <div style="font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase;">Gross Profit</div>
                                <div style="font-size: 22px; font-weight: 700; color: #0D9488; margin-top: 4px;">${profit:,.2f}</div>
                                <div style="font-size: 11px; color: #0D9488; margin-top: 2px;">{margin:.2f}% Margin</div>
                            </td>
                            <td style="width: 2%;"></td>
                            <td style="width: 32%; background-color: #F1F5F9; padding: 16px; border-radius: 6px; text-align: center; border: 1px solid #E2E8F0;">
                                <div style="font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase;">Total Orders</div>
                                <div style="font-size: 22px; font-weight: 700; color: #0F172A; margin-top: 4px;">{orders:,}</div>
                                <div style="font-size: 11px; color: #64748B; margin-top: 2px;">${aov:,.2f} AOV</div>
                            </td>
                        </tr>
                    </table>

                    <!-- AI Executive Summary Card -->
                    <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; padding: 20px; margin-bottom: 24px;">
                        <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #1E3A8A; font-weight: 600;">
                            Grounded AI Executive Overview
                        </h2>
                        <p style="margin: 0 0 14px 0; font-size: 13.5px; line-height: 1.6; color: #334155;">
                            {overview_text}
                        </p>
                        
                        <h4 style="margin: 12px 0 6px 0; font-size: 13px; color: #0F172A;">Recommended Priorities:</h4>
                        <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #475569; line-height: 1.5;">
                            {priority_bullets}
                        </ul>
                    </div>

                    <!-- Anomaly Section -->
                    {anomaly_section}

                    <!-- Product Performance Table -->
                    <div style="margin-top: 28px;">
                        <h3 style="margin: 0 0 12px 0; font-size: 15px; color: #0F172A;">Top Performing Product Categories</h3>
                        <table style="width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #E2E8F0;">
                            <thead>
                                <tr style="background-color: #F1F5F9; text-align: left; color: #475569; font-weight: 600;">
                                    <th style="padding: 10px 12px;">Category</th>
                                    <th style="padding: 10px 12px; text-align: right;">Revenue</th>
                                    <th style="padding: 10px 12px; text-align: right;">Margin %</th>
                                    <th style="padding: 10px 12px; text-align: right;">Orders</th>
                                </tr>
                            </thead>
                            <tbody>
                                {cat_rows}
                            </tbody>
                        </table>
                    </div>

                </div>

                <!-- Footer -->
                <div style="background-color: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 20px 32px; font-size: 11px; color: #64748B; text-align: center;">
                    <p style="margin: 0 0 4px 0;">
                        Report ID: <code style="color: #0F172A;">{report_id}</code> | Snapshot: <code>{str(snapshot.snapshot_id)[:8]}</code>
                    </p>
                    <p style="margin: 0;">
                        Generated automatically by EIAP Data & AI Engine • Local Demonstration System • Portfolio of Datta Sable
                    </p>
                </div>

            </div>
        </body>
        </html>
        """
