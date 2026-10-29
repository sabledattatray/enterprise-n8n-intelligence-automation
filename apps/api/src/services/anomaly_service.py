import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from apps.api.src.models.entities import AnomalyEvent, KPISnapshot
from apps.api.src.schemas.kpi import AnomalyEvaluationResult, AnomalyEventData

logger = logging.getLogger("eiap.anomaly")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnomalyService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate_anomalies(self, snapshot_id: uuid.UUID) -> AnomalyEvaluationResult:
        """
        Evaluates rule-based business anomalies against a materialized KPI snapshot.
        Rules:
          1. RULE_REV_SPIKE: Relative daily revenue spike > 50% vs 7-day trailing baseline.
          2. RULE_MARGIN_DROP: Profit margin drops below 35.0% or relative drop > 30%.
          3. RULE_CANCEL_SPIKE: Order cancellation rate > 15.0%.
        Applies alert suppression to avoid duplicate alerts within a 24-hour window.
        """
        snapshot = self.db.query(KPISnapshot).filter(KPISnapshot.snapshot_id == snapshot_id).first()
        if not snapshot:
            raise KeyError(f"KPI snapshot '{snapshot_id}' not found.")

        detected: List[AnomalyEventData] = []
        suppressed_count = 0

        # Rule 1: Daily Revenue Spikes vs 7-Day Trailing Baseline
        # Find daily trends for the currency
        sql_daily = text("""
            SELECT
                d.full_date,
                COALESCE(SUM(f.revenue), 0) AS daily_rev,
                COUNT(DISTINCT f.external_order_id) AS orders
            FROM fact_orders f
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE f.currency_code = :currency
            GROUP BY d.full_date
            ORDER BY d.full_date ASC
        """)
        rows = self.db.execute(sql_daily, {"currency": snapshot.currency_code}).mappings().all()

        daily_data = [(r["full_date"], float(r["daily_rev"]), int(r["orders"])) for r in rows]

        # Scan for daily spikes using 7-day rolling window
        for i in range(len(daily_data)):
            dt, rev, orders = daily_data[i]
            # Prior window of up to 7 days
            prior_window = [daily_data[j][1] for j in range(max(0, i - 7), i)]
            if len(prior_window) >= 3:
                baseline_mean = sum(prior_window) / len(prior_window)
                if baseline_mean >= 1000.0:  # Minimum volume filter
                    pct_increase = ((rev - baseline_mean) / baseline_mean) * 100.0
                    if pct_increase >= 50.0:
                        severity = "CRITICAL" if pct_increase >= 100.0 else "WARNING"
                        msg = (
                            f"Daily revenue spike on {dt}: ${rev:,.2f} vs 7-day baseline "
                            f"${baseline_mean:,.2f} (+{pct_increase:.1f}% increase)."
                        )
                        event = self._process_anomaly_candidate(
                            snapshot_id=snapshot.snapshot_id,
                            rule_id="RULE_REV_SPIKE",
                            metric="daily_revenue",
                            observed=rev,
                            baseline=baseline_mean,
                            deviation=pct_increase,
                            severity=severity,
                            message=msg,
                        )
                        if event:
                            detected.append(event)
                        else:
                            suppressed_count += 1

        # Rule 2: Profit Margin Drop (< 35.0% absolute threshold or baseline expected 50.0%)
        margin = float(snapshot.margin_pct)
        baseline_margin = 50.0  # Enterprise target baseline
        if margin < 35.0:
            severity = "CRITICAL" if margin < 25.0 else "WARNING"
            margin_drop_pct = ((baseline_margin - margin) / baseline_margin) * 100.0
            msg = (
                f"Low profit margin observed: {margin:.2f}% (target baseline {baseline_margin:.1f}%, "
                f"-{margin_drop_pct:.1f}% below target)."
            )
            event = self._process_anomaly_candidate(
                snapshot_id=snapshot.snapshot_id,
                rule_id="RULE_MARGIN_DROP",
                metric="margin_pct",
                observed=margin,
                baseline=baseline_margin,
                deviation=margin_drop_pct,
                severity=severity,
                message=msg,
            )
            if event:
                detected.append(event)
            else:
                suppressed_count += 1

        # Rule 3: Cancellation Rate Spike (> 15.0%)
        # Calculate cancellation rate for snapshot period
        sql_cancel = text("""
            SELECT
                ROUND(
                    COUNT(CASE WHEN f.order_status = 'CANCELLED' THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100,
                    2
                ) AS cancel_rate
            FROM fact_orders f
            WHERE f.currency_code = :currency
        """)
        cancel_row = self.db.execute(sql_cancel, {"currency": snapshot.currency_code}).mappings().first()
        cancel_rate = float(cancel_row["cancel_rate"] or 0.0) if cancel_row else 0.0
        baseline_cancel_rate = 5.0  # Enterprise baseline target
        if cancel_rate > 15.0:
            severity = "CRITICAL" if cancel_rate > 25.0 else "WARNING"
            cancel_increase_pct = ((cancel_rate - baseline_cancel_rate) / baseline_cancel_rate) * 100.0
            msg = (
                f"Elevated order cancellation rate: {cancel_rate:.2f}% (normal baseline {baseline_cancel_rate:.1f}%, "
                f"+{cancel_increase_pct:.1f}% increase)."
            )
            event = self._process_anomaly_candidate(
                snapshot_id=snapshot.snapshot_id,
                rule_id="RULE_CANCEL_SPIKE",
                metric="cancellation_rate_pct",
                observed=cancel_rate,
                baseline=baseline_cancel_rate,
                deviation=cancel_increase_pct,
                severity=severity,
                message=msg,
            )
            if event:
                detected.append(event)
            else:
                suppressed_count += 1

        # Generate Executive Alert Headline and Text
        if detected:
            headline = f"[ALERT] {len(detected)} Business Anomalies Detected (Snapshot {str(snapshot.snapshot_id)[:8]})"
            bullets = "\n".join([f"- [{e.severity}] {e.rule_id} ({e.metric}): {e.message}" for e in detected])
            exec_text = (
                f"Executive Alert Summary\n"
                f"-----------------------\n"
                f"Timestamp: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Snapshot: {snapshot.snapshot_id}\n"
                f"Currency: {snapshot.currency_code}\n"
                f"Total Revenue: ${float(snapshot.revenue):,.2f} | Orders: {snapshot.orders:,}\n"
                f"Quality Score: {float(snapshot.quality_score):.1f}%\n\n"
                f"Detected Anomalies ({len(detected)}):\n{bullets}\n\n"
                f"Action Required: Investigation recommended by operations & BI leads."
            )
        else:
            headline = f"[NORMAL] No Critical Anomalies Detected (Snapshot {str(snapshot.snapshot_id)[:8]})"
            exec_text = (
                f"Executive Status Digest\n"
                f"-----------------------\n"
                f"Timestamp: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Snapshot: {snapshot.snapshot_id}\n"
                f"Total Revenue: ${float(snapshot.revenue):,.2f} | Profit: ${float(snapshot.profit):,.2f} | Margin: {float(snapshot.margin_pct):.2f}%\n"
                f"All metrics within standard operational control boundaries."
            )

        logger.info(
            f"Anomaly evaluation for snapshot {snapshot_id}: {len(detected)} detected, {suppressed_count} suppressed."
        )

        return AnomalyEvaluationResult(
            snapshot_id=snapshot.snapshot_id,
            anomalies_detected=len(detected),
            anomalies=detected,
            summary_headline=headline,
            executive_alert_text=exec_text,
        )

    def _process_anomaly_candidate(
        self,
        snapshot_id: uuid.UUID,
        rule_id: str,
        metric: str,
        observed: float,
        baseline: float,
        deviation: float,
        severity: str,
        message: str,
    ) -> Optional[AnomalyEventData]:
        """
        Suppresses alerts if an OPEN anomaly for the exact rule and metric was created within 24 hours.
        Otherwise, records the new AnomalyEvent to the database.
        """
        cutoff = utc_now() - timedelta(hours=24)
        recent_open = (
            self.db.query(AnomalyEvent)
            .filter(
                AnomalyEvent.rule_id == rule_id,
                AnomalyEvent.metric == metric,
                AnomalyEvent.status == "OPEN",
                AnomalyEvent.created_at >= cutoff,
            )
            .first()
        )

        if recent_open:
            logger.info(
                f"Alert suppression active: open alert {recent_open.anomaly_id} exists for {rule_id}/{metric} within 24h. Suppressing duplicate."
            )
            return None

        anomaly_id = uuid.uuid4()
        now = utc_now()
        event = AnomalyEvent(
            anomaly_id=anomaly_id,
            snapshot_id=snapshot_id,
            rule_id=rule_id,
            metric=metric,
            observed_value=Decimal(str(round(observed, 4))),
            baseline_value=Decimal(str(round(baseline, 4))),
            severity=severity,
            status="OPEN",
            created_at=now,
        )
        self.db.add(event)
        self.db.commit()

        return AnomalyEventData(
            anomaly_id=anomaly_id,
            snapshot_id=snapshot_id,
            rule_id=rule_id,
            metric=metric,
            observed_value=round(observed, 2),
            baseline_value=round(baseline, 2),
            deviation_pct=round(deviation, 2),
            severity=severity,
            status="OPEN",
            message=message,
            created_at=now,
        )

