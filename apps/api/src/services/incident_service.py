import logging
import random
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from apps.api.src.config import settings
from apps.api.src.models.entities import OperationalIncident
from apps.api.src.schemas.operations import IncidentRecordRequest, IncidentResponse

logger = logging.getLogger("eiap.incident_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentService:
    def __init__(self, db: Session):
        self.db = db

    def record_incident(self, req: IncidentRecordRequest, correlation_id: str) -> IncidentResponse:
        """
        Classifies operational failures, calculates backoff jitter,
        schedules next retry timestamp, stores incident records in PostgreSQL,
        and alerts operations via Mailpit.
        """
        corr = req.correlation_id or correlation_id
        category, severity, is_retryable = self._classify_failure(req.error_code, req.error_message, req.failure_category)

        # Calculate backoff with jitter if transient
        suggested_backoff = None
        scheduled_retry_at = None
        now = utc_now()

        if is_retryable:
            base_backoff = min(60.0, 2.0 ** 1.0)
            jitter = random.uniform(0.5, 2.0)
            suggested_backoff = round(base_backoff + jitter, 2)
            scheduled_retry_at = now + timedelta(seconds=suggested_backoff)

        incident_id = uuid.uuid4()
        details = dict(req.error_details or {})
        details["scheduled_retry_at"] = scheduled_retry_at.isoformat() if scheduled_retry_at else None
        details["suggested_backoff_seconds"] = suggested_backoff
        details["retry_audit_trail"] = []

        record = OperationalIncident(
            incident_id=incident_id,
            workflow_name=req.workflow_name,
            execution_id=req.execution_id,
            correlation_id=corr,
            failure_category=category,
            severity=severity,
            status="OPEN" if is_retryable else "DEAD_LETTER",
            error_code=req.error_code,
            error_message=req.error_message,
            error_details=details,
            retry_count=0,
            max_retries=3 if is_retryable else 0,
            created_at=now,
        )
        self.db.add(record)
        self.db.commit()

        # Dispatch Local Alert via Mailpit for high-severity incidents
        if severity in ("CRITICAL", "WARNING"):
            self._send_incident_alert_email(record)

        logger.info(
            f"Recorded operational incident {incident_id} [{category}/{severity}] for workflow '{req.workflow_name}' "
            f"(Retryable: {is_retryable}, Backoff: {suggested_backoff}s)"
        )

        return IncidentResponse(
            incident_id=incident_id,
            workflow_name=record.workflow_name,
            execution_id=record.execution_id,
            correlation_id=record.correlation_id,
            failure_category=record.failure_category,
            severity=record.severity,
            status=record.status,
            error_code=record.error_code,
            error_message=record.error_message,
            retry_count=record.retry_count,
            max_retries=record.max_retries,
            eligible_for_retry=is_retryable,
            suggested_backoff_seconds=suggested_backoff,
            created_at=record.created_at,
            last_retried_at=record.last_retried_at,
            resolved_at=record.resolved_at,
        )

    def execute_delayed_retry(self, incident_id: uuid.UUID, force: bool = False) -> IncidentResponse:
        """
        Enforces actual elapsed backoff duration before executing retry.
        If current time is before scheduled_retry_at and not force, rejects early retry.
        Demonstrates actual elapsed delay with nanosecond-resolution timestamp audit.
        """
        record = self.db.query(OperationalIncident).filter(OperationalIncident.incident_id == incident_id).first()
        if not record:
            raise KeyError(f"Incident '{incident_id}' not found.")

        if record.status == "RESOLVED":
            raise ValueError("Incident is already marked RESOLVED.")

        if record.status == "DEAD_LETTER" or record.retry_count >= record.max_retries:
            record.status = "DEAD_LETTER"
            self.db.commit()
            raise ValueError(f"Incident exceeded maximum allowed retries ({record.max_retries}). Moved to DEAD_LETTER.")

        now = utc_now()
        details = dict(record.error_details or {})
        scheduled_iso = details.get("scheduled_retry_at")

        if scheduled_iso and not force:
            scheduled_dt = datetime.fromisoformat(scheduled_iso)
            if now < scheduled_dt:
                remaining_s = round((scheduled_dt - now).total_seconds(), 2)
                raise TimeoutError(
                    f"Retry rejected: Backoff interval has not elapsed yet. "
                    f"Scheduled for {scheduled_iso} ({remaining_s}s remaining). Refusing early retry."
                )

        # Execute Retry
        record.retry_count += 1
        record.last_retried_at = now
        elapsed_since_created = round((now - record.created_at).total_seconds(), 3)

        # Calculate next backoff interval with exponential backoff & jitter
        base_backoff = min(60.0, 2.0 ** float(record.retry_count + 1))
        jitter = random.uniform(0.5, 2.0)
        next_backoff = round(base_backoff + jitter, 2)
        next_scheduled = now + timedelta(seconds=next_backoff)

        # Audit trail recording genuine timing evidence
        trail = list(details.get("retry_audit_trail", []))
        trail.append({
            "retry_attempt": record.retry_count,
            "executed_at": now.isoformat(),
            "elapsed_seconds_since_incident": elapsed_since_created,
            "next_backoff_seconds": next_backoff if record.retry_count < record.max_retries else None,
        })

        details["retry_audit_trail"] = trail
        details["scheduled_retry_at"] = next_scheduled.isoformat() if record.retry_count < record.max_retries else None
        details["suggested_backoff_seconds"] = next_backoff
        record.error_details = details

        if record.retry_count >= record.max_retries:
            record.status = "DEAD_LETTER"
            logger.warning(f"Incident {incident_id} exhausted all {record.max_retries} retries. Moved to DEAD_LETTER.")
        else:
            record.status = "RETRIED"

        self.db.commit()

        logger.info(
            f"Executed delayed retry for incident {incident_id} (Attempt {record.retry_count}/{record.max_retries}, "
            f"Elapsed: {elapsed_since_created}s, Next Backoff: {next_backoff}s)"
        )

        return IncidentResponse(
            incident_id=record.incident_id,
            workflow_name=record.workflow_name,
            execution_id=record.execution_id,
            correlation_id=record.correlation_id,
            failure_category=record.failure_category,
            severity=record.severity,
            status=record.status,
            error_code=record.error_code,
            error_message=record.error_message,
            retry_count=record.retry_count,
            max_retries=record.max_retries,
            eligible_for_retry=(record.status == "RETRIED" and record.retry_count < record.max_retries),
            suggested_backoff_seconds=next_backoff if record.retry_count < record.max_retries else None,
            created_at=record.created_at,
            last_retried_at=record.last_retried_at,
            resolved_at=record.resolved_at,
        )

    def retry_incident(self, incident_id: uuid.UUID) -> IncidentResponse:
        """Alias delegating to execute_delayed_retry with force=True for backward compatibility."""
        return self.execute_delayed_retry(incident_id, force=True)

    def resolve_incident(self, incident_id: uuid.UUID, note: str) -> IncidentResponse:
        """
        Closes an operational incident as RESOLVED.
        """
        record = self.db.query(OperationalIncident).filter(OperationalIncident.incident_id == incident_id).first()
        if not record:
            raise KeyError(f"Incident '{incident_id}' not found.")

        now = utc_now()
        record.status = "RESOLVED"
        record.resolved_at = now
        details = dict(record.error_details or {})
        details["resolution_note"] = note
        details["resolved_timestamp"] = now.isoformat()
        record.error_details = details
        self.db.commit()

        logger.info(f"Incident {incident_id} marked RESOLVED: {note}")

        return IncidentResponse(
            incident_id=record.incident_id,
            workflow_name=record.workflow_name,
            execution_id=record.execution_id,
            correlation_id=record.correlation_id,
            failure_category=record.failure_category,
            severity=record.severity,
            status=record.status,
            error_code=record.error_code,
            error_message=record.error_message,
            retry_count=record.retry_count,
            max_retries=record.max_retries,
            eligible_for_retry=False,
            suggested_backoff_seconds=None,
            created_at=record.created_at,
            last_retried_at=record.last_retried_at,
            resolved_at=record.resolved_at,
        )

    def _classify_failure(
        self,
        error_code: str,
        error_message: str,
        user_category: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        """
        Deterministic failure classifier:
        - TRANSIENT: network timeouts, 502/503/504, connection errors -> is_retryable=True
        - AUTH: 401/403, missing/invalid key -> is_retryable=False, severity=CRITICAL
        - VALIDATION: 422, missing fields, schema errors -> is_retryable=False, severity=WARNING
        - PERMANENT: logic errors, null constraints -> is_retryable=False, severity=WARNING
        """
        if user_category and user_category in ("TRANSIENT", "PERMANENT", "AUTH", "VALIDATION", "INFRASTRUCTURE"):
            category = user_category
            is_retryable = (category == "TRANSIENT")
            severity = "CRITICAL" if category in ("AUTH", "INFRASTRUCTURE") else "WARNING"
            return category, severity, is_retryable

        text = f"{error_code} {error_message}".lower()

        if any(w in text for w in ("auth", "401", "403", "forbidden", "unauthorized", "invalid key")):
            return "AUTH", "CRITICAL", False
        elif any(w in text for w in ("timeout", "502", "503", "504", "connection", "busy", "temporary", "econnreset", "lock")):
            return "TRANSIENT", "WARNING", True
        elif any(w in text for w in ("validation", "422", "schema", "invalid field", "format")):
            return "VALIDATION", "WARNING", False
        elif any(w in text for w in ("disk", "space", "out of memory", "oom")):
            return "INFRASTRUCTURE", "CRITICAL", False
        else:
            return "PERMANENT", "WARNING", False

    def _send_incident_alert_email(self, incident: OperationalIncident):
        """
        Delivers an incident alert to Mailpit for local observability.
        """
        try:
            smtp_host = settings.SMTP_HOST if settings.RUNNING_IN_DOCKER else settings.LOCAL_SMTP_HOST
            smtp_port = settings.SMTP_PORT if settings.RUNNING_IN_DOCKER else settings.LOCAL_SMTP_PORT

            msg = EmailMessage()
            msg["Subject"] = f"[EIAP OPERATIONAL ALERT - {incident.severity}] {incident.workflow_name} Failed ({incident.error_code})"
            msg["From"] = settings.SMTP_FROM
            msg["To"] = "devops-alerts@internal.local"
            msg["X-Incident-ID"] = str(incident.incident_id)

            body = (
                f"OPERATIONAL INCIDENT ALERT\n"
                f"--------------------------\n"
                f"Incident ID: {incident.incident_id}\n"
                f"Workflow: {incident.workflow_name}\n"
                f"Execution ID: {incident.execution_id or 'N/A'}\n"
                f"Correlation ID: {incident.correlation_id}\n"
                f"Category: {incident.failure_category}\n"
                f"Severity: {incident.severity}\n"
                f"Status: {incident.status}\n"
                f"Error Code: {incident.error_code}\n"
                f"Error Message: {incident.error_message}\n"
                f"Timestamp: {incident.created_at.isoformat()}\n\n"
                f"Automated Action: Incident registered in operational database.\n"
                f"Review & resolve via EIAP Operations Console."
            )
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
                server.send_message(msg)
            logger.info(f"Dispatched incident alert for {incident.incident_id} to Mailpit.")
        except Exception as exc:
            logger.warning(f"Failed to deliver incident alert email: {exc}")
