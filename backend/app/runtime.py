from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
import shutil
import socket
import subprocess  # nosec B404
import threading
import uuid
from pathlib import Path
from time import perf_counter
import platform

from app.audit_service import AuditService
from app.branding import default_workspace_name
from app.auth import AuthService, utc_now_iso
from app.change_service import ChangeService
from app.connector_support_service import ConnectorSupportService
from app.config import settings
from app.engine import AccessGraphEngine
from app.entitlement_service import EntitlementService
from app.explain_service import ExplainService
from app.feature_inventory_service import FeatureInventoryService
from app.federated_auth import FederatedAuthService
from app.fs_collectors import collect_real_snapshot
from app.graph_service import GraphService
from app.index_refresh_service import IndexRefreshService
from app.governance import build_review_candidates, enrich_campaign_detail, remediation_plan_for_item
from app.integration_collectors import collect_configured_bundles, discover_connector_inventory
from app.job_center_service import JobCenterService
from app.mvp_readiness_service import MvpReadinessService
from app.models import (
    AccessReviewCampaignCreateRequest,
    AccessReviewCampaignDetailResponse,
    AccessReviewCampaignListResponse,
    AccessReviewDecisionRequest,
    AccessReviewRemediationPlan,
    AdminUserListResponse,
    AdminUserSummary,
    AuditEventsResponse,
    AuthProviderCreateRequest,
    AuthProviderDetailResponse,
    AuthProviderListResponse,
    AuthProviderUpdateRequest,
    BenchmarkMetric,
    BenchmarkResponse,
    BenchmarkSnapshot,
    ConnectorRuntimeResponse,
    ConnectorRuntimeStatus,
    ConnectorSupportMatrixResponse,
    ConnectorStatus,
    Entity,
    EntityDetailResponse,
    ExposureAnalyticsResponse,
    FeatureInventoryResponse,
    GroupClosureRecord,
    ImportedSourceBundle,
    ImportedSourceDetailResponse,
    ImportedSourceListResponse,
    ImportedSourceUpdateRequest,
    IndexRefreshSummary,
    InsightNote,
    MetricCard,
    PlatformComponentStatus,
    PlatformPostureResponse,
    QueryPerformanceResponse,
    PrincipalAccessSummaryRecord,
    PublicAuthProviderListResponse,
    JobCenterResponse,
    MvpReadinessResponse,
    PrincipalAccessResponse,
    PrincipalResourceRecord,
    ReportScheduleCreateRequest,
    ReportScheduleDetailResponse,
    ReportScheduleListResponse,
    ReportScheduleRunRecord,
    ReportScheduleUpdateRequest,
    Relationship,
    ResourceAccessRecord,
    ResourceAccessResponse,
    ResourceExposureSummaryRecord,
    ResourceHierarchyRecord,
    OperationalFlowResponse,
    SetupLocalAdminRequest,
    SetupStatusResponse,
    RuntimeStatusResponse,
    ScanRunRecord,
    ScanRunsResponse,
    ScanTarget,
    ScanTargetCreateRequest,
    ScanTargetUpdateRequest,
    SearchResult,
    RiskFinding,
    WorkspaceCreateRequest,
    WorkspaceListResponse,
    WorkspaceSummary,
    WorkspaceUpdateRequest,
)
from app.operational_flow_service import OperationalFlowService
from app.pipeline import NormalizationPipeline, RawCollectionBatch
from app.platform_services import (
    KAFKA_DOCS,
    LANGFUSE_DOCS,
    NEO4J_DOCS,
    TEMPORAL_DOCS,
    build_platform_services,
    configured_component_status,
)
from app.query_performance_service import QueryPerformanceService
from app.report_schedule_service import ReportScheduleService
from app.risk_service import RiskService
from app.search_service import SearchService
from app.storage import AppStorage
from app.whatif_service import WhatIfService

logger = logging.getLogger(__name__)


class RuntimeState:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        configured_data_dir = os.getenv("EIP_DATA_DIR")
        self.data_dir = Path(configured_data_dir) if configured_data_dir else self.project_root / "backend" / "data"
        self.workspace_root_dir = self.data_dir / "workspaces"
        self.workspace_root_dir.mkdir(parents=True, exist_ok=True)
        self.control_storage = AppStorage(self.data_dir / "control.db")
        self.control_storage.initialize()
        self.runtime_role = settings.runtime_role
        self._background_jobs_capable = self.runtime_role in {"all", "worker"}
        self._background_heartbeat_interval_seconds = settings.background_heartbeat_interval_seconds
        self._background_stale_after_seconds = max(
            settings.background_stale_after_seconds,
            self._background_heartbeat_interval_seconds * 3,
        )
        self._background_worker_id = (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self._background_leader = False
        self._background_thread: threading.Thread | None = None
        self._background_stop = threading.Event()
        self.auth = AuthService(self.control_storage, self.data_dir)
        self.federated_auth = FederatedAuthService(self.control_storage, self.auth)
        self.platform_services = build_platform_services()
        self.normalization_pipeline = NormalizationPipeline()
        self.storage: AppStorage
        self.index_refresh_service: IndexRefreshService
        self.active_workspace_id: str | None = None
        self.active_workspace_storage_path: Path | None = None
        self.bootstrap = self.auth.ensure_bootstrap_admin()
        self._last_index_refresh_summary: IndexRefreshSummary | None = None
        self._workspace_lock = threading.RLock()
        self._scan_lock = threading.Lock()
        self._scan_in_progress = False
        self._latest_scan: ScanRunRecord | None = None
        self._connector_runtime_statuses: dict[str, ConnectorRuntimeStatus] = {}
        self._scheduler_enabled = self._background_jobs_capable and os.getenv("EIP_ENABLE_SCHEDULER") == "1"
        self._scheduler_interval_seconds = max(60, int(os.getenv("EIP_SCAN_INTERVAL_SECONDS", "900")))
        self._scheduler_thread: threading.Thread | None = None
        self._scheduler_stop = threading.Event()
        self._report_scheduler_enabled = (
            self._background_jobs_capable and os.getenv("EIP_ENABLE_REPORT_SCHEDULER", "1") != "0"
        )
        self._report_scheduler_interval_seconds = max(
            30,
            int(os.getenv("EIP_REPORT_SCHEDULER_INTERVAL_SECONDS", "60")),
        )
        self._report_scheduler_thread: threading.Thread | None = None
        self._report_scheduler_stop = threading.Event()

        self._ensure_default_workspace()
        active_workspace_id = self.control_storage.active_workspace_id()
        if active_workspace_id is None:
            raise RuntimeError("No active workspace is configured.")
        self._bind_workspace(active_workspace_id)
        self._connector_runtime_statuses = {
            item.id: item
            for item in discover_connector_inventory().connectors
        }
        self._start_background_runtime()
        self._start_scheduler()
        self._start_report_scheduler()

    def _slugify_workspace(self, value: str) -> str:
        slug = "".join(
            character.lower() if character.isalnum() else "-"
            for character in value.strip()
        )
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug.strip("-")
        return slug or "workspace"

    def _workspace_storage_path(self, workspace_id: str) -> Path:
        workspace_dir = self.workspace_root_dir / workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir / "workspace.db"

    def _workspace_summary(self, payload: dict[str, object]) -> WorkspaceSummary:
        storage_path = self._workspace_storage_path(str(payload["id"]))
        return WorkspaceSummary(
            id=str(payload["id"]),
            name=str(payload["name"]),
            slug=str(payload["slug"]),
            description=None if payload.get("description") is None else str(payload["description"]),
            environment=str(payload.get("environment") or "on-prem"),
            active=bool(payload.get("active")),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            storage_path=str(storage_path),
        )

    def _ensure_default_workspace(self) -> None:
        if self.control_storage.list_workspaces():
            return
        default_name = (
            self.control_storage.get_setting("tenant_name")
            or default_workspace_name(socket.gethostname())
        )
        workspace_id = "workspace_default"
        self.control_storage.create_workspace(
            workspace_id=workspace_id,
            name=default_name,
            slug=self._slugify_workspace(default_name),
            description="Default operational workspace.",
            environment="on-prem",
            created_at=utc_now_iso(),
            active=True,
        )

    def _rebuild_workspace_services(self) -> None:
        self.entitlement_service = EntitlementService(lambda: self.engine, self.storage, self.platform_services)
        self.search_service = SearchService(lambda: self.engine, self.platform_services)
        self.explain_service = ExplainService(lambda: self.engine, self.platform_services)
        self.whatif_service = WhatIfService(lambda: self.engine, self.platform_services)
        self.graph_service = GraphService(lambda: self.engine, self.platform_services)
        self.risk_service = RiskService(lambda: self.engine, self.storage, self.platform_services)
        self.change_service = ChangeService(self.storage)
        self.audit_service = AuditService(self.storage)
        self.operational_flow_service = OperationalFlowService(self.storage, lambda: self)
        self.mvp_readiness_service = MvpReadinessService(self.storage, lambda: self)
        self.feature_inventory_service = FeatureInventoryService(self.storage, lambda: self)
        self.connector_support_service = ConnectorSupportService(self.storage, lambda: self)
        self.job_center_service = JobCenterService(self.storage, lambda: self)
        self.query_performance_service = QueryPerformanceService(self.storage)
        self.report_schedule_service = ReportScheduleService(
            self.storage,
            self.data_dir,
            lambda: self.engine,
            self.get_access_review,
        )

    def _bind_workspace(self, workspace_id: str) -> None:
        workspace = self.control_storage.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError(f"Unknown workspace: {workspace_id}")
        self.active_workspace_id = workspace_id
        self.active_workspace_storage_path = self._workspace_storage_path(workspace_id)
        self.storage = AppStorage(self.active_workspace_storage_path)
        self.storage.initialize()
        self.storage.set_setting("tenant_name", str(workspace["name"]))
        self.index_refresh_service = IndexRefreshService(self.storage)
        self._last_index_refresh_summary = None
        self._ensure_default_targets()
        snapshot = self.storage.load_latest_snapshot()
        if snapshot is None:
            tenant_name = str(workspace["name"])
            self.engine = AccessGraphEngine(
                self._empty_engine_snapshot().model_copy(update={"tenant": tenant_name})
            )
            self._latest_scan = None
            if os.getenv("EIP_DISABLE_AUTOSCAN") != "1":
                self.run_scan()
        else:
            self.engine = AccessGraphEngine(snapshot)
            self._refresh_enterprise_indexes(snapshot)
            latest_runs = self.storage.list_scan_runs(limit=1)
            self._latest_scan = latest_runs[0] if latest_runs else None
        self._rebuild_workspace_services()

    def active_workspace(self) -> WorkspaceSummary | None:
        if self.active_workspace_id is None:
            return None
        workspace = self.control_storage.get_workspace(self.active_workspace_id)
        if workspace is None:
            return None
        return self._workspace_summary(workspace)

    def list_workspaces(self) -> WorkspaceListResponse:
        workspaces = [self._workspace_summary(item) for item in self.control_storage.list_workspaces()]
        return WorkspaceListResponse(
            generated_at=utc_now_iso(),
            active_workspace_id=self.active_workspace_id,
            workspaces=workspaces,
        )

    def create_workspace(self, payload: WorkspaceCreateRequest) -> WorkspaceSummary:
        with self._workspace_lock:
            slug = self._slugify_workspace(payload.slug or payload.name)
            if self.control_storage.slug_in_use(slug):
                raise ValueError("A workspace with the same slug already exists.")
            workspace_id = f"workspace_{uuid.uuid4().hex[:12]}"
            self.control_storage.create_workspace(
                workspace_id=workspace_id,
                name=payload.name,
                slug=slug,
                description=payload.description,
                environment=payload.environment,
                created_at=utc_now_iso(),
                active=False,
            )
            workspace = self.control_storage.get_workspace(workspace_id)
            if workspace is None:
                raise RuntimeError("Workspace could not be reloaded after creation.")
            workspace_storage = AppStorage(self._workspace_storage_path(workspace_id))
            workspace_storage.initialize()
            workspace_storage.set_setting("tenant_name", payload.name)
            return self._workspace_summary(workspace)

    def update_workspace(self, workspace_id: str, payload: WorkspaceUpdateRequest) -> WorkspaceSummary | None:
        with self._workspace_lock:
            updated = self.control_storage.update_workspace(
                workspace_id,
                name=payload.name,
                description=payload.description,
                environment=payload.environment,
                updated_at=utc_now_iso(),
            )
            if updated is None:
                return None
            workspace_storage = AppStorage(self._workspace_storage_path(workspace_id))
            workspace_storage.initialize()
            workspace_storage.set_setting("tenant_name", str(updated["name"]))
            if workspace_id == self.active_workspace_id:
                self._bind_workspace(workspace_id)
            return self._workspace_summary(updated)

    def activate_workspace(self, workspace_id: str) -> WorkspaceSummary:
        with self._workspace_lock:
            if not self.control_storage.set_active_workspace(workspace_id, updated_at=utc_now_iso()):
                raise KeyError(f"Unknown workspace: {workspace_id}")
            self._bind_workspace(workspace_id)
            workspace = self.control_storage.get_workspace(workspace_id)
            if workspace is None:
                raise RuntimeError("Workspace could not be reloaded after activation.")
            return self._workspace_summary(workspace)

    def _load_background_leader(self) -> dict[str, object] | None:
        raw = self.storage.get_setting("runtime_background_leader")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _background_leader_age_seconds(self, payload: dict[str, object] | None) -> float | None:
        if not payload:
            return None
        updated_at = payload.get("updated_at")
        if not isinstance(updated_at, str):
            return None
        try:
            timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds())

    def _background_leader_is_stale(self, payload: dict[str, object] | None) -> bool:
        age_seconds = self._background_leader_age_seconds(payload)
        if age_seconds is None:
            return True
        return age_seconds > self._background_stale_after_seconds

    def _background_leader_payload(self) -> dict[str, object]:
        return {
            "worker_id": self._background_worker_id,
            "runtime_role": self.runtime_role,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "updated_at": utc_now_iso(),
            "scan_scheduler_enabled": self._scheduler_enabled,
            "report_scheduler_enabled": self._report_scheduler_enabled,
        }

    def _refresh_background_leader(self) -> None:
        if not self._background_jobs_capable:
            self._background_leader = False
            return
        current = self._load_background_leader()
        current_worker_id = None if current is None else current.get("worker_id")
        if current is None or self._background_leader_is_stale(current) or current_worker_id == self._background_worker_id:
            payload = self._background_leader_payload()
            self.storage.set_setting("runtime_background_leader", json.dumps(payload))
            self._background_leader = True
            return
        self._background_leader = False

    def background_worker_status(self) -> dict[str, object]:
        payload = self._load_background_leader()
        stale = self._background_leader_is_stale(payload)
        if stale:
            payload = None
        worker_id = None if payload is None else payload.get("worker_id")
        state = "missing"
        if self._background_jobs_capable:
            if worker_id == self._background_worker_id and payload is not None:
                state = "local"
            elif payload is not None:
                state = "standby"
        elif payload is not None:
            state = "remote"
        return {
            "state": state,
            "host": None if payload is None else payload.get("host"),
            "runtime_role": None if payload is None else payload.get("runtime_role"),
            "updated_at": None if payload is None else payload.get("updated_at"),
            "scan_scheduler_enabled": bool(payload.get("scan_scheduler_enabled")) if payload else False,
            "report_scheduler_enabled": bool(payload.get("report_scheduler_enabled")) if payload else False,
        }

    def _start_background_runtime(self) -> None:
        if not self._background_jobs_capable or self._background_thread is not None:
            return

        self._refresh_background_leader()

        def _loop() -> None:
            while not self._background_stop.wait(self._background_heartbeat_interval_seconds):
                try:
                    self._refresh_background_leader()
                except Exception:
                    logger.exception("Background runtime heartbeat failed.")

        self._background_thread = threading.Thread(
            target=_loop,
            name="eip-background-runtime",
            daemon=True,
        )
        self._background_thread.start()

    def shutdown(self) -> None:
        self._background_stop.set()
        self._scheduler_stop.set()
        self._report_scheduler_stop.set()

    def runtime_status(self) -> RuntimeStatusResponse:
        targets = self.storage.list_targets()
        snapshot = self.storage.load_latest_snapshot()
        bootstrap = self.auth.bootstrap_status()
        background_worker = self.background_worker_status()
        latest_runs = self.storage.list_scan_runs(limit=10)
        latest_run = latest_runs[0] if latest_runs else None
        last_successful_run = next(
            (
                run
                for run in latest_runs
                if run.status in {"healthy", "warning"} and run.finished_at
            ),
            None,
        )
        raw_stats = self.storage.raw_snapshot_stats()
        access_index_stats = (
            self.storage.materialized_access_index_stats(snapshot.generated_at)
            if snapshot
            else {"row_count": 0}
        )
        freshness_status: str = "empty"
        if snapshot and snapshot.generated_at:
            snapshot_timestamp = datetime.fromisoformat(
                snapshot.generated_at.replace("Z", "+00:00")
            )
            age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - snapshot_timestamp).total_seconds(),
            )
            freshness_status = "fresh" if age_seconds <= 86400 else "stale"
        return RuntimeStatusResponse(
            host=socket.gethostname(),
            platform=platform.system(),
            runtime_role=self.runtime_role,
            admin_username=bootstrap.admin_username,
            bootstrap=bootstrap,
            target_count=len(targets),
            active_target_count=sum(1 for target in targets if target.enabled),
            latest_snapshot_at=snapshot.generated_at if snapshot else None,
            latest_scan_status=latest_run.status if latest_run else None,
            last_successful_scan_at=last_successful_run.finished_at if last_successful_run else None,
            last_successful_scan_duration_ms=(
                last_successful_run.duration_ms if last_successful_run else None
            ),
            raw_batch_count=int(raw_stats["row_count"]),
            materialized_access_rows=int(access_index_stats["row_count"]),
            freshness_status=freshness_status,
            scan_in_progress=self._scan_in_progress,
            scheduler_enabled=self._scheduler_enabled,
            scheduler_interval_seconds=self._scheduler_interval_seconds if self._scheduler_enabled else None,
            report_scheduler_enabled=self._report_scheduler_enabled,
            report_scheduler_interval_seconds=(
                self._report_scheduler_interval_seconds
                if self._report_scheduler_enabled
                else None
            ),
            background_jobs_capable=self._background_jobs_capable,
            background_jobs_active=bool(self._background_leader),
            background_worker_state=str(background_worker["state"]),
            background_worker_host=(
                None
                if background_worker["host"] is None
                else str(background_worker["host"])
            ),
            background_worker_last_seen_at=(
                None
                if background_worker["updated_at"] is None
                else str(background_worker["updated_at"])
            ),
            index_refresh=self._last_index_refresh_summary,
        )

    def mvp_readiness(self) -> MvpReadinessResponse:
        return self.mvp_readiness_service.status()

    def feature_inventory(self) -> FeatureInventoryResponse:
        return self.feature_inventory_service.status()

    def connector_support_matrix(self) -> ConnectorSupportMatrixResponse:
        return self.connector_support_service.status()

    def job_center(self) -> JobCenterResponse:
        return self.job_center_service.status()

    def exposure_analytics(self) -> ExposureAnalyticsResponse:
        snapshot_generated_at = self.engine.snapshot.generated_at
        resource_rows = self.storage.list_resource_exposure_index(snapshot_generated_at, limit=12)
        if not resource_rows:
            resource_rows = self.engine.resource_exposure_index()[:12]
        principal_rows = self.storage.list_principal_access_summary(snapshot_generated_at, limit=12)
        if not principal_rows:
            principal_rows = self.engine.principal_access_summary_index()[:12]
        return ExposureAnalyticsResponse(
            generated_at=utc_now_iso(),
            resource_summaries=[
                ResourceExposureSummaryRecord(
                    resource=self.engine.summary(str(row["resource_id"])),
                    principal_count=int(row["principal_count"]),
                    privileged_principal_count=int(row["privileged_principal_count"]),
                    max_risk_score=int(row["max_risk_score"]),
                    average_path_complexity=int(row["average_path_complexity"]),
                    exposure_score=int(row["exposure_score"]),
                )
                for row in resource_rows
            ],
            principal_summaries=[
                PrincipalAccessSummaryRecord(
                    principal=self.engine.summary(str(row["principal_id"])),
                    resource_count=int(row["resource_count"]),
                    privileged_resource_count=int(row["privileged_resource_count"]),
                    max_risk_score=int(row["max_risk_score"]),
                    average_path_complexity=int(row["average_path_complexity"]),
                    exposure_score=int(row["exposure_score"]),
                )
                for row in principal_rows
            ],
        )

    def query_performance(self) -> QueryPerformanceResponse:
        return self.query_performance_service.status()

    def record_query_metric(
        self,
        *,
        operation: str,
        duration_ms: float,
        status_code: int,
        request_path: str,
    ) -> None:
        timestamp = utc_now_iso()
        self.storage.record_query_metric(
            operation=operation,
            duration_ms=duration_ms,
            status_code=status_code,
            request_path=request_path,
            recorded_at=timestamp,
        )
        self.platform_services.analytics.record_query(
            {
                "recorded_at": timestamp,
                "operation": operation,
                "duration_ms": float(duration_ms),
                "status_code": int(status_code),
                "request_path": request_path,
            }
        )

    def setup_status(self) -> SetupStatusResponse:
        active_workspace = self.active_workspace()
        tenant_name = (
            active_workspace.name
            if active_workspace is not None
            else self.control_storage.get_setting("tenant_name") or default_workspace_name(socket.gethostname())
        )
        auth_provider_count = len(self.control_storage.list_auth_providers())
        return SetupStatusResponse(
            setup_required=self.auth.setup_required(),
            local_admin_configured=not self.auth.setup_required(),
            auth_provider_count=auth_provider_count,
            tenant_name=tenant_name,
            recommended_flow=(
                "Create a local administrator first, then optionally enable LDAP or OAuth2 sign-in."
                if self.auth.setup_required()
                else "Platform initialized. You can now configure LDAP or OAuth2 sign-in providers."
            ),
        )

    def complete_initial_setup(self, payload: SetupLocalAdminRequest) -> SetupStatusResponse:
        self.bootstrap = self.auth.create_initial_admin(
            username=payload.username,
            password=payload.password,
            tenant_name=payload.tenant_name,
        )
        if payload.tenant_name:
            active_workspace = self.active_workspace()
            if active_workspace is not None:
                self.control_storage.update_workspace(
                    active_workspace.id,
                    name=payload.tenant_name,
                    updated_at=utc_now_iso(),
                )
                self._bind_workspace(active_workspace.id)
        self.audit(
            actor_username=payload.username,
            action="initial_setup_completed",
            status="success",
            target_type="setup",
            target_id=payload.username,
            summary="Initial application administrator created.",
            details={"tenant_name": payload.tenant_name or ""},
        )
        if self.storage.load_latest_snapshot() is None and os.getenv("EIP_DISABLE_AUTOSCAN") != "1":
            self.run_scan()
        return self.setup_status()

    def list_auth_providers(self) -> AuthProviderListResponse:
        return self.federated_auth.list_providers()

    def list_admin_users(self) -> AdminUserListResponse:
        return self.auth.list_admin_users()

    def update_admin_user_roles(self, username: str, roles: list[str]) -> AdminUserSummary:
        return self.auth.update_admin_roles(username, roles)

    def list_public_auth_providers(self) -> PublicAuthProviderListResponse:
        return self.federated_auth.list_public_providers()

    def create_auth_provider(self, payload: AuthProviderCreateRequest) -> AuthProviderDetailResponse:
        return self.federated_auth.create_provider(payload)

    def update_auth_provider(
        self,
        provider_id: str,
        payload: AuthProviderUpdateRequest,
    ) -> AuthProviderDetailResponse | None:
        return self.federated_auth.update_provider(provider_id, payload)

    def delete_auth_provider(self, provider_id: str) -> bool:
        return self.federated_auth.delete_provider(provider_id)

    def connector_inventory(self) -> ConnectorRuntimeResponse:
        return discover_connector_inventory(
            latest_status_by_id=self._connector_runtime_statuses,
        )

    def list_access_reviews(self) -> AccessReviewCampaignListResponse:
        return AccessReviewCampaignListResponse(
            generated_at=utc_now_iso(),
            campaigns=self.storage.list_access_review_campaigns(),
        )

    def get_access_review(self, campaign_id: str) -> AccessReviewCampaignDetailResponse | None:
        detail = self.storage.get_access_review_campaign(campaign_id)
        if detail is None:
            return None
        return enrich_campaign_detail(self.engine, detail)

    def create_access_review(
        self,
        payload: AccessReviewCampaignCreateRequest,
        *,
        actor_username: str,
    ) -> AccessReviewCampaignDetailResponse:
        access_rows = self.storage.list_materialized_access_index(self.engine.snapshot.generated_at)
        if not access_rows:
            access_rows = self.engine.materialized_access_index()
            self.storage.save_materialized_access_index(self.engine.snapshot.generated_at, access_rows)
        candidates = build_review_candidates(self.engine, access_rows, payload)
        if not candidates:
            raise ValueError(
                "No access paths matched the current review filters. Lower the risk threshold or include non-privileged access."
            )
        campaign_id = self.storage.create_access_review_campaign(
            payload,
            snapshot_generated_at=self.engine.snapshot.generated_at,
            created_by=actor_username,
            timestamp=utc_now_iso(),
            items=candidates,
        )
        detail = self.get_access_review(campaign_id)
        if detail is None:
            raise RuntimeError("Access review campaign could not be reloaded after creation.")
        return detail

    def update_access_review_decision(
        self,
        campaign_id: str,
        item_id: str,
        payload: AccessReviewDecisionRequest,
    ) -> AccessReviewCampaignDetailResponse | None:
        detail = self.storage.update_access_review_decision(
            campaign_id,
            item_id,
            payload,
            timestamp=utc_now_iso(),
        )
        if detail is None:
            return None
        return enrich_campaign_detail(self.engine, detail)

    def access_review_remediation(
        self,
        campaign_id: str,
        item_id: str,
    ) -> AccessReviewRemediationPlan:
        detail = self.get_access_review(campaign_id)
        if detail is None:
            raise KeyError(f"Unknown access review campaign: {campaign_id}")
        item = next((candidate for candidate in detail.items if candidate.id == item_id), None)
        if item is None:
            raise KeyError(f"Unknown access review item: {item_id}")
        return remediation_plan_for_item(self.engine, campaign_id, item)

    def list_report_schedules(self) -> ReportScheduleListResponse:
        return ReportScheduleListResponse(
            generated_at=utc_now_iso(),
            schedules=self.report_schedule_service.list_schedules(),
        )

    def get_report_schedule(self, schedule_id: str) -> ReportScheduleDetailResponse | None:
        return self.report_schedule_service.get_schedule(schedule_id)

    def create_report_schedule(
        self,
        payload: ReportScheduleCreateRequest,
        *,
        actor_username: str,
    ) -> ReportScheduleDetailResponse:
        return self.report_schedule_service.create_schedule(payload, actor_username=actor_username)

    def update_report_schedule(
        self,
        schedule_id: str,
        payload: ReportScheduleUpdateRequest,
    ) -> ReportScheduleDetailResponse | None:
        return self.report_schedule_service.update_schedule(schedule_id, payload)

    def delete_report_schedule(self, schedule_id: str) -> bool:
        return self.report_schedule_service.delete_schedule(schedule_id)

    def run_report_schedule(
        self,
        schedule_id: str,
        *,
        trigger: str = "manual",
    ) -> tuple[ReportScheduleDetailResponse, ReportScheduleRunRecord]:
        return self.report_schedule_service.run_schedule(schedule_id, trigger=trigger)

    def platform_posture(self) -> PlatformPostureResponse:
        snapshot = self.storage.load_latest_snapshot()
        snapshot_generated_at = snapshot.generated_at if snapshot else self.engine.snapshot.generated_at
        access_index_stats = self.storage.materialized_access_index_stats(snapshot_generated_at)
        exposure_index_stats = self.storage.resource_exposure_index_stats(snapshot_generated_at)
        principal_summary_stats = self.storage.principal_access_summary_stats(snapshot_generated_at)
        raw_snapshot_stats = self.storage.raw_snapshot_stats()
        background_worker = self.background_worker_status()
        storage_summary = (
            f"{self.storage.backend_name} source of truth is active."
            if self.storage.backend_name == "PostgreSQL"
            else "SQLite fallback is active for local or test deployments."
        )
        components: list[PlatformComponentStatus] = [
            PlatformComponentStatus(
                id="storage",
                name=self.storage.backend_name,
                category="core-data",
                state="active",
                configured=True,
                connected=True,
                summary=storage_summary,
                details=[
                    f"Schema version: {self.storage.schema_version()}",
                    f"Snapshot retention: {settings.snapshot_retention}",
                    f"Latest snapshot: {snapshot_generated_at}",
                    (
                        f"Default scan root: {settings.default_scan_root}"
                        if settings.default_scan_root
                        else "Default scan root: automatic discovery"
                    ),
                ],
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="raw-snapshot-store",
                name="Raw snapshot store",
                category="pipeline",
                state="active" if raw_snapshot_stats["row_count"] else "configured",
                configured=True,
                connected=raw_snapshot_stats["row_count"] > 0,
                summary=(
                    "Collector output is retained before normalization."
                    if raw_snapshot_stats["row_count"]
                    else "Raw snapshot retention is enabled and will populate on the next scan."
                ),
                details=[
                    f"Rows: {raw_snapshot_stats['row_count']}",
                    (
                        f"Latest capture: {raw_snapshot_stats['latest_captured_at']}"
                        if raw_snapshot_stats["latest_captured_at"]
                        else "Latest capture: none yet"
                    ),
                ],
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="materialized-access-index",
                name="Materialized access index",
                category="core-data",
                state=(
                    "active"
                    if access_index_stats["row_count"]
                    else "configured"
                    if settings.enable_materialized_access_index
                    else "disabled"
                ),
                configured=settings.enable_materialized_access_index,
                connected=access_index_stats["row_count"] > 0,
                summary=(
                    "Effective access index is precomputed and ready."
                    if access_index_stats["row_count"]
                    else "Materialized access index is enabled and will be populated on the next scan."
                    if settings.enable_materialized_access_index
                    else "Materialized access index is intentionally disabled for this deployment."
                ),
                details=[
                    f"Rows: {access_index_stats['row_count']}",
                    f"Principals indexed: {access_index_stats['principal_count']}",
                    f"Resources indexed: {access_index_stats['resource_count']}",
                ],
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="incremental-index-refresh",
                name="Incremental index refresh",
                category="pipeline",
                state=(
                    "active"
                    if self._last_index_refresh_summary is not None
                    and self._last_index_refresh_summary.mode in {"delta", "carry_forward", "existing"}
                    else "configured"
                    if self._last_index_refresh_summary is not None
                    else "optional"
                ),
                configured=True,
                connected=self._last_index_refresh_summary is not None,
                summary=(
                    "Index refresh reuses or recomputes only the impacted graph surfaces."
                    if self._last_index_refresh_summary is not None
                    and self._last_index_refresh_summary.mode in {"delta", "carry_forward", "existing"}
                    else "The latest snapshot required a full index rebuild."
                    if self._last_index_refresh_summary is not None
                    else "The next successful scan will publish an index refresh summary."
                ),
                details=(
                    [
                        f"Mode: {self._last_index_refresh_summary.mode}",
                        f"Reused access rows: {self._last_index_refresh_summary.reused_access_rows}",
                        f"Recomputed access rows: {self._last_index_refresh_summary.recomputed_access_rows}",
                        f"Impacted principals: {self._last_index_refresh_summary.impacted_principals}",
                        f"Impacted resources: {self._last_index_refresh_summary.impacted_resources}",
                    ]
                    + [
                        f"Fallback: {reason}"
                        for reason in self._last_index_refresh_summary.fallback_reasons[:3]
                    ]
                    if self._last_index_refresh_summary is not None
                    else ["No refresh summary captured yet."]
                ),
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="resource-exposure-index",
                name="Resource exposure index",
                category="analytics",
                state="active" if exposure_index_stats["row_count"] else "configured",
                configured=True,
                connected=exposure_index_stats["row_count"] > 0,
                summary=(
                    "Resource exposure summaries are materialized and ready for fast hotspot views."
                    if exposure_index_stats["row_count"]
                    else "Resource exposure summaries will populate on the next index refresh."
                ),
                details=[
                    f"Rows: {exposure_index_stats['row_count']}",
                    f"Max exposure score: {exposure_index_stats['max_exposure_score']}",
                ],
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="principal-access-summary",
                name="Principal access summary",
                category="analytics",
                state="active" if principal_summary_stats["row_count"] else "configured",
                configured=True,
                connected=principal_summary_stats["row_count"] > 0,
                summary=(
                    "Principal access summaries are materialized for fast operator overviews."
                    if principal_summary_stats["row_count"]
                    else "Principal access summaries will populate on the next index refresh."
                ),
                details=[
                    f"Rows: {principal_summary_stats['row_count']}",
                    f"Max exposure score: {principal_summary_stats['max_exposure_score']}",
                ],
                documentation_url="https://www.postgresql.org/download/",
            ),
            PlatformComponentStatus(
                id="background-runtime",
                name="Background runtime",
                category="operations",
                state=(
                    "active"
                    if background_worker["state"] == "local"
                    else "configured"
                    if background_worker["state"] in {"remote", "standby"}
                    else "error"
                ),
                configured=self._background_jobs_capable or background_worker["state"] == "remote",
                connected=background_worker["state"] in {"local", "remote", "standby"},
                summary=(
                    "This node currently owns background scheduling and recurring enterprise refreshes."
                    if background_worker["state"] == "local"
                    else "A remote worker currently owns background scheduling for this deployment."
                    if background_worker["state"] == "remote"
                    else "Another background-capable node currently owns the scheduling lease."
                    if background_worker["state"] == "standby"
                    else "No active background worker heartbeat is visible right now."
                ),
                details=[
                    f"Runtime role: {self.runtime_role}",
                    f"Worker state: {background_worker['state']}",
                    *(
                        [f"Worker host: {background_worker['host']}"]
                        if background_worker["host"]
                        else []
                    ),
                    *(
                        [f"Last seen: {background_worker['updated_at']}"]
                        if background_worker["updated_at"]
                        else []
                    ),
                ],
                documentation_url=TEMPORAL_DOCS,
            ),
            self.platform_services.search.status(),
            self.platform_services.graph.status(),
            self.platform_services.cache.status(),
            self.platform_services.analytics.status(),
            configured_component_status(
                component_id="kafka",
                name="Apache Kafka",
                category="eventing",
                configured=bool(settings.kafka_bootstrap_servers),
                summary_enabled="Kafka bootstrap servers are configured for asynchronous ingest.",
                summary_disabled="Kafka is optional and not configured in this deployment.",
                documentation_url=KAFKA_DOCS,
                details=[f"Bootstrap servers: {settings.kafka_bootstrap_servers}"] if settings.kafka_bootstrap_servers else [
                    "Use Kafka when collector fan-out or event volume outgrows direct in-process ingestion."
                ],
            ),
            configured_component_status(
                component_id="temporal",
                name="Temporal",
                category="workflow",
                configured=bool(settings.temporal_address),
                summary_enabled="Temporal endpoint is configured for durable workflows.",
                summary_disabled="Temporal is optional and not configured in this deployment.",
                documentation_url=TEMPORAL_DOCS,
                details=[f"Address: {settings.temporal_address}"] if settings.temporal_address else [
                    "Use Temporal to orchestrate sync, retry and remediation workflows."
                ],
            ),
            configured_component_status(
                component_id="langfuse",
                name="Langfuse",
                category="ai-observability",
                configured=bool(settings.langfuse_base_url),
                summary_enabled="Langfuse base URL is configured for AI tracing.",
                summary_disabled="Langfuse is optional and not configured in this deployment.",
                documentation_url=LANGFUSE_DOCS,
                details=[f"Base URL: {settings.langfuse_base_url}"] if settings.langfuse_base_url else [
                    "Use Langfuse only for AI explanation and copiloting, never for entitlement calculation."
                ],
            ),
        ]
        return PlatformPostureResponse(
            generated_at=utc_now_iso(),
            storage_backend=self.storage.backend_name,
            search_backend=self.platform_services.search.name,
            cache_backend=self.platform_services.cache.name,
            analytics_backend=self.platform_services.analytics.name,
            materialized_access_index=settings.enable_materialized_access_index,
            components=components,
        )

    def search(self, query: str) -> list[SearchResult]:
        return self.search_service.search(query)

    def overview(self):
        return self.entitlement_service.overview()

    def catalog(self):
        return self.entitlement_service.catalog()

    def get_resource_access(
        self,
        resource_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> ResourceAccessResponse:
        return self.entitlement_service.resource_exposure(resource_id, limit=limit, offset=offset)

    def get_principal_access(
        self,
        principal_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> PrincipalAccessResponse:
        return self.entitlement_service.principal_access(principal_id, limit=limit, offset=offset)

    def entity_detail(self, entity_id: str) -> EntityDetailResponse:
        detail = self.engine.entity_detail(entity_id)
        steps = [*detail.inbound, *detail.outbound]
        direct_grants = [
            step
            for step in steps
            if step.permissions and not step.inherits
        ]
        inherited_grants = [
            step
            for step in steps
            if step.permissions and step.inherits
        ]
        group_paths = [
            step
            for step in steps
            if step.edge_kind in {"member_of", "nested_group"}
        ]
        role_paths = [
            step
            for step in steps
            if step.edge_kind in {"assigned_role", "role_grant"}
        ]
        risk_findings = self._entity_risk_findings(entity_id)
        recent_changes = self.change_service.list_changes(limit=6).changes

        overview_metrics: list[MetricCard] = []
        principal_access_records = []
        resource_access_records = []
        admin_rights = []

        if detail.perspective == "principal":
            closure_rows = self.storage.list_principal_group_closure(
                self.engine.snapshot.generated_at,
                entity_id,
                limit=8,
            )
            if closure_rows:
                detail.group_closure = [
                    GroupClosureRecord(
                        group=self.engine.summary(row["group_id"]),
                        depth=int(row["depth"]),
                        shortest_parent=self.engine.summary(row["shortest_parent_id"]),
                        path_count=int(row["path_count"]),
                    )
                    for row in closure_rows
                ]
            else:
                detail.group_closure = self.engine.principal_group_closure(entity_id)[:8]
            principal_access = self.get_principal_access(entity_id, limit=8)
            principal_access_records = principal_access.records[:8]
            admin_rights = [
                record
                for record in principal_access.records
                if self.engine.is_privileged_permissions(record.permissions)
            ][:6]
            overview_metrics = [
                MetricCard(
                    title="Access Overview",
                    value=str(principal_access.total_resources),
                    delta=f"{principal_access.privileged_resources} privileged resource(s)",
                    tone="warn" if principal_access.privileged_resources else "good",
                    description="Effective resources currently reachable by this identity after graph compilation.",
                ),
                MetricCard(
                    title="Admin Rights",
                    value=str(len(admin_rights)),
                    delta=f"{len(group_paths)} group path(s)",
                    tone="critical" if admin_rights else "neutral",
                    description="Privileged effective access surfaced for fast investigation and review.",
                ),
                MetricCard(
                    title="Group Paths",
                    value=str(len(group_paths)),
                    delta=f"{len(role_paths)} role route(s)",
                    tone="neutral",
                    description="Membership and nested-group routes currently contributing to access spread.",
                ),
                MetricCard(
                    title="High Risk Access",
                    value=str(len(risk_findings)),
                    delta=f"{len(direct_grants)} direct grant(s)",
                    tone="warn" if risk_findings else "good",
                    description="Risk findings linked to this identity in the current materialized snapshot.",
                ),
            ]
        elif detail.perspective == "resource":
            hierarchy_rows = self.storage.list_resource_hierarchy_closure(
                self.engine.snapshot.generated_at,
                entity_id,
                limit=8,
            )
            if hierarchy_rows:
                detail.resource_hierarchy = [
                    ResourceHierarchyRecord(
                        ancestor=self.engine.summary(row["ancestor_resource_id"]),
                        depth=int(row["depth"]),
                        inherits_acl=bool(row["inherits_acl"]),
                    )
                    for row in hierarchy_rows
                ]
            else:
                detail.resource_hierarchy = self.engine.resource_hierarchy_closure(entity_id)[:8]
            resource_access = self.get_resource_access(entity_id, limit=8)
            resource_access_records = resource_access.records[:8]
            privileged_records = [
                record
                for record in resource_access.records
                if self.engine.is_privileged_permissions(record.permissions)
            ]
            overview_metrics = [
                MetricCard(
                    title="Who Has Access",
                    value=str(resource_access.total_principals),
                    delta=f"{resource_access.privileged_principal_count} privileged principal(s)",
                    tone="critical" if resource_access.privileged_principal_count else "neutral",
                    description="Principals currently reaching this resource through effective entitlement paths.",
                ),
                MetricCard(
                    title="Direct Grants",
                    value=str(len(direct_grants)),
                    delta=f"{len(inherited_grants)} inherited grant(s)",
                    tone="neutral",
                    description="Observed direct versus inherited relationships attached to this resource.",
                ),
                MetricCard(
                    title="Risk Findings",
                    value=str(len(risk_findings)),
                    delta=f"{len(privileged_records)} privileged principal(s)",
                    tone="warn" if risk_findings else "good",
                    description="Risk findings highlighting broad, privileged or indirect exposure on this resource.",
                ),
                MetricCard(
                    title="Group Paths",
                    value=str(len(group_paths)),
                    delta=f"{len(role_paths)} role route(s)",
                    tone="neutral",
                    description="Indirect membership or role routes contributing to current exposure.",
                ),
            ]
        else:
            overview_metrics = [
                MetricCard(
                    title="Neighborhood",
                    value=str(len(detail.inbound) + len(detail.outbound)),
                    delta=f"{len(group_paths)} group path(s)",
                    tone="neutral",
                    description="Connected relationships observed around this supporting entity.",
                ),
                MetricCard(
                    title="Direct Grants",
                    value=str(len(direct_grants)),
                    delta=f"{len(inherited_grants)} inherited grant(s)",
                    tone="neutral",
                    description="Direct or inherited permission-bearing edges connected to this entity.",
                ),
                MetricCard(
                    title="Risk Findings",
                    value=str(len(risk_findings)),
                    delta=f"{len(role_paths)} role route(s)",
                    tone="warn" if risk_findings else "good",
                    description="Current findings that reference this entity in the access graph.",
                ),
            ]

        return detail.model_copy(
            update={
                "overview_metrics": overview_metrics,
                "direct_grants": direct_grants,
                "inherited_grants": inherited_grants,
                "group_paths": group_paths,
                "role_paths": role_paths,
                "principal_access": principal_access_records,
                "resource_access": resource_access_records,
                "admin_rights": admin_rights,
                "risk_findings": risk_findings,
                "recent_changes": recent_changes,
            }
        )

    def explain(self, principal_id: str, resource_id: str):
        return self.explain_service.explain(principal_id, resource_id)

    def what_if(self, edge_id: str, focus_resource_id: str | None = None):
        return self.whatif_service.simulate(edge_id, focus_resource_id)

    def graph_subgraph(
        self,
        entity_id: str,
        depth: int = 1,
        *,
        max_nodes: int = 160,
        max_edges: int = 320,
    ):
        return self.graph_service.subgraph(
            entity_id,
            depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    def risk_findings(self, limit: int = 25):
        return self.risk_service.list_findings(limit)

    def recent_changes(self, limit: int = 20):
        return self.change_service.list_changes(limit)

    def audit_events(self, limit: int = 50) -> AuditEventsResponse:
        return self.audit_service.list_events(limit)

    def _entity_risk_findings(self, entity_id: str) -> list[RiskFinding]:
        findings = self.risk_service.list_findings(limit=50).findings
        return [
            finding
            for finding in findings
            if (finding.resource and finding.resource.id == entity_id)
            or (finding.principal and finding.principal.id == entity_id)
        ][:6]

    def operational_flow(self) -> OperationalFlowResponse:
        return self.operational_flow_service.status()

    def audit(
        self,
        *,
        actor_username: str,
        action: str,
        status: str,
        target_type: str,
        summary: str,
        target_id: str | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        self.storage.record_audit_event(
            actor_username=actor_username,
            action=action,
            status=status,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            details=details,
            occurred_at=utc_now_iso(),
        )

    def list_imported_sources(self) -> ImportedSourceListResponse:
        sources = self.storage.list_imported_sources()
        return ImportedSourceListResponse(
            generated_at=utc_now_iso(),
            total_sources=len(sources),
            sources=sources,
        )

    def create_imported_source(self, bundle: ImportedSourceBundle) -> ImportedSourceDetailResponse:
        detail = self.storage.create_imported_source(bundle, timestamp=utc_now_iso())
        self._refresh_runtime_snapshot()
        return detail

    def update_imported_source(
        self, source_id: str, payload: ImportedSourceUpdateRequest
    ) -> ImportedSourceDetailResponse | None:
        detail = self.storage.update_imported_source(source_id, payload, timestamp=utc_now_iso())
        if detail is not None:
            self._refresh_runtime_snapshot()
        return detail

    def delete_imported_source(self, source_id: str) -> bool:
        deleted = self.storage.delete_imported_source(source_id)
        if deleted:
            self._refresh_runtime_snapshot()
        return deleted

    def list_targets(self) -> list[ScanTarget]:
        return self.storage.list_targets()

    def create_target(self, payload: ScanTargetCreateRequest) -> ScanTarget:
        return self.storage.create_target(payload, timestamp=utc_now_iso())

    def update_target(self, target_id: str, payload: ScanTargetUpdateRequest) -> ScanTarget | None:
        return self.storage.update_target(target_id, payload, timestamp=utc_now_iso())

    def scan_runs(self) -> ScanRunsResponse:
        recent = self.storage.list_scan_runs(limit=10)
        return ScanRunsResponse(
            active=self._scan_in_progress,
            latest=recent[0] if recent else self._latest_scan,
            recent=recent,
        )

    def run_scan(self, target_ids: list[str] | None = None) -> ScanRunRecord:
        with self._scan_lock:
            self._scan_in_progress = True
            started_at = utc_now_iso()
            started = perf_counter()
            try:
                targets = self._resolve_targets(target_ids)
                for target in targets:
                    self.storage.touch_target_status(
                        target.id,
                        status="running",
                        timestamp=started_at,
                    )

                payload = self._collect_snapshot_payload(targets)
                snapshot = payload["snapshot"]
                finished_at = utc_now_iso()
                self.storage.save_raw_snapshot(
                    snapshot.generated_at,
                    "normalization-pipeline",
                    dict(payload["raw_batch"]),
                    captured_at=finished_at,
                )
                self.storage.save_snapshot(snapshot)
                for target in targets:
                    self.storage.replace_scan_cache(
                        target.id,
                        list(payload.get("cache_records_by_target", {}).get(target.id, [])),
                        timestamp=finished_at,
                    )
                self.engine = AccessGraphEngine(snapshot)
                self._refresh_enterprise_indexes(snapshot)

                run = ScanRunRecord(
                    id=f"scan_{uuid.uuid4().hex[:12]}",
                    started_at=started_at,
                    finished_at=finished_at,
                    status="warning" if payload["warning_count"] else "healthy",
                    duration_ms=round((perf_counter() - started) * 1000, 4),
                    target_ids=[target.id for target in targets],
                    resource_count=len(
                        [entity for entity in snapshot.entities if entity.kind == "resource"]
                    ),
                    principal_count=len(
                        [entity for entity in snapshot.entities if entity.kind in {"user", "service_account", "group"}]
                    ),
                    relationship_count=len(snapshot.relationships),
                    warning_count=int(payload["warning_count"]),
                    notes=list(payload["notes"]),
                )
                self.storage.record_scan_run(
                    run,
                    privileged_path_count=int(payload["privileged_path_count"]),
                    broad_access_count=int(payload["broad_access_count"]),
                )
                self.platform_services.analytics.record_scan(
                    {
                        "recorded_at": finished_at,
                        "run_id": run.id,
                        "tenant": snapshot.tenant,
                        "snapshot_generated_at": snapshot.generated_at,
                        "status": run.status,
                        "duration_ms": float(run.duration_ms or 0.0),
                        "target_count": len(run.target_ids),
                        "resource_count": run.resource_count,
                        "principal_count": run.principal_count,
                        "relationship_count": run.relationship_count,
                        "warning_count": run.warning_count,
                        "privileged_path_count": int(payload["privileged_path_count"]),
                        "broad_access_count": int(payload["broad_access_count"]),
                    }
                )
                self.audit(
                    actor_username="system",
                    action="scan_completed",
                    status=run.status,
                    target_type="scan",
                    target_id=run.id,
                    summary=(
                        f"Collection finished for {len(run.target_ids)} target(s) with "
                        f"{run.resource_count} resources and {run.relationship_count} relationships."
                    ),
                    details={
                        "snapshot_generated_at": snapshot.generated_at,
                        "target_count": str(len(run.target_ids)),
                        "warning_count": str(run.warning_count),
                    },
                )
                self._latest_scan = run
                self.bootstrap = self.auth.bootstrap_status()

                finished_status = "warning" if payload["warning_count"] else "healthy"
                for target in targets:
                    target_warnings = [
                        note for note in payload["notes"] if target.path.lower() in note.lower()
                    ]
                    self.storage.touch_target_status(
                        target.id,
                        status="warning" if target_warnings else finished_status,
                        timestamp=finished_at,
                        error=target_warnings[0] if target_warnings else None,
                    )
                return run
            except Exception as exc:
                self.audit(
                    actor_username="system",
                    action="scan_completed",
                    status="failed",
                    target_type="scan",
                    summary="Collection failed before a new snapshot could be persisted.",
                    details={"error": str(exc)},
                )
                failed_at = utc_now_iso()
                for target in self._resolve_targets(target_ids, strict=False):
                    self.storage.touch_target_status(
                        target.id,
                        status="failed",
                        timestamp=failed_at,
                        error=str(exc),
                    )
                raise
            finally:
                self._scan_in_progress = False

    def benchmark(self, iterations: int = 1, target_ids: list[str] | None = None) -> BenchmarkResponse:
        targets = self._resolve_targets(target_ids)
        timings: dict[str, list[float]] = {
            "collection": [],
            "graph_compile": [],
            "overview": [],
            "catalog": [],
        }
        latest_snapshot = None
        cache_notes: list[str] = []
        for _ in range(max(1, iterations)):
            collect_started = perf_counter()
            payload = self._collect_snapshot_payload(targets)
            timings["collection"].append((perf_counter() - collect_started) * 1000)
            cache_hits = int(payload.get("cache_hits", 0))
            cache_misses = int(payload.get("cache_misses", 0))
            if cache_hits or cache_misses:
                cache_notes = [
                    f"Incremental collection cache: {cache_hits} hit(s), {cache_misses} miss(es)."
                ]

            latest_snapshot = payload["snapshot"]
            compile_started = perf_counter()
            engine = AccessGraphEngine(latest_snapshot)
            timings["graph_compile"].append((perf_counter() - compile_started) * 1000)

            overview_started = perf_counter()
            engine.get_overview()
            timings["overview"].append((perf_counter() - overview_started) * 1000)

            catalog_started = perf_counter()
            engine.get_catalog()
            timings["catalog"].append((perf_counter() - catalog_started) * 1000)

        if latest_snapshot is None:
            raise RuntimeError("Benchmark did not produce a snapshot.")
        return BenchmarkResponse(
            generated_at=utc_now_iso(),
            snapshot=BenchmarkSnapshot(
                mode="real",
                scope=f"{len(targets)} monitored target(s)",
                target_count=len(targets),
                entity_count=len(latest_snapshot.entities),
                relationship_count=len(latest_snapshot.relationships),
            ),
            metrics=[
                _metric_from_values("collection", timings["collection"]),
                _metric_from_values("graph_compile", timings["graph_compile"]),
                _metric_from_values("overview", timings["overview"]),
                _metric_from_values("catalog", timings["catalog"]),
            ],
            notes=[
                "Benchmarks were executed against the live filesystem collector with the current monitored targets.",
                "The collection phase includes ACL enumeration and snapshot construction.",
                *cache_notes,
            ],
        )

    def _resolve_targets(self, target_ids: list[str] | None, *, strict: bool = True) -> list[ScanTarget]:
        if target_ids:
            selected = [self.storage.get_target(target_id) for target_id in target_ids]
            targets = [target for target in selected if target is not None]
        else:
            targets = [target for target in self.storage.list_targets() if target.enabled]

        if strict and not targets:
            raise ValueError("No scan targets are configured or enabled.")
        return targets

    def _ensure_default_targets(self) -> None:
        if self.storage.list_targets():
            return

        discovered = self._discover_default_targets()
        for payload in discovered:
            self.storage.create_target(payload, timestamp=utc_now_iso())

    def _discover_default_targets(self) -> list[ScanTargetCreateRequest]:
        if settings.default_scan_root:
            configured_root = Path(settings.default_scan_root).expanduser()
            if not configured_root.exists():
                if settings.environment == "production":
                    raise RuntimeError(
                        f"EIP_DEFAULT_SCAN_ROOT does not exist or is not mounted: {configured_root}"
                    )
            else:
                return [
                    ScanTargetCreateRequest(
                        name="Configured scan root",
                        path=str(configured_root),
                        platform="windows" if os.name == "nt" else "linux",
                        recursive=True,
                        max_depth=4,
                        max_entries=2000,
                        notes="Explicit scan scope configured through EIP_DEFAULT_SCAN_ROOT.",
                    )
                ]

        defaults: list[ScanTargetCreateRequest] = []
        if os.name == "nt":
            for drive in self._discover_windows_drives()[:2]:
                defaults.append(
                    ScanTargetCreateRequest(
                        name=f"{drive} inventory",
                        path=drive,
                        platform="windows",
                        recursive=True,
                        max_depth=1,
                        max_entries=250,
                        notes="Automatic shallow inventory of the local drive root.",
                    )
                )
            home = Path.home()
            if home.exists():
                defaults.append(
                    ScanTargetCreateRequest(
                        name="Current admin profile",
                        path=str(home),
                        platform="windows",
                        recursive=True,
                        max_depth=2,
                        max_entries=350,
                        notes="Deeper live scan of the current administrator profile.",
                    )
                )
        else:
            defaults.append(
                ScanTargetCreateRequest(
                    name="Root filesystem inventory",
                    path="/",
                    platform="linux",
                    recursive=True,
                    max_depth=1,
                    max_entries=250,
                    notes="Automatic shallow inventory of the root filesystem.",
                )
            )
            home = Path.home()
            if home.exists():
                defaults.append(
                    ScanTargetCreateRequest(
                        name="Current admin profile",
                        path=str(home),
                        platform="linux",
                        recursive=True,
                        max_depth=2,
                        max_entries=350,
                        notes="Deeper live scan of the current administrator profile.",
                    )
                )

        workspace = self.project_root
        if workspace.exists():
            defaults.append(
                ScanTargetCreateRequest(
                    name="Workspace monitoring",
                    path=str(workspace),
                    platform="windows" if os.name == "nt" else "linux",
                    recursive=True,
                    max_depth=4,
                    max_entries=600,
                    notes="Focused monitor for the working area hosting the application.",
                )
            )
        return defaults

    def _discover_windows_drives(self) -> list[str]:
        if hasattr(os, "listdrives"):
            return [drive for drive in os.listdrives() if drive]

        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            return []
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-Command",
                "Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )  # nosec B603
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    def _empty_engine_snapshot(self):
        payload = self._collect_snapshot_payload([])
        return payload["snapshot"]

    def _refresh_enterprise_indexes(self, snapshot) -> None:
        self._last_index_refresh_summary = self.index_refresh_service.ensure_indexes(snapshot, self.engine)
        self.platform_services.search.index_snapshot(snapshot)
        self.platform_services.graph.index_snapshot(snapshot)

    def _collect_snapshot_payload(self, targets: list[ScanTarget]) -> dict[str, object]:
        cache_by_target = self.storage.load_scan_caches([target.id for target in targets])
        base_payload = collect_real_snapshot(
            targets,
            historical_metrics=self.storage.list_scan_run_metrics(limit=20),
            cache_by_target=cache_by_target,
        )
        bundles, statuses = collect_configured_bundles()
        imported_bundles = self._imported_source_bundles()
        batch = RawCollectionBatch(
            generated_at=base_payload["snapshot"].generated_at,
            targets=targets,
            base_snapshot=base_payload["snapshot"],
            configured_bundles=bundles,
            imported_bundles=imported_bundles,
            raw_collector_payload=dict(base_payload.get("raw_payload", {})),
            notes=list(base_payload["notes"]),
            warning_count=int(base_payload["warning_count"]),
            privileged_path_count=int(base_payload["privileged_path_count"]),
            broad_access_count=int(base_payload["broad_access_count"]),
            cache_hits=int(base_payload.get("cache_hits", 0)),
            cache_misses=int(base_payload.get("cache_misses", 0)),
            cache_records_by_target=dict(base_payload.get("cache_records_by_target", {})),
        )
        merged_snapshot = self.normalization_pipeline.normalize(
            batch,
            tenant_name=self.storage.get_setting("tenant_name"),
        )
        self._connector_runtime_statuses = statuses
        base_payload["snapshot"] = merged_snapshot
        base_payload["warning_count"] = int(base_payload["warning_count"]) + sum(
            len(bundle.notes) for bundle in (bundles + imported_bundles)
        )
        base_payload["notes"] = list(base_payload["notes"]) + [
            note for bundle in (bundles + imported_bundles) for note in bundle.notes
        ]
        base_payload["raw_batch"] = self.normalization_pipeline.serialize_raw_batch(batch)
        return base_payload

    def _merge_entities(self, base_entities, bundles):
        merged = {entity.id: entity for entity in base_entities}
        for bundle in bundles:
            for entity in bundle.entities:
                existing = merged.get(entity.id)
                if existing is None or (len(entity.tags) + entity.risk_score) > (len(existing.tags) + existing.risk_score):
                    merged[entity.id] = entity
        return list(merged.values())

    def _merge_relationships(self, base_relationships, bundles):
        merged = {relationship.id: relationship for relationship in base_relationships}
        for bundle in bundles:
            for relationship in bundle.relationships:
                merged[relationship.id] = relationship
        return list(merged.values())

    def _merge_connectors(self, base_connectors, bundles):
        merged = {f"{connector.name}:{connector.source}": connector for connector in base_connectors}
        for bundle in bundles:
            for connector in bundle.connectors:
                merged[f"{connector.name}:{connector.source}"] = connector
        return list(merged.values())

    def _merge_insights(self, base_insights, bundles):
        merged = {insight.title: insight for insight in base_insights}
        for bundle in bundles:
            for insight in bundle.insights:
                merged[insight.title] = insight
        return list(merged.values())[:10]

    def _imported_source_bundles(self):
        bundles = []
        for imported_source in self.storage.list_imported_sources():
            if not imported_source.enabled:
                continue
            detail = self.storage.get_imported_source(imported_source.id)
            if detail is None:
                continue
            bundles.append(self._collection_bundle_from_imported_source(detail))
        return bundles

    def _collection_bundle_from_imported_source(
        self, detail: ImportedSourceDetailResponse
    ):
        bundle = detail.bundle
        summary = detail.summary
        entity_id_map = {
            entity.id: f"{summary.id}__{entity.id}"
            for entity in bundle.entities
        }
        entities = [
            entity.model_copy(
                update={
                    "id": entity_id_map[entity.id],
                    "tags": [
                        *entity.tags,
                        "imported-source",
                        summary.id,
                        summary.source.lower().replace(" ", "-"),
                    ],
                }
            )
            for entity in bundle.entities
        ]
        relationships = [
            relationship.model_copy(
                update={
                    "id": f"{summary.id}__{relationship.id}",
                    "source": entity_id_map.get(relationship.source, relationship.source),
                    "target": entity_id_map.get(relationship.target, relationship.target),
                    "metadata": {
                        **relationship.metadata,
                        "origin": "imported-source",
                        "imported_source_id": summary.id,
                    },
                }
            )
            for relationship in bundle.relationships
        ]
        connectors = bundle.connectors or [
            ConnectorStatus(
                name=f"Imported source: {summary.name}",
                source=summary.source,
                status="healthy",
                latency_ms=1,
                last_sync=summary.updated_at,
                coverage=f"{summary.entity_count} entities, {summary.relationship_count} relationships",
            )
        ]
        insights = bundle.insights or [
            InsightNote(
                title=f"Imported source active: {summary.name}",
                body=(
                    f"{summary.entity_count} entities and {summary.relationship_count} relationships "
                    f"were merged from the imported {summary.source} bundle."
                ),
                tone="neutral",
            )
        ]
        from app.integration_collectors import CollectionBundle

        return CollectionBundle(
            entities=entities,
            relationships=relationships,
            connectors=connectors,
            insights=insights,
            notes=[],
            runtime_status=None,
        )

    def _start_scheduler(self) -> None:
        if not self._scheduler_enabled or self._scheduler_thread is not None:
            return

        def _loop() -> None:
            while not self._scheduler_stop.wait(self._scheduler_interval_seconds):
                if not self._background_leader or self._scan_in_progress:
                    continue
                try:
                    self.run_scan()
                except Exception:
                    logger.exception("Scheduled scan failed.")
                    continue

        self._scheduler_thread = threading.Thread(target=_loop, name="eip-scheduler", daemon=True)
        self._scheduler_thread.start()

    def _start_report_scheduler(self) -> None:
        if not self._report_scheduler_enabled or self._report_scheduler_thread is not None:
            return

        def _loop() -> None:
            while not self._report_scheduler_stop.wait(self._report_scheduler_interval_seconds):
                if not self._background_leader:
                    continue
                try:
                    results = self.report_schedule_service.run_due_schedules()
                    for detail, run in results:
                        self.audit(
                            actor_username="system",
                            action="report_schedule_run",
                            status=run.status,
                            target_type="report_schedule",
                            target_id=detail.summary.id,
                            summary=f"Scheduled report '{detail.summary.name}' executed.",
                            details={
                                "trigger": run.trigger,
                                "channels": ", ".join(run.delivered_channels),
                                "message": run.message or "",
                            },
                        )
                except Exception:
                    logger.exception("Scheduled report execution failed.")
                    continue

        self._report_scheduler_thread = threading.Thread(
            target=_loop,
            name="eip-report-scheduler",
            daemon=True,
        )
        self._report_scheduler_thread.start()

    def _refresh_runtime_snapshot(self) -> None:
        try:
            enabled_targets = [target.id for target in self.storage.list_targets() if target.enabled]
            if enabled_targets:
                self.run_scan(enabled_targets)
            else:
                payload = self._collect_snapshot_payload([])
                snapshot = payload["snapshot"]
                timestamp = utc_now_iso()
                self.storage.save_raw_snapshot(
                    snapshot.generated_at,
                    "normalization-pipeline",
                    dict(payload["raw_batch"]),
                    captured_at=timestamp,
                )
                self.storage.save_snapshot(snapshot)
                self.engine = AccessGraphEngine(snapshot)
                self._refresh_enterprise_indexes(snapshot)
        except Exception:
            logger.exception("Runtime snapshot refresh failed.")
            return


def _metric_from_values(name: str, values: list[float]) -> BenchmarkMetric:
    ordered = sorted(values)
    average = sum(ordered) / len(ordered)
    median = ordered[len(ordered) // 2]
    p95_index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * 0.95)))
    return BenchmarkMetric(
        name=name,
        iterations=len(ordered),
        average_ms=round(average, 4),
        median_ms=round(median, 4),
        p95_ms=round(ordered[p95_index], 4),
        max_ms=round(ordered[-1], 4),
    )


runtime = RuntimeState(Path(__file__).resolve().parents[2])
