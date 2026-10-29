import abc
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session
from apps.api.src.config import settings
from apps.api.src.models.entities import IngestionRun, IntegrationEvent
from apps.api.src.schemas.integrations import PowerBIRefreshRequest, PowerBIRefreshResponse

logger = logging.getLogger("eiap.powerbi")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BasePowerBIAdapter(abc.ABC):
    @abc.abstractmethod
    async def trigger_refresh(
        self,
        request: PowerBIRefreshRequest,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        pass

    @abc.abstractmethod
    async def get_refresh_status(
        self,
        refresh_id: str,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        pass


class MockPowerBIAdapter(BasePowerBIAdapter):
    """
    Deterministic Mock Power BI Adapter for zero-cloud-cost local development,
    automated testing, and offline portfolio demonstration.
    Simulates asynchronous refresh lifecycle: QUEUED -> IN_PROGRESS -> COMPLETED (or FAILED).
    """

    # In-memory session state for simulated operations
    _operations: Dict[str, Dict[str, Any]] = {}

    async def trigger_refresh(
        self,
        request: PowerBIRefreshRequest,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        # Check for active or recently completed refresh for idempotency (within 5 minutes)
        for existing_id, op in self._operations.items():
            if (
                op["dataset_id"] == request.dataset_id
                and op.get("run_id") == (str(request.run_id) if request.run_id else None)
                and op["status"] in ("QUEUED", "IN_PROGRESS", "COMPLETED")
            ):
                age_seconds = (utc_now() - op["submitted_at"]).total_seconds()
                if age_seconds < 300:  # 5 minute deduplication window
                    logger.info(
                        f"Idempotent refresh requested for dataset {request.dataset_id}; returning active refresh {existing_id}"
                    )
                    return PowerBIRefreshResponse(
                        refresh_id=existing_id,
                        dataset_id=op["dataset_id"],
                        workspace_id=op.get("workspace_id"),
                        run_id=request.run_id,
                        status=op["status"],
                        submitted_at=op["submitted_at"],
                        completed_at=op.get("completed_at"),
                        attempts=op.get("attempts", 0),
                        idempotent_replay=True,
                        adapter_mode="mock",
                    )

        refresh_id = f"pbi_ref_{uuid.uuid4().hex[:12]}"
        now = utc_now()

        # Track state
        self._operations[refresh_id] = {
            "refresh_id": refresh_id,
            "dataset_id": request.dataset_id,
            "workspace_id": request.workspace_id,
            "run_id": str(request.run_id) if request.run_id else None,
            "status": "IN_PROGRESS",
            "submitted_at": now,
            "completed_at": None,
            "attempts": 0,
            "simulate_failure": request.simulate_failure,
            "simulate_timeout": request.simulate_timeout,
            "correlation_id": correlation_id,
        }

        # Check if run_id exists in DB to prevent foreign key violation
        valid_run_id = None
        if request.run_id:
            exists = db.query(IngestionRun).filter(IngestionRun.run_id == request.run_id).first()
            if exists:
                valid_run_id = request.run_id

        # Persist event to integration_events
        event = IntegrationEvent(
            run_id=valid_run_id,
            integration_type="POWERBI_REFRESH",
            external_request_id=refresh_id,
            status="SUBMITTED",
            metadata_json={
                "dataset_id": request.dataset_id,
                "workspace_id": request.workspace_id,
                "correlation_id": correlation_id,
                "simulate_failure": request.simulate_failure,
                "simulate_timeout": request.simulate_timeout,
                "adapter": "mock",
            },
            occurred_at=now,
        )
        db.add(event)
        db.commit()

        logger.info(
            f"Mock Power BI refresh submitted: {refresh_id} for dataset {request.dataset_id} (corr: {correlation_id})"
        )

        return PowerBIRefreshResponse(
            refresh_id=refresh_id,
            dataset_id=request.dataset_id,
            workspace_id=request.workspace_id,
            run_id=request.run_id,
            status="IN_PROGRESS",
            submitted_at=now,
            completed_at=None,
            attempts=0,
            idempotent_replay=False,
            adapter_mode="mock",
        )

    async def get_refresh_status(
        self,
        refresh_id: str,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        op = self._operations.get(refresh_id)
        if not op:
            # Query from DB if present
            event = (
                db.query(IntegrationEvent)
                .filter(IntegrationEvent.external_request_id == refresh_id)
                .order_by(IntegrationEvent.occurred_at.desc())
                .first()
            )
            if not event:
                raise KeyError(f"Power BI refresh with ID '{refresh_id}' not found.")
            meta = event.metadata_json or {}
            return PowerBIRefreshResponse(
                refresh_id=refresh_id,
                dataset_id=meta.get("dataset_id", "unknown"),
                workspace_id=meta.get("workspace_id"),
                run_id=event.run_id,
                status=event.status,
                submitted_at=event.occurred_at,
                completed_at=event.occurred_at if event.status in ("COMPLETED", "FAILED") else None,
                attempts=1,
                idempotent_replay=False,
                adapter_mode="mock",
            )

        op["attempts"] += 1
        now = utc_now()

        # Handle failure simulation
        if op.get("simulate_failure"):
            op["status"] = "FAILED"
            op["completed_at"] = now
            op["error_message"] = "Simulated upstream Power BI error: Data source connection timeout"
        # Handle timeout simulation: stays IN_PROGRESS
        elif op.get("simulate_timeout"):
            op["status"] = "IN_PROGRESS"
        # Normal async progression: 1st poll -> IN_PROGRESS, 2nd poll -> COMPLETED
        elif op["attempts"] >= 1:
            op["status"] = "COMPLETED"
            op["completed_at"] = now

        # Update integration_events record
        event = (
            db.query(IntegrationEvent)
            .filter(IntegrationEvent.external_request_id == refresh_id)
            .order_by(IntegrationEvent.occurred_at.desc())
            .first()
        )
        if event:
            event.status = op["status"]
            meta = event.metadata_json or {}
            meta["attempts"] = op["attempts"]
            meta["completed_at"] = op["completed_at"].isoformat() if op["completed_at"] else None
            if op.get("error_message"):
                meta["error_message"] = op["error_message"]
            event.metadata_json = meta
            db.commit()

        run_uuid = None
        if op.get("run_id"):
            try:
                run_uuid = uuid.UUID(op["run_id"])
            except Exception:
                pass

        return PowerBIRefreshResponse(
            refresh_id=refresh_id,
            dataset_id=op["dataset_id"],
            workspace_id=op.get("workspace_id"),
            run_id=run_uuid,
            status=op["status"],
            submitted_at=op["submitted_at"],
            completed_at=op["completed_at"],
            attempts=op["attempts"],
            idempotent_replay=False,
            error_message=op.get("error_message"),
            adapter_mode="mock",
        )


class RealPowerBIAdapter(BasePowerBIAdapter):
    """
    Microsoft Power BI REST API adapter with Microsoft Entra ID (Azure AD)
    OAuth2 client credentials authentication.
    Enabled conditionally via FEATURE_FLAG_POWERBI_ENABLED=true.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.tenant_id = tenant_id or getattr(settings, "POWERBI_TENANT_ID", "")
        self.client_id = client_id or getattr(settings, "POWERBI_CLIENT_ID", "")
        self.client_secret = client_secret or getattr(settings, "POWERBI_CLIENT_SECRET", "")
        self.base_url = "https://api.powerbi.com/v1.0/myorg"
        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    async def _get_access_token(self) -> str:
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise ValueError(
                "Power BI service principal credentials not configured. "
                "Ensure POWERBI_TENANT_ID, POWERBI_CLIENT_ID, and POWERBI_CLIENT_SECRET are set."
            )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://analysis.windows.net/powerbi/api/.default",
                },
            )
            if resp.status_code != 200:
                logger.error(f"Entra ID token retrieval failed: HTTP {resp.status_code}")
                raise ConnectionError("Failed to obtain Microsoft Entra ID access token for Power BI API.")
            return resp.json()["access_token"]

    async def trigger_refresh(
        self,
        request: PowerBIRefreshRequest,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        token = await self._get_access_token()
        now = utc_now()
        url = (
            f"{self.base_url}/groups/{request.workspace_id}/datasets/{request.dataset_id}/refreshes"
            if request.workspace_id
            else f"{self.base_url}/datasets/{request.dataset_id}/refreshes"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Correlation-ID": correlation_id,
                },
                json={"notifyOption": "NoNotification"},
            )
            if resp.status_code not in (200, 202):
                logger.error(f"Power BI REST API refresh request failed: {resp.status_code} - {resp.text}")
                raise RuntimeError(f"Power BI API returned error: HTTP {resp.status_code}")

            refresh_id = resp.headers.get("X-PowerBI-RequestId") or f"pbi_real_{uuid.uuid4().hex[:12]}"

        # Record in integration_events
        valid_run_id = None
        if request.run_id:
            exists = db.query(IngestionRun).filter(IngestionRun.run_id == request.run_id).first()
            if exists:
                valid_run_id = request.run_id

        event = IntegrationEvent(
            run_id=valid_run_id,
            integration_type="POWERBI_REFRESH",
            external_request_id=refresh_id,
            status="SUBMITTED",
            metadata_json={
                "dataset_id": request.dataset_id,
                "workspace_id": request.workspace_id,
                "correlation_id": correlation_id,
                "adapter": "real",
            },
            occurred_at=now,
        )
        db.add(event)
        db.commit()

        return PowerBIRefreshResponse(
            refresh_id=refresh_id,
            dataset_id=request.dataset_id,
            workspace_id=request.workspace_id,
            run_id=request.run_id,
            status="IN_PROGRESS",
            submitted_at=now,
            completed_at=None,
            attempts=0,
            idempotent_replay=False,
            adapter_mode="real",
        )

    async def get_refresh_status(
        self,
        refresh_id: str,
        correlation_id: str,
        db: Session,
    ) -> PowerBIRefreshResponse:
        token = await self._get_access_token()
        # In a real environment, query latest refresh history for the dataset
        # For simplicity and robustness, read integration_event metadata to find dataset_id
        event = (
            db.query(IntegrationEvent)
            .filter(IntegrationEvent.external_request_id == refresh_id)
            .order_by(IntegrationEvent.occurred_at.desc())
            .first()
        )
        if not event:
            raise KeyError(f"Power BI refresh operation '{refresh_id}' not found.")

        meta = event.metadata_json or {}
        dataset_id = meta.get("dataset_id")
        workspace_id = meta.get("workspace_id")
        url = (
            f"{self.base_url}/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top=1"
            if workspace_id
            else f"{self.base_url}/datasets/{dataset_id}/refreshes?$top=1"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch refresh status: HTTP {resp.status_code}")

            data = resp.json().get("value", [])
            latest = data[0] if data else {}
            api_status = latest.get("status", "Unknown").upper()
            status_map = {
                "COMPLETED": "COMPLETED",
                "FAILED": "FAILED",
                "DISABLED": "FAILED",
                "UNKNOWN": "IN_PROGRESS",
            }
            mapped_status = status_map.get(api_status, "IN_PROGRESS")

            event.status = mapped_status
            db.commit()

            return PowerBIRefreshResponse(
                refresh_id=refresh_id,
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                run_id=event.run_id,
                status=mapped_status,
                submitted_at=event.occurred_at,
                completed_at=utc_now() if mapped_status in ("COMPLETED", "FAILED") else None,
                attempts=1,
                idempotent_replay=False,
                adapter_mode="real",
            )


def get_powerbi_adapter() -> BasePowerBIAdapter:
    """Factory selecting Mock or Real adapter depending on feature flags and configuration."""
    if settings.FEATURE_FLAG_POWERBI_ENABLED and settings.POWERBI_ADAPTER.lower() == "real":
        return RealPowerBIAdapter()
    return MockPowerBIAdapter()

