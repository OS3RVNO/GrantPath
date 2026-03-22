from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.branding import PRODUCT_REPORT_BODY, PRODUCT_REPORT_SUBJECT_PREFIX

NodeKind = Literal["user", "service_account", "group", "role", "resource"]
EntityPerspective = Literal["principal", "resource", "supporting"]
RelationshipKind = Literal[
    "member_of",
    "nested_group",
    "delegated_access",
    "assigned_role",
    "direct_acl",
    "deny_acl",
    "role_grant",
    "contains",
]
Tone = Literal["neutral", "good", "warn", "critical"]
ConnectorStatusValue = Literal["healthy", "warning", "degraded"]
CollectionMode = Literal["snapshot", "incremental", "hybrid"]
ImplementationStatus = Literal["live", "partial", "blueprint"]
PlatformComponentState = Literal["active", "configured", "optional", "disabled", "error"]
TargetPlatform = Literal["auto", "windows", "linux"]
TargetKind = Literal["filesystem"]
TargetConnectionMode = Literal["local", "ssh"]
TargetStatusValue = Literal["idle", "running", "healthy", "warning", "failed"]
FreshnessStatusValue = Literal["fresh", "stale", "empty"]
BenchmarkMode = Literal["real", "synthetic"]
ConnectorRuntimeStatusValue = Literal["configured", "disabled", "needs_config", "healthy", "warning", "failed"]
ConnectorSupportTier = Literal["supported", "pilot", "experimental", "blueprint"]
ConnectorValidationLevel = Literal["runtime_verified", "config_validated", "doc_aligned", "planned"]
ConnectorRecommendedUsage = Literal["production", "pilot", "lab", "design_only"]
AuthProviderKind = Literal["ldap", "oidc"]
AuthProviderPreset = Literal["custom", "microsoft", "google", "github", "okta", "keycloak"]
AppRole = Literal[
    "viewer",
    "investigator",
    "admin",
    "connector_admin",
    "auditor",
    "executive_read_only",
]
AccessReviewDecisionValue = Literal["pending", "keep", "revoke", "needs_follow_up"]
AccessReviewCampaignStatus = Literal["open", "completed"]
ReportFormat = Literal["html", "pdf", "xlsx"]
ReportScheduleCadence = Literal["hourly", "daily", "weekly", "monthly"]
ReportScheduleKind = Literal["access_review", "review_campaign"]
ReportDeliverySecurityMode = Literal["none", "starttls", "ssl"]
ReportScheduleRunTrigger = Literal["manual", "scheduled"]
ReportScheduleRunStatus = Literal["success", "failed", "partial", "running"]
ReportScheduleState = Literal["never", "success", "failed", "partial", "running"]
JobLaneState = Literal["idle", "running", "scheduled", "disabled", "attention"]
RuntimeRole = Literal["all", "api", "worker"]
BackgroundWorkerState = Literal["local", "remote", "standby", "missing"]
IndexRefreshMode = Literal["full", "delta", "carry_forward", "existing"]


class Entity(BaseModel):
    id: str
    name: str
    kind: NodeKind
    source: str
    environment: Literal["on-prem", "cloud", "hybrid"]
    description: str
    criticality: int = 1
    risk_score: int = 0
    tags: list[str] = Field(default_factory=list)
    owner: str | None = None


class Relationship(BaseModel):
    id: str
    kind: RelationshipKind
    source: str
    target: str
    label: str
    rationale: str
    permissions: list[str] = Field(default_factory=list)
    inherits: bool = False
    temporary: bool = False
    expires_at: str | None = None
    removable: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class MetricCard(BaseModel):
    title: str
    value: str
    delta: str
    tone: Tone = "neutral"
    description: str


class ConnectorStatus(BaseModel):
    name: str
    source: str
    status: ConnectorStatusValue
    latency_ms: int
    last_sync: str
    coverage: str


class DocumentationLink(BaseModel):
    title: str
    url: str


class ConnectorBlueprint(BaseModel):
    id: str
    vendor: str
    surface: str
    collection_mode: CollectionMode
    implementation_status: ImplementationStatus = "blueprint"
    priority: int
    freshness: str
    configuration_env: list[str] = Field(default_factory=list)
    tenant_requirements: list[str] = Field(default_factory=list)
    recommended_endpoints: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    supported_entities: list[str] = Field(default_factory=list)
    algorithm_notes: list[str] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    official_limitations: list[str] = Field(default_factory=list)
    current_runtime_coverage: list[str] = Field(default_factory=list)
    documentation_links: list[DocumentationLink] = Field(default_factory=list)


class ConnectorBlueprintResponse(BaseModel):
    generated_at: str
    blueprints: list[ConnectorBlueprint]


class PlatformComponentStatus(BaseModel):
    id: str
    name: str
    category: str
    state: PlatformComponentState
    configured: bool
    connected: bool
    summary: str
    details: list[str] = Field(default_factory=list)
    documentation_url: str | None = None


class PlatformPostureResponse(BaseModel):
    generated_at: str
    storage_backend: str
    search_backend: str
    cache_backend: str
    analytics_backend: str
    materialized_access_index: bool
    components: list[PlatformComponentStatus] = Field(default_factory=list)


class InsightNote(BaseModel):
    title: str
    body: str
    tone: Tone = "neutral"


class HistoricalPoint(BaseModel):
    day: str
    privileged_paths: int
    dormant_entitlements: int
    change_requests: int


class Snapshot(BaseModel):
    tenant: str
    generated_at: str
    entities: list[Entity]
    relationships: list[Relationship]
    connectors: list[ConnectorStatus]
    history: list[HistoricalPoint]
    insights: list[InsightNote]


class EntitySummary(BaseModel):
    id: str
    name: str
    kind: NodeKind
    source: str
    environment: Literal["on-prem", "cloud", "hybrid"]


class SearchResult(BaseModel):
    entity: EntitySummary
    headline: str
    keywords: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    label: str
    kind: NodeKind
    source: str
    tags: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    kind: RelationshipKind
    highlighted: bool = False


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class PathStep(BaseModel):
    edge_id: str
    edge_kind: RelationshipKind
    source: EntitySummary
    target: EntitySummary
    label: str
    rationale: str
    permissions: list[str] = Field(default_factory=list)
    inherits: bool = False
    temporary: bool = False
    removable: bool = False


class AccessPath(BaseModel):
    permissions: list[str]
    access_mode: str
    risk_score: int
    narrative: str
    steps: list[PathStep]


class ResourceAccessRecord(BaseModel):
    principal: EntitySummary
    permissions: list[str]
    path_count: int
    path_complexity: int = 0
    access_mode: str
    risk_score: int
    why: str


class PrincipalResourceRecord(BaseModel):
    resource: EntitySummary
    permissions: list[str]
    path_count: int
    path_complexity: int = 0
    access_mode: str
    risk_score: int
    why: str


class Hotspot(BaseModel):
    resource: EntitySummary
    privileged_principal_count: int
    delegated_path_count: int
    exposure_score: int
    headline: str


class ResourceExposureSummaryRecord(BaseModel):
    resource: EntitySummary
    principal_count: int
    privileged_principal_count: int
    max_risk_score: int
    average_path_complexity: int
    exposure_score: int


class PrincipalAccessSummaryRecord(BaseModel):
    principal: EntitySummary
    resource_count: int
    privileged_resource_count: int
    max_risk_score: int
    average_path_complexity: int
    exposure_score: int


class ExposureAnalyticsResponse(BaseModel):
    generated_at: str
    resource_summaries: list[ResourceExposureSummaryRecord] = Field(default_factory=list)
    principal_summaries: list[PrincipalAccessSummaryRecord] = Field(default_factory=list)


class QueryPerformanceMetric(BaseModel):
    operation: str
    calls: int
    average_ms: float
    p95_ms: float
    max_ms: float
    error_count: int = 0
    last_seen_at: str | None = None


class QueryPerformanceResponse(BaseModel):
    generated_at: str
    metrics: list[QueryPerformanceMetric] = Field(default_factory=list)


class ScenarioChoice(BaseModel):
    edge_id: str
    label: str
    reason: str
    focus_resource_id: str | None = None
    estimated_impacted_principals: int


class OverviewResponse(BaseModel):
    tenant: str
    generated_at: str
    metrics: list[MetricCard]
    connectors: list[ConnectorStatus]
    hotspots: list[Hotspot]
    scenarios: list[ScenarioChoice]
    history: list[HistoricalPoint]
    insights: list[InsightNote]
    default_principal_id: str | None = None
    default_resource_id: str | None = None
    default_scenario_edge_id: str | None = None


class CatalogResponse(BaseModel):
    principals: list[EntitySummary]
    resources: list[EntitySummary]
    scenarios: list[ScenarioChoice]


class ResourceAccessResponse(BaseModel):
    resource: EntitySummary
    total_principals: int
    privileged_principal_count: int
    offset: int = 0
    limit: int
    returned_count: int
    has_more: bool = False
    records: list[ResourceAccessRecord]


class PrincipalAccessResponse(BaseModel):
    principal: EntitySummary
    total_resources: int
    privileged_resources: int
    offset: int = 0
    limit: int
    returned_count: int
    has_more: bool = False
    records: list[PrincipalResourceRecord]


class ExplainRequest(BaseModel):
    principal_id: str
    resource_id: str


class ExplainResponse(BaseModel):
    principal: EntitySummary
    resource: EntitySummary
    permissions: list[str]
    path_count: int
    risk_score: int
    paths: list[AccessPath]
    graph: GraphPayload


class EntityDetailResponse(BaseModel):
    entity: Entity
    perspective: EntityPerspective = "supporting"
    inbound: list[PathStep]
    outbound: list[PathStep]
    overview_metrics: list[MetricCard] = Field(default_factory=list)
    direct_grants: list[PathStep] = Field(default_factory=list)
    inherited_grants: list[PathStep] = Field(default_factory=list)
    group_paths: list[PathStep] = Field(default_factory=list)
    group_closure: list["GroupClosureRecord"] = Field(default_factory=list)
    resource_hierarchy: list["ResourceHierarchyRecord"] = Field(default_factory=list)
    role_paths: list[PathStep] = Field(default_factory=list)
    principal_access: list[PrincipalResourceRecord] = Field(default_factory=list)
    resource_access: list[ResourceAccessRecord] = Field(default_factory=list)
    admin_rights: list[PrincipalResourceRecord] = Field(default_factory=list)
    risk_findings: list["RiskFinding"] = Field(default_factory=list)
    recent_changes: list["ChangeRecord"] = Field(default_factory=list)


class GroupClosureRecord(BaseModel):
    group: EntitySummary
    depth: int
    shortest_parent: EntitySummary
    path_count: int


class ResourceHierarchyRecord(BaseModel):
    ancestor: EntitySummary
    depth: int
    inherits_acl: bool = True


class GraphSubgraphResponse(BaseModel):
    focus: EntitySummary
    depth: int = 1
    truncated: bool = False
    node_limit: int = 0
    edge_limit: int = 0
    graph: GraphPayload
    inbound_count: int = 0
    outbound_count: int = 0


class WhatIfRequest(BaseModel):
    edge_id: str
    focus_resource_id: str | None = None


class WhatIfDiffItem(BaseModel):
    principal: EntitySummary
    resource: EntitySummary
    removed_permissions: list[str]
    access_mode_before: str


class ResourceImpact(BaseModel):
    resource: EntitySummary
    removed_principal_count: int
    removed_permission_count: int
    severity: Tone


class FlowNode(BaseModel):
    id: str
    label: str
    kind: str
    x: float
    y: float


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str


class FlowPayload(BaseModel):
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class WhatIfResponse(BaseModel):
    edge: Relationship
    narrative: str
    impacted_principals: int
    impacted_resources: int
    removed_paths: int
    privileged_paths_removed: int
    recomputed_principals: int
    recomputed_resources: int
    recomputed_pairs: int
    diff: list[WhatIfDiffItem]
    blast_radius: list[ResourceImpact]
    focus_resource_id: str | None = None
    focus_before: list[ResourceAccessRecord]
    focus_after: list[ResourceAccessRecord]
    flow: FlowPayload


class BenchmarkMetric(BaseModel):
    name: str
    iterations: int
    average_ms: float
    median_ms: float
    p95_ms: float
    max_ms: float


class BenchmarkSnapshot(BaseModel):
    mode: BenchmarkMode
    scope: str
    target_count: int
    entity_count: int
    relationship_count: int
    scale: int | None = None


class BenchmarkResponse(BaseModel):
    generated_at: str
    snapshot: BenchmarkSnapshot
    metrics: list[BenchmarkMetric]
    notes: list[str] = Field(default_factory=list)


class RiskFinding(BaseModel):
    id: str
    category: str
    severity: Tone
    headline: str
    detail: str
    recommended_action: str
    affected_principal_count: int = 0
    affected_resource_count: int = 0
    resource: EntitySummary | None = None
    principal: EntitySummary | None = None
    source: str


class RiskFindingsResponse(BaseModel):
    generated_at: str
    total_findings: int
    findings: list[RiskFinding] = Field(default_factory=list)


class ChangeRecord(BaseModel):
    id: str
    occurred_at: str
    change_type: str
    status: str
    summary: str
    previous_snapshot_at: str | None = None
    current_snapshot_at: str | None = None
    target_count: int = 0
    resource_count: int = 0
    relationship_count: int = 0
    warning_count: int = 0
    privileged_path_count: int = 0
    broad_access_count: int = 0
    added_access_count: int = 0
    removed_access_count: int = 0
    changed_access_count: int = 0
    affected_principal_count: int = 0
    affected_resource_count: int = 0


class ChangesResponse(BaseModel):
    generated_at: str
    changes: list[ChangeRecord] = Field(default_factory=list)


class AuditEventRecord(BaseModel):
    id: str
    occurred_at: str
    actor_username: str
    action: str
    status: str
    target_type: str
    target_id: str | None = None
    summary: str
    details: dict[str, str] = Field(default_factory=dict)


class AuditEventsResponse(BaseModel):
    generated_at: str
    events: list[AuditEventRecord] = Field(default_factory=list)


class OperationalFlowStep(BaseModel):
    id: str
    title: str
    status: Literal["ready", "action_required", "in_progress"]
    detail: str
    recommended_action: str


class OperationalFlowResponse(BaseModel):
    generated_at: str
    overall_status: Literal["ready", "action_required", "in_progress"]
    completion_percent: int
    steps: list[OperationalFlowStep] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class MvpReadinessItem(BaseModel):
    id: str
    title: str
    status: Literal["ready", "action_required", "in_progress"]
    required: bool = True
    summary: str
    why_it_matters: str
    recommended_action: str
    workspace: str
    section: str | None = None


class MvpReadinessAction(BaseModel):
    id: str
    label: str
    detail: str
    workspace: str
    section: str | None = None


class MvpReadinessFreshness(BaseModel):
    status: Literal["fresh", "aging", "stale", "missing"]
    summary: str
    snapshot_generated_at: str | None = None
    latest_successful_scan_at: str | None = None
    age_minutes: int | None = None


class MvpReadinessResponse(BaseModel):
    generated_at: str
    overall_status: Literal["ready", "action_required", "in_progress"]
    completion_percent: int
    primary_scope: str
    checklist: list[MvpReadinessItem] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    actions: list[MvpReadinessAction] = Field(default_factory=list)
    freshness: MvpReadinessFreshness


class FeatureInventoryItem(BaseModel):
    id: str
    title: str
    status: Literal["present", "partial", "missing"]
    required_for_mvp: bool = True
    summary: str
    gap: str
    recommended_action: str
    workspace: str
    section: str | None = None


class FeatureInventoryCategory(BaseModel):
    id: str
    title: str
    summary: str
    items: list[FeatureInventoryItem] = Field(default_factory=list)
    present_count: int = 0
    partial_count: int = 0
    missing_count: int = 0


class FeatureInventoryResponse(BaseModel):
    generated_at: str
    primary_scope: str
    overall_status: Literal["ready", "action_required", "in_progress"]
    categories: list[FeatureInventoryCategory] = Field(default_factory=list)
    present_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    required_missing: list[str] = Field(default_factory=list)


class BootstrapStatusResponse(BaseModel):
    setup_required: bool = False
    admin_username: str
    must_change_password: bool
    password_generated: bool
    password_file: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)
    provider_id: str | None = Field(default=None, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class SessionResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    auth_source: str | None = None
    roles: list[AppRole] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    must_change_password: bool = False
    csrf_token: str | None = None
    mfa_required: bool = False
    mfa_enabled: bool = False
    mfa_challenge_token: str | None = None
    setup_required: bool = False
    bootstrap: BootstrapStatusResponse | None = None
    active_workspace_id: str | None = None
    active_workspace_name: str | None = None


class SetupStatusResponse(BaseModel):
    setup_required: bool
    local_admin_configured: bool
    auth_provider_count: int
    tenant_name: str
    recommended_flow: str


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    environment: Literal["on-prem", "cloud", "hybrid"] = "on-prem"
    active: bool = False
    created_at: str
    updated_at: str
    storage_path: str


class WorkspaceListResponse(BaseModel):
    generated_at: str
    active_workspace_id: str | None = None
    workspaces: list[WorkspaceSummary] = Field(default_factory=list)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    environment: Literal["on-prem", "cloud", "hybrid"] = "on-prem"


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    environment: Literal["on-prem", "cloud", "hybrid"] | None = None


class AdminUserSummary(BaseModel):
    username: str
    display_name: str | None = None
    auth_source: str
    roles: list[AppRole] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    mfa_enabled: bool = False
    created_at: str
    must_change_password: bool = False


class AdminUserListResponse(BaseModel):
    generated_at: str
    users: list[AdminUserSummary] = Field(default_factory=list)


class AdminUserRolesUpdateRequest(BaseModel):
    roles: list[AppRole] = Field(default_factory=list, min_length=1)


class SetupLocalAdminRequest(BaseModel):
    tenant_name: str | None = Field(default=None, max_length=160)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=512)


class MfaStatusResponse(BaseModel):
    available: bool = False
    enabled: bool = False
    pending_setup: bool = False
    method: Literal["totp"] = "totp"
    issuer: str
    provider_hint: str


class MfaSetupResponse(BaseModel):
    method: Literal["totp"] = "totp"
    issuer: str
    account_name: str
    manual_entry_key: str
    provisioning_uri: str


class MfaChallengeVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=6, max_length=12)


class MfaSetupConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class MfaDisableRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    code: str = Field(min_length=6, max_length=12)


class ScanTarget(BaseModel):
    id: str
    kind: TargetKind = "filesystem"
    name: str
    path: str
    platform: TargetPlatform = "auto"
    connection_mode: TargetConnectionMode = "local"
    host: str | None = None
    port: int = Field(default=22, ge=1, le=65535)
    username: str | None = None
    secret_env: str | None = None
    key_path: str | None = None
    recursive: bool = True
    max_depth: int = Field(default=2, ge=0, le=32)
    max_entries: int = Field(default=500, ge=25, le=10000)
    include_hidden: bool = False
    enabled: bool = True
    notes: str | None = None
    last_scan_at: str | None = None
    last_status: TargetStatusValue = "idle"
    last_error: str | None = None
    created_at: str
    updated_at: str


class ScanTargetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=512)
    platform: TargetPlatform = "auto"
    connection_mode: TargetConnectionMode = "local"
    host: str | None = Field(default=None, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    secret_env: str | None = Field(default=None, max_length=255)
    key_path: str | None = Field(default=None, max_length=512)
    recursive: bool = True
    max_depth: int = Field(default=2, ge=0, le=32)
    max_entries: int = Field(default=500, ge=25, le=10000)
    include_hidden: bool = False
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=500)


class ScanTargetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    path: str | None = Field(default=None, min_length=1, max_length=512)
    platform: TargetPlatform | None = None
    connection_mode: TargetConnectionMode | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    secret_env: str | None = Field(default=None, max_length=255)
    key_path: str | None = Field(default=None, max_length=512)
    recursive: bool | None = None
    max_depth: int | None = Field(default=None, ge=0, le=32)
    max_entries: int | None = Field(default=None, ge=25, le=10000)
    include_hidden: bool | None = None
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class ScanRunRecord(BaseModel):
    id: str
    started_at: str
    finished_at: str | None = None
    status: TargetStatusValue
    duration_ms: float | None = None
    target_ids: list[str] = Field(default_factory=list)
    resource_count: int = 0
    principal_count: int = 0
    relationship_count: int = 0
    warning_count: int = 0
    notes: list[str] = Field(default_factory=list)


class ScanRunsResponse(BaseModel):
    active: bool
    latest: ScanRunRecord | None = None
    recent: list[ScanRunRecord] = Field(default_factory=list)


class IndexRefreshSummary(BaseModel):
    generated_at: str
    previous_snapshot_at: str | None = None
    mode: IndexRefreshMode = "full"
    changed_entities: int = 0
    changed_relationships: int = 0
    impacted_principals: int = 0
    impacted_resources: int = 0
    reused_access_rows: int = 0
    recomputed_access_rows: int = 0
    total_access_rows: int = 0
    carried_forward_group_closure: bool = False
    recomputed_group_closure_principals: int = 0
    carried_forward_resource_hierarchy: bool = False
    recomputed_resource_hierarchy_resources: int = 0
    fallback_reasons: list[str] = Field(default_factory=list)


class RuntimeStatusResponse(BaseModel):
    host: str
    platform: str
    runtime_role: RuntimeRole = "all"
    admin_username: str
    bootstrap: BootstrapStatusResponse
    target_count: int
    active_target_count: int
    latest_snapshot_at: str | None = None
    latest_scan_status: TargetStatusValue | None = None
    last_successful_scan_at: str | None = None
    last_successful_scan_duration_ms: float | None = None
    raw_batch_count: int = 0
    materialized_access_rows: int = 0
    freshness_status: FreshnessStatusValue = "empty"
    scan_in_progress: bool = False
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int | None = None
    report_scheduler_enabled: bool = False
    report_scheduler_interval_seconds: int | None = None
    background_jobs_capable: bool = False
    background_jobs_active: bool = False
    background_worker_state: BackgroundWorkerState = "missing"
    background_worker_host: str | None = None
    background_worker_last_seen_at: str | None = None
    index_refresh: IndexRefreshSummary | None = None


class JobWorkerLane(BaseModel):
    id: str
    name: str
    kind: Literal["scan", "report_delivery"]
    state: JobLaneState
    scheduler_enabled: bool
    execution_mode: BackgroundWorkerState = "missing"
    worker_host: str | None = None
    worker_role: RuntimeRole | None = None
    worker_last_seen_at: str | None = None
    queue_depth: int = 0
    active_work_items: int = 0
    last_completed_at: str | None = None
    next_due_at: str | None = None
    last_status: str | None = None
    summary: str


class JobRecentActivity(BaseModel):
    id: str
    lane_id: str
    label: str
    status: str
    started_at: str
    finished_at: str | None = None
    summary: str


class JobCenterResponse(BaseModel):
    generated_at: str
    overall_status: Literal["healthy", "watch", "attention"]
    lanes: list[JobWorkerLane] = Field(default_factory=list)
    recent_jobs: list[JobRecentActivity] = Field(default_factory=list)


class AuthProviderConfig(BaseModel):
    kind: AuthProviderKind
    preset: AuthProviderPreset = "custom"
    description: str | None = Field(default=None, max_length=400)
    issuer_url: str | None = Field(default=None, max_length=400)
    discovery_url: str | None = Field(default=None, max_length=400)
    client_id: str | None = Field(default=None, max_length=255)
    client_secret_env: str | None = Field(default=None, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_emails: list[str] = Field(default_factory=list)
    username_attribute: str | None = Field(default=None, max_length=120)
    email_attribute: str | None = Field(default=None, max_length=120)
    ldap_server_uri: str | None = Field(default=None, max_length=400)
    ldap_base_dn: str | None = Field(default=None, max_length=400)
    ldap_bind_dn: str | None = Field(default=None, max_length=400)
    ldap_bind_password_env: str | None = Field(default=None, max_length=255)
    ldap_user_search_filter: str | None = Field(default=None, max_length=400)
    allowed_groups: list[str] = Field(default_factory=list)
    start_tls: bool = False


class AuthProviderSummary(BaseModel):
    id: str
    name: str
    kind: AuthProviderKind
    preset: AuthProviderPreset = "custom"
    enabled: bool = True
    description: str | None = None
    accepts_password: bool = False
    uses_redirect: bool = False
    created_at: str
    updated_at: str


class AuthProviderDetailResponse(BaseModel):
    summary: AuthProviderSummary
    config: AuthProviderConfig


class AuthProviderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    config: AuthProviderConfig


class AuthProviderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = None
    config: AuthProviderConfig | None = None


class AuthProviderListResponse(BaseModel):
    generated_at: str
    providers: list[AuthProviderSummary] = Field(default_factory=list)


class PublicAuthProviderSummary(BaseModel):
    id: str
    name: str
    kind: AuthProviderKind
    preset: AuthProviderPreset = "custom"
    sign_in_label: str
    accepts_password: bool = False
    uses_redirect: bool = False
    login_path: str | None = None


class PublicAuthProviderListResponse(BaseModel):
    generated_at: str
    providers: list[PublicAuthProviderSummary] = Field(default_factory=list)


class ConnectorRuntimeStatus(BaseModel):
    id: str
    name: str
    source: str
    surface: str
    implementation_status: ImplementationStatus = "blueprint"
    configured: bool
    enabled: bool
    status: ConnectorRuntimeStatusValue
    collection_mode: CollectionMode
    description: str
    required_env: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    supported_entities: list[str] = Field(default_factory=list)
    tenant_requirements: list[str] = Field(default_factory=list)
    official_limitations: list[str] = Field(default_factory=list)
    current_runtime_coverage: list[str] = Field(default_factory=list)
    documentation_links: list[DocumentationLink] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    last_sync: str | None = None
    entity_count: int = 0
    relationship_count: int = 0


class ConnectorRuntimeResponse(BaseModel):
    generated_at: str
    connectors: list[ConnectorRuntimeStatus]


class ConnectorSupportMatrixEntry(BaseModel):
    id: str
    name: str
    category: str
    vendor: str
    support_tier: ConnectorSupportTier
    validation_level: ConnectorValidationLevel
    recommended_usage: ConnectorRecommendedUsage
    runtime_configured: bool
    runtime_enabled: bool
    implementation_status: ImplementationStatus
    summary: str
    evidence: list[str] = Field(default_factory=list)
    current_gaps: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    documentation_links: list[DocumentationLink] = Field(default_factory=list)


class ConnectorSupportMatrixResponse(BaseModel):
    generated_at: str
    primary_scope: str
    entries: list[ConnectorSupportMatrixEntry] = Field(default_factory=list)
    counts_by_tier: dict[str, int] = Field(default_factory=dict)
    counts_by_validation: dict[str, int] = Field(default_factory=dict)


class ImportedSourceBundle(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=160)
    environment: Literal["on-prem", "cloud", "hybrid"] = "hybrid"
    description: str | None = Field(default=None, max_length=500)
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    connectors: list[ConnectorStatus] = Field(default_factory=list)
    insights: list[InsightNote] = Field(default_factory=list)


class ImportedSourceSummary(BaseModel):
    id: str
    name: str
    source: str
    environment: Literal["on-prem", "cloud", "hybrid"]
    description: str | None = None
    enabled: bool = True
    entity_count: int = 0
    relationship_count: int = 0
    connector_count: int = 0
    created_at: str
    updated_at: str


class ImportedSourceDetailResponse(BaseModel):
    summary: ImportedSourceSummary
    bundle: ImportedSourceBundle


class ImportedSourceUpdateRequest(BaseModel):
    enabled: bool | None = None


class ImportedSourceListResponse(BaseModel):
    generated_at: str
    total_sources: int
    sources: list[ImportedSourceSummary] = Field(default_factory=list)


class IdentityClusterSummary(BaseModel):
    id: str
    display_name: str
    entity_count: int
    source_count: int
    sources: list[str] = Field(default_factory=list)
    match_keys: list[str] = Field(default_factory=list)
    combined_resource_count: int = 0
    max_risk_score: int = 0


class IdentityClusterMember(BaseModel):
    entity: EntitySummary
    confidence: int
    evidence: list[str] = Field(default_factory=list)
    match_keys: list[str] = Field(default_factory=list)


class IdentityClusterResource(BaseModel):
    resource: EntitySummary
    permissions: list[str] = Field(default_factory=list)
    contributing_identities: list[EntitySummary] = Field(default_factory=list)
    max_risk_score: int = 0
    path_count: int = 0


class IdentityClustersResponse(BaseModel):
    generated_at: str
    total_clusters: int
    clusters: list[IdentityClusterSummary] = Field(default_factory=list)


class IdentityClusterDetailResponse(BaseModel):
    cluster: IdentityClusterSummary
    members: list[IdentityClusterMember] = Field(default_factory=list)
    top_resources: list[IdentityClusterResource] = Field(default_factory=list)


class AccessReviewRemediationStep(BaseModel):
    order: int
    title: str
    detail: str
    impact: str


class AccessReviewRemediationPlan(BaseModel):
    item_id: str
    campaign_id: str
    summary: str
    suggested_edge_id: str | None = None
    suggested_edge_label: str | None = None
    impacted_principals: int = 0
    impacted_resources: int = 0
    privileged_paths_removed: int = 0
    steps: list[AccessReviewRemediationStep] = Field(default_factory=list)


class AccessReviewItem(BaseModel):
    id: str
    campaign_id: str
    principal_id: str
    resource_id: str
    principal: EntitySummary
    resource: EntitySummary
    permissions: list[str] = Field(default_factory=list)
    path_count: int
    access_mode: str
    risk_score: int
    why: str
    decision: AccessReviewDecisionValue = "pending"
    decision_note: str | None = None
    reviewed_at: str | None = None
    suggested_edge_id: str | None = None
    suggested_edge_label: str | None = None
    suggested_remediation: str | None = None


class AccessReviewCampaignSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    snapshot_generated_at: str
    status: AccessReviewCampaignStatus = "open"
    created_by: str
    created_at: str
    updated_at: str
    total_items: int = 0
    pending_items: int = 0
    keep_count: int = 0
    revoke_count: int = 0
    follow_up_count: int = 0
    min_risk_score: int = 0
    privileged_only: bool = False


class AccessReviewCampaignDetailResponse(BaseModel):
    summary: AccessReviewCampaignSummary
    items: list[AccessReviewItem] = Field(default_factory=list)


class AccessReviewCampaignListResponse(BaseModel):
    generated_at: str
    campaigns: list[AccessReviewCampaignSummary] = Field(default_factory=list)


class AccessReviewCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=400)
    min_risk_score: int = Field(default=70, ge=0, le=100)
    privileged_only: bool = True
    max_items: int = Field(default=25, ge=1, le=200)


class AccessReviewDecisionRequest(BaseModel):
    decision: AccessReviewDecisionValue
    decision_note: str | None = Field(default=None, max_length=500)


class ReportEmailDeliverySettings(BaseModel):
    enabled: bool = False
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    security: ReportDeliverySecurityMode = "starttls"
    username: str | None = Field(default=None, max_length=255)
    password_env: str | None = Field(default=None, max_length=255)
    from_address: str | None = Field(default=None, max_length=255)
    reply_to: str | None = Field(default=None, max_length=255)
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject_template: str = Field(default=f"{PRODUCT_REPORT_SUBJECT_PREFIX}: {{schedule_name}}", max_length=255)
    message_body: str = Field(
        default=PRODUCT_REPORT_BODY,
        max_length=4000,
    )
    attach_formats: list[ReportFormat] = Field(default_factory=list)
    include_html_body: bool = True


class ReportWebhookDeliverySettings(BaseModel):
    enabled: bool = False
    url: str | None = Field(default=None, max_length=500)
    secret_env: str | None = Field(default=None, max_length=255)
    secret_header: str = Field(default="X-EIP-Webhook-Secret", max_length=120)
    include_summary: bool = True


class ReportArchiveDeliverySettings(BaseModel):
    enabled: bool = True
    directory: str | None = Field(default=None, max_length=500)
    filename_prefix: str | None = Field(default=None, max_length=120)


class ReportDeliverySettings(BaseModel):
    email: ReportEmailDeliverySettings = Field(default_factory=ReportEmailDeliverySettings)
    webhook: ReportWebhookDeliverySettings = Field(default_factory=ReportWebhookDeliverySettings)
    archive: ReportArchiveDeliverySettings = Field(default_factory=ReportArchiveDeliverySettings)


class ReportScheduleConfig(BaseModel):
    kind: ReportScheduleKind = "access_review"
    locale: Literal["en", "it", "de", "fr", "es"] = "en"
    formats: list[ReportFormat] = Field(default_factory=lambda: ["pdf"])
    principal_id: str | None = Field(default=None, max_length=255)
    resource_id: str | None = Field(default=None, max_length=255)
    scenario_edge_id: str | None = Field(default=None, max_length=255)
    focus_resource_id: str | None = Field(default=None, max_length=255)
    campaign_id: str | None = Field(default=None, max_length=255)
    title_override: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_scope(self) -> "ReportScheduleConfig":
        if not self.formats:
            raise ValueError("At least one report format must be selected.")
        if self.kind == "access_review":
            if not self.principal_id or not self.resource_id or not self.scenario_edge_id:
                raise ValueError(
                    "Access review schedules require principal, resource and scenario selections."
                )
        if self.kind == "review_campaign" and not self.campaign_id:
            raise ValueError("Review campaign schedules require a campaign selection.")
        return self


class ReportScheduleSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    enabled: bool = True
    cadence: ReportScheduleCadence = "daily"
    timezone: str = "UTC"
    hour: int = 8
    minute: int = 0
    day_of_week: int | None = None
    day_of_month: int | None = None
    report_kind: ReportScheduleKind
    locale: Literal["en", "it", "de", "fr", "es"] = "en"
    formats: list[ReportFormat] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    created_by: str
    created_at: str
    updated_at: str
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_status: ReportScheduleState = "never"
    last_message: str | None = None


class ReportScheduleRunRecord(BaseModel):
    id: str
    schedule_id: str
    started_at: str
    finished_at: str | None = None
    trigger: ReportScheduleRunTrigger = "manual"
    status: ReportScheduleRunStatus = "running"
    delivered_channels: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    message: str | None = None


class ReportScheduleDetailResponse(BaseModel):
    summary: ReportScheduleSummary
    config: ReportScheduleConfig
    delivery: ReportDeliverySettings
    recent_runs: list[ReportScheduleRunRecord] = Field(default_factory=list)


class ReportScheduleListResponse(BaseModel):
    generated_at: str
    schedules: list[ReportScheduleSummary] = Field(default_factory=list)


class ReportScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool = True
    cadence: ReportScheduleCadence = "daily"
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    config: ReportScheduleConfig
    delivery: ReportDeliverySettings = Field(default_factory=ReportDeliverySettings)

    @model_validator(mode="after")
    def validate_timing(self) -> "ReportScheduleCreateRequest":
        if self.cadence == "weekly" and self.day_of_week is None:
            raise ValueError("Weekly schedules require a day of week.")
        if self.cadence == "monthly" and self.day_of_month is None:
            raise ValueError("Monthly schedules require a day of month.")
        return self


class ReportScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
    cadence: ReportScheduleCadence | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    config: ReportScheduleConfig | None = None
    delivery: ReportDeliverySettings | None = None


EntityDetailResponse.model_rebuild()
