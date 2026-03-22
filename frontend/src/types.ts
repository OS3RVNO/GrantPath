export type EntityKind = 'user' | 'service_account' | 'group' | 'role' | 'resource'
export type EntityPerspective = 'principal' | 'resource' | 'supporting'
export type Tone = 'neutral' | 'good' | 'warn' | 'critical'
export type ConnectorStatus = 'healthy' | 'warning' | 'degraded'
export type ConnectorRuntimeState =
  | 'configured'
  | 'disabled'
  | 'needs_config'
  | 'healthy'
  | 'warning'
  | 'failed'
export type ConnectorImplementationStatus = 'live' | 'partial' | 'blueprint'
export type PlatformComponentState = 'active' | 'configured' | 'optional' | 'disabled' | 'error'
export type RuntimeRole = 'all' | 'api' | 'worker'
export type BackgroundWorkerState = 'local' | 'remote' | 'standby' | 'missing'
export type IndexRefreshMode = 'full' | 'delta' | 'carry_forward' | 'existing'

export interface EntitySummary {
  id: string
  name: string
  kind: EntityKind
  source: string
  environment: 'on-prem' | 'cloud' | 'hybrid'
}

export interface Entity extends EntitySummary {
  description: string
  criticality: number
  risk_score: number
  tags: string[]
  owner?: string | null
}

export interface Relationship {
  id: string
  kind: string
  source: string
  target: string
  label: string
  rationale: string
  permissions: string[]
  inherits: boolean
  temporary: boolean
  expires_at?: string | null
  removable: boolean
  metadata: Record<string, string>
}

export interface MetricCard {
  title: string
  value: string
  delta: string
  tone: Tone
  description: string
}

export interface Connector {
  name: string
  source: string
  status: ConnectorStatus
  latency_ms: number
  last_sync: string
  coverage: string
}

export interface DocumentationLink {
  title: string
  url: string
}

export interface ConnectorBlueprint {
  id: string
  vendor: string
  surface: string
  collection_mode: 'snapshot' | 'incremental' | 'hybrid'
  implementation_status: ConnectorImplementationStatus
  priority: number
  freshness: string
  configuration_env: string[]
  tenant_requirements: string[]
  recommended_endpoints: string[]
  required_permissions: string[]
  supported_entities: string[]
  algorithm_notes: string[]
  consistency_notes: string[]
  official_limitations: string[]
  current_runtime_coverage: string[]
  documentation_links: DocumentationLink[]
}

export interface ConnectorBlueprintResponse {
  generated_at: string
  blueprints: ConnectorBlueprint[]
}

export interface Hotspot {
  resource: EntitySummary
  privileged_principal_count: number
  delegated_path_count: number
  exposure_score: number
  headline: string
}

export interface ResourceExposureSummaryRecord {
  resource: EntitySummary
  principal_count: number
  privileged_principal_count: number
  max_risk_score: number
  average_path_complexity: number
  exposure_score: number
}

export interface PrincipalAccessSummaryRecord {
  principal: EntitySummary
  resource_count: number
  privileged_resource_count: number
  max_risk_score: number
  average_path_complexity: number
  exposure_score: number
}

export interface ExposureAnalyticsResponse {
  generated_at: string
  resource_summaries: ResourceExposureSummaryRecord[]
  principal_summaries: PrincipalAccessSummaryRecord[]
}

export interface QueryPerformanceMetric {
  operation: string
  calls: number
  average_ms: number
  p95_ms: number
  max_ms: number
  error_count: number
  last_seen_at?: string | null
}

export interface QueryPerformanceResponse {
  generated_at: string
  metrics: QueryPerformanceMetric[]
}

export interface IndexRefreshSummary {
  generated_at: string
  previous_snapshot_at?: string | null
  mode: IndexRefreshMode
  changed_entities: number
  changed_relationships: number
  impacted_principals: number
  impacted_resources: number
  reused_access_rows: number
  recomputed_access_rows: number
  total_access_rows: number
  carried_forward_group_closure: boolean
  recomputed_group_closure_principals: number
  carried_forward_resource_hierarchy: boolean
  recomputed_resource_hierarchy_resources: number
  fallback_reasons: string[]
}

export interface HistoricalPoint {
  day: string
  privileged_paths: number
  dormant_entitlements: number
  change_requests: number
}

export interface InsightNote {
  title: string
  body: string
  tone: Tone
}

export interface ScenarioChoice {
  edge_id: string
  label: string
  reason: string
  focus_resource_id?: string | null
  estimated_impacted_principals: number
}

export interface OverviewResponse {
  tenant: string
  generated_at: string
  metrics: MetricCard[]
  connectors: Connector[]
  hotspots: Hotspot[]
  scenarios: ScenarioChoice[]
  history: HistoricalPoint[]
  insights: InsightNote[]
  default_principal_id?: string | null
  default_resource_id?: string | null
  default_scenario_edge_id?: string | null
}

export interface CatalogResponse {
  principals: EntitySummary[]
  resources: EntitySummary[]
  scenarios: ScenarioChoice[]
}

export interface SearchResult {
  entity: EntitySummary
  headline: string
  keywords: string[]
}

export interface ResourceAccessRecord {
  principal: EntitySummary
  permissions: string[]
  path_count: number
  path_complexity: number
  access_mode: string
  risk_score: number
  why: string
}

export interface ResourceAccessResponse {
  resource: EntitySummary
  total_principals: number
  privileged_principal_count: number
  offset: number
  limit: number
  returned_count: number
  has_more: boolean
  records: ResourceAccessRecord[]
}

export interface PrincipalResourceRecord {
  resource: EntitySummary
  permissions: string[]
  path_count: number
  path_complexity: number
  access_mode: string
  risk_score: number
  why: string
}

export interface PrincipalAccessResponse {
  principal: EntitySummary
  total_resources: number
  privileged_resources: number
  offset: number
  limit: number
  returned_count: number
  has_more: boolean
  records: PrincipalResourceRecord[]
}

export interface GraphNode {
  id: string
  label: string
  kind: EntityKind
  source: string
  tags: string[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  kind: string
  highlighted: boolean
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface PathStep {
  edge_id: string
  edge_kind: string
  source: EntitySummary
  target: EntitySummary
  label: string
  rationale: string
  permissions: string[]
  inherits: boolean
  temporary: boolean
  removable: boolean
}

export interface AccessPath {
  permissions: string[]
  access_mode: string
  risk_score: number
  narrative: string
  steps: PathStep[]
}

export interface ExplainResponse {
  principal: EntitySummary
  resource: EntitySummary
  permissions: string[]
  path_count: number
  risk_score: number
  paths: AccessPath[]
  graph: GraphPayload
}

export interface EntityDetailResponse {
  entity: Entity
  perspective: EntityPerspective
  inbound: PathStep[]
  outbound: PathStep[]
  overview_metrics: MetricCard[]
  direct_grants: PathStep[]
  inherited_grants: PathStep[]
  group_paths: PathStep[]
  group_closure: GroupClosureRecord[]
  resource_hierarchy: ResourceHierarchyRecord[]
  role_paths: PathStep[]
  principal_access: PrincipalResourceRecord[]
  resource_access: ResourceAccessRecord[]
  admin_rights: PrincipalResourceRecord[]
  risk_findings: RiskFinding[]
  recent_changes: ChangeRecord[]
}

export interface GroupClosureRecord {
  group: EntitySummary
  depth: number
  shortest_parent: EntitySummary
  path_count: number
}

export interface ResourceHierarchyRecord {
  ancestor: EntitySummary
  depth: number
  inherits_acl: boolean
}

export interface GraphSubgraphResponse {
  focus: EntitySummary
  depth: number
  truncated: boolean
  node_limit: number
  edge_limit: number
  graph: GraphPayload
  inbound_count: number
  outbound_count: number
}

export interface WhatIfDiffItem {
  principal: EntitySummary
  resource: EntitySummary
  removed_permissions: string[]
  access_mode_before: string
}

export interface ResourceImpact {
  resource: EntitySummary
  removed_principal_count: number
  removed_permission_count: number
  severity: Tone
}

export interface FlowNode {
  id: string
  label: string
  kind: string
  x: number
  y: number
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  label: string
}

export interface FlowPayload {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export interface WhatIfResponse {
  edge: Relationship
  narrative: string
  impacted_principals: number
  impacted_resources: number
  removed_paths: number
  privileged_paths_removed: number
  recomputed_principals: number
  recomputed_resources: number
  recomputed_pairs: number
  diff: WhatIfDiffItem[]
  blast_radius: ResourceImpact[]
  focus_resource_id?: string | null
  focus_before: ResourceAccessRecord[]
  focus_after: ResourceAccessRecord[]
  flow: FlowPayload
}

export interface BenchmarkMetric {
  name: string
  iterations: number
  average_ms: number
  median_ms: number
  p95_ms: number
  max_ms: number
}

export interface BenchmarkSnapshot {
  mode: 'real' | 'synthetic'
  scope: string
  target_count: number
  entity_count: number
  relationship_count: number
  scale?: number | null
}

export interface BenchmarkResponse {
  generated_at: string
  snapshot: BenchmarkSnapshot
  metrics: BenchmarkMetric[]
  notes: string[]
}

export interface RiskFinding {
  id: string
  category: string
  severity: Tone
  headline: string
  detail: string
  recommended_action: string
  affected_principal_count: number
  affected_resource_count: number
  resource?: EntitySummary | null
  principal?: EntitySummary | null
  source: string
}

export interface RiskFindingsResponse {
  generated_at: string
  total_findings: number
  findings: RiskFinding[]
}

export interface ChangeRecord {
  id: string
  occurred_at: string
  change_type: string
  status: string
  summary: string
  previous_snapshot_at?: string | null
  current_snapshot_at?: string | null
  target_count: number
  resource_count: number
  relationship_count: number
  warning_count: number
  privileged_path_count: number
  broad_access_count: number
  added_access_count: number
  removed_access_count: number
  changed_access_count: number
  affected_principal_count: number
  affected_resource_count: number
}

export interface ChangesResponse {
  generated_at: string
  changes: ChangeRecord[]
}

export interface AuditEventRecord {
  id: string
  occurred_at: string
  actor_username: string
  action: string
  status: string
  target_type: string
  target_id?: string | null
  summary: string
  details: Record<string, string>
}

export interface AuditEventsResponse {
  generated_at: string
  events: AuditEventRecord[]
}

export interface OperationalFlowStep {
  id: string
  title: string
  status: 'ready' | 'action_required' | 'in_progress'
  detail: string
  recommended_action: string
}

export interface OperationalFlowResponse {
  generated_at: string
  overall_status: 'ready' | 'action_required' | 'in_progress'
  completion_percent: number
  steps: OperationalFlowStep[]
  next_actions: string[]
}

export interface MvpReadinessItem {
  id: string
  title: string
  status: 'ready' | 'action_required' | 'in_progress'
  required: boolean
  summary: string
  why_it_matters: string
  recommended_action: string
  workspace: string
  section?: string | null
}

export interface MvpReadinessAction {
  id: string
  label: string
  detail: string
  workspace: string
  section?: string | null
}

export interface MvpReadinessFreshness {
  status: 'fresh' | 'aging' | 'stale' | 'missing'
  summary: string
  snapshot_generated_at?: string | null
  latest_successful_scan_at?: string | null
  age_minutes?: number | null
}

export interface MvpReadinessResponse {
  generated_at: string
  overall_status: 'ready' | 'action_required' | 'in_progress'
  completion_percent: number
  primary_scope: string
  checklist: MvpReadinessItem[]
  blockers: string[]
  next_actions: string[]
  actions: MvpReadinessAction[]
  freshness: MvpReadinessFreshness
}

export interface FeatureInventoryItem {
  id: string
  title: string
  status: 'present' | 'partial' | 'missing'
  required_for_mvp: boolean
  summary: string
  gap: string
  recommended_action: string
  workspace: string
  section?: string | null
}

export interface FeatureInventoryCategory {
  id: string
  title: string
  summary: string
  items: FeatureInventoryItem[]
  present_count: number
  partial_count: number
  missing_count: number
}

export interface FeatureInventoryResponse {
  generated_at: string
  primary_scope: string
  overall_status: 'ready' | 'action_required' | 'in_progress'
  categories: FeatureInventoryCategory[]
  present_count: number
  partial_count: number
  missing_count: number
  required_missing: string[]
}

export interface BootstrapStatus {
  setup_required: boolean
  admin_username: string
  must_change_password: boolean
  password_generated: boolean
  password_file?: string | null
}

export interface SessionResponse {
  authenticated: boolean
  username?: string | null
  auth_source?: string | null
  roles: AppRole[]
  capabilities: string[]
  must_change_password: boolean
  csrf_token?: string | null
  mfa_required?: boolean
  mfa_enabled?: boolean
  mfa_challenge_token?: string | null
  setup_required: boolean
  bootstrap?: BootstrapStatus | null
  active_workspace_id?: string | null
  active_workspace_name?: string | null
}

export interface WorkspaceSummary {
  id: string
  name: string
  slug: string
  description?: string | null
  environment: 'on-prem' | 'cloud' | 'hybrid'
  active: boolean
  created_at: string
  updated_at: string
  storage_path: string
}

export interface WorkspaceListResponse {
  generated_at: string
  active_workspace_id?: string | null
  workspaces: WorkspaceSummary[]
}

export interface MfaStatusResponse {
  available: boolean
  enabled: boolean
  pending_setup: boolean
  method: 'totp'
  issuer: string
  provider_hint: string
}

export interface MfaSetupResponse {
  method: 'totp'
  issuer: string
  account_name: string
  manual_entry_key: string
  provisioning_uri: string
}

export interface SetupStatusResponse {
  setup_required: boolean
  local_admin_configured: boolean
  auth_provider_count: number
  tenant_name: string
  recommended_flow: string
}

export interface AdminUserSummary {
  username: string
  display_name?: string | null
  auth_source: string
  roles: AppRole[]
  capabilities: string[]
  mfa_enabled: boolean
  created_at: string
  must_change_password: boolean
}

export interface AdminUserListResponse {
  generated_at: string
  users: AdminUserSummary[]
}

export interface RuntimeStatusResponse {
  host: string
  platform: string
  runtime_role: RuntimeRole
  admin_username: string
  bootstrap: BootstrapStatus
  target_count: number
  active_target_count: number
  latest_snapshot_at?: string | null
  latest_scan_status?: TargetStatus | null
  last_successful_scan_at?: string | null
  last_successful_scan_duration_ms?: number | null
  raw_batch_count: number
  materialized_access_rows: number
  freshness_status: 'fresh' | 'stale' | 'empty'
  scan_in_progress: boolean
  scheduler_enabled: boolean
  scheduler_interval_seconds?: number | null
  report_scheduler_enabled: boolean
  report_scheduler_interval_seconds?: number | null
  background_jobs_capable: boolean
  background_jobs_active: boolean
  background_worker_state: BackgroundWorkerState
  background_worker_host?: string | null
  background_worker_last_seen_at?: string | null
  index_refresh?: IndexRefreshSummary | null
}

export interface JobWorkerLane {
  id: string
  name: string
  kind: 'scan' | 'report_delivery'
  state: 'idle' | 'running' | 'scheduled' | 'disabled' | 'attention'
  scheduler_enabled: boolean
  execution_mode: BackgroundWorkerState
  worker_host?: string | null
  worker_role?: RuntimeRole | null
  worker_last_seen_at?: string | null
  queue_depth: number
  active_work_items: number
  last_completed_at?: string | null
  next_due_at?: string | null
  last_status?: string | null
  summary: string
}

export interface JobRecentActivity {
  id: string
  lane_id: string
  label: string
  status: string
  started_at: string
  finished_at?: string | null
  summary: string
}

export interface JobCenterResponse {
  generated_at: string
  overall_status: 'healthy' | 'watch' | 'attention'
  lanes: JobWorkerLane[]
  recent_jobs: JobRecentActivity[]
}

export type TargetPlatform = 'auto' | 'windows' | 'linux'
export type TargetConnectionMode = 'local' | 'ssh'
export type TargetStatus = 'idle' | 'running' | 'healthy' | 'warning' | 'failed'

export interface ScanTarget {
  id: string
  kind: 'filesystem'
  name: string
  path: string
  platform: TargetPlatform
  connection_mode: TargetConnectionMode
  host?: string | null
  port: number
  username?: string | null
  secret_env?: string | null
  key_path?: string | null
  recursive: boolean
  max_depth: number
  max_entries: number
  include_hidden: boolean
  enabled: boolean
  notes?: string | null
  last_scan_at?: string | null
  last_status: TargetStatus
  last_error?: string | null
  created_at: string
  updated_at: string
}

export interface ScanRunRecord {
  id: string
  started_at: string
  finished_at?: string | null
  status: TargetStatus
  duration_ms?: number | null
  target_ids: string[]
  resource_count: number
  principal_count: number
  relationship_count: number
  warning_count: number
  notes: string[]
}

export interface ScanRunsResponse {
  active: boolean
  latest?: ScanRunRecord | null
  recent: ScanRunRecord[]
}

export interface ConnectorRuntimeStatus {
  id: string
  name: string
  source: string
  surface: string
  implementation_status: ConnectorImplementationStatus
  configured: boolean
  enabled: boolean
  status: ConnectorRuntimeState
  collection_mode: 'snapshot' | 'incremental' | 'hybrid'
  description: string
  required_env: string[]
  required_permissions: string[]
  supported_entities: string[]
  tenant_requirements: string[]
  official_limitations: string[]
  current_runtime_coverage: string[]
  documentation_links: DocumentationLink[]
  notes: string[]
  last_sync?: string | null
  entity_count: number
  relationship_count: number
}

export interface ConnectorRuntimeResponse {
  generated_at: string
  connectors: ConnectorRuntimeStatus[]
}

export interface ConnectorSupportMatrixEntry {
  id: string
  name: string
  category: string
  vendor: string
  support_tier: 'supported' | 'pilot' | 'experimental' | 'blueprint'
  validation_level: 'runtime_verified' | 'config_validated' | 'doc_aligned' | 'planned'
  recommended_usage: 'production' | 'pilot' | 'lab' | 'design_only'
  runtime_configured: boolean
  runtime_enabled: boolean
  implementation_status: ConnectorImplementationStatus
  summary: string
  evidence: string[]
  current_gaps: string[]
  next_actions: string[]
  documentation_links: DocumentationLink[]
}

export interface ConnectorSupportMatrixResponse {
  generated_at: string
  primary_scope: string
  entries: ConnectorSupportMatrixEntry[]
  counts_by_tier: Record<string, number>
  counts_by_validation: Record<string, number>
}

export interface PlatformComponentStatus {
  id: string
  name: string
  category: string
  state: PlatformComponentState
  configured: boolean
  connected: boolean
  summary: string
  details: string[]
  documentation_url?: string | null
}

export interface PlatformPostureResponse {
  generated_at: string
  storage_backend: string
  search_backend: string
  cache_backend: string
  analytics_backend: string
  materialized_access_index: boolean
  components: PlatformComponentStatus[]
}

export type AccessReviewDecisionValue = 'pending' | 'keep' | 'revoke' | 'needs_follow_up'
export type AccessReviewCampaignStatus = 'open' | 'completed'

export interface AccessReviewItem {
  id: string
  campaign_id: string
  principal_id: string
  resource_id: string
  principal: EntitySummary
  resource: EntitySummary
  permissions: string[]
  path_count: number
  access_mode: string
  risk_score: number
  why: string
  decision: AccessReviewDecisionValue
  decision_note?: string | null
  reviewed_at?: string | null
  suggested_edge_id?: string | null
  suggested_edge_label?: string | null
  suggested_remediation?: string | null
}

export interface AccessReviewCampaignSummary {
  id: string
  name: string
  description?: string | null
  snapshot_generated_at: string
  status: AccessReviewCampaignStatus
  created_by: string
  created_at: string
  updated_at: string
  total_items: number
  pending_items: number
  keep_count: number
  revoke_count: number
  follow_up_count: number
  min_risk_score: number
  privileged_only: boolean
}

export interface AccessReviewCampaignDetailResponse {
  summary: AccessReviewCampaignSummary
  items: AccessReviewItem[]
}

export interface AccessReviewCampaignListResponse {
  generated_at: string
  campaigns: AccessReviewCampaignSummary[]
}

export type ReportFormat = 'html' | 'pdf' | 'xlsx'
export type ReportScheduleCadence = 'hourly' | 'daily' | 'weekly' | 'monthly'
export type ReportScheduleKind = 'access_review' | 'review_campaign'
export type ReportDeliverySecurityMode = 'none' | 'starttls' | 'ssl'
export type ReportScheduleRunTrigger = 'manual' | 'scheduled'
export type ReportScheduleRunStatus = 'success' | 'failed' | 'partial' | 'running'
export type ReportScheduleState = 'never' | 'success' | 'failed' | 'partial' | 'running'

export interface ReportEmailDeliverySettings {
  enabled: boolean
  smtp_host?: string | null
  smtp_port: number
  security: ReportDeliverySecurityMode
  username?: string | null
  password_env?: string | null
  from_address?: string | null
  reply_to?: string | null
  to: string[]
  cc: string[]
  bcc: string[]
  subject_template: string
  message_body: string
  attach_formats: ReportFormat[]
  include_html_body: boolean
}

export interface ReportWebhookDeliverySettings {
  enabled: boolean
  url?: string | null
  secret_env?: string | null
  secret_header: string
  include_summary: boolean
}

export interface ReportArchiveDeliverySettings {
  enabled: boolean
  directory?: string | null
  filename_prefix?: string | null
}

export interface ReportDeliverySettings {
  email: ReportEmailDeliverySettings
  webhook: ReportWebhookDeliverySettings
  archive: ReportArchiveDeliverySettings
}

export interface ReportScheduleConfig {
  kind: ReportScheduleKind
  locale: 'en' | 'it' | 'de' | 'fr' | 'es'
  formats: ReportFormat[]
  principal_id?: string | null
  resource_id?: string | null
  scenario_edge_id?: string | null
  focus_resource_id?: string | null
  campaign_id?: string | null
  title_override?: string | null
}

export interface ReportScheduleSummary {
  id: string
  name: string
  description?: string | null
  enabled: boolean
  cadence: ReportScheduleCadence
  timezone: string
  hour: number
  minute: number
  day_of_week?: number | null
  day_of_month?: number | null
  report_kind: ReportScheduleKind
  locale: 'en' | 'it' | 'de' | 'fr' | 'es'
  formats: ReportFormat[]
  channels: string[]
  created_by: string
  created_at: string
  updated_at: string
  next_run_at?: string | null
  last_run_at?: string | null
  last_status: ReportScheduleState
  last_message?: string | null
}

export interface ReportScheduleRunRecord {
  id: string
  schedule_id: string
  started_at: string
  finished_at?: string | null
  trigger: ReportScheduleRunTrigger
  status: ReportScheduleRunStatus
  delivered_channels: string[]
  artifact_paths: string[]
  message?: string | null
}

export interface ReportScheduleDetailResponse {
  summary: ReportScheduleSummary
  config: ReportScheduleConfig
  delivery: ReportDeliverySettings
  recent_runs: ReportScheduleRunRecord[]
}

export interface ReportScheduleListResponse {
  generated_at: string
  schedules: ReportScheduleSummary[]
}

export interface AccessReviewRemediationStep {
  order: number
  title: string
  detail: string
  impact: string
}

export interface AccessReviewRemediationPlan {
  item_id: string
  campaign_id: string
  summary: string
  suggested_edge_id?: string | null
  suggested_edge_label?: string | null
  impacted_principals: number
  impacted_resources: number
  privileged_paths_removed: number
  steps: AccessReviewRemediationStep[]
}

export interface ImportedSourceBundle {
  name: string
  source: string
  environment: 'on-prem' | 'cloud' | 'hybrid'
  description?: string | null
  entities: Entity[]
  relationships: Relationship[]
  connectors: Connector[]
  insights: InsightNote[]
}

export interface ImportedSourceSummary {
  id: string
  name: string
  source: string
  environment: 'on-prem' | 'cloud' | 'hybrid'
  description?: string | null
  enabled: boolean
  entity_count: number
  relationship_count: number
  connector_count: number
  created_at: string
  updated_at: string
}

export interface ImportedSourceDetailResponse {
  summary: ImportedSourceSummary
  bundle: ImportedSourceBundle
}

export interface ImportedSourceListResponse {
  generated_at: string
  total_sources: number
  sources: ImportedSourceSummary[]
}

export interface IdentityClusterSummary {
  id: string
  display_name: string
  entity_count: number
  source_count: number
  sources: string[]
  match_keys: string[]
  combined_resource_count: number
  max_risk_score: number
}

export type AuthProviderKind = 'ldap' | 'oidc'
export type AuthProviderPreset =
  | 'custom'
  | 'microsoft'
  | 'google'
  | 'github'
  | 'okta'
  | 'keycloak'
export type AppRole =
  | 'viewer'
  | 'investigator'
  | 'admin'
  | 'connector_admin'
  | 'auditor'
  | 'executive_read_only'

export interface AuthProviderConfig {
  kind: AuthProviderKind
  preset: AuthProviderPreset
  description?: string | null
  issuer_url?: string | null
  discovery_url?: string | null
  client_id?: string | null
  client_secret_env?: string | null
  scopes: string[]
  allowed_domains: string[]
  allowed_emails: string[]
  username_attribute?: string | null
  email_attribute?: string | null
  ldap_server_uri?: string | null
  ldap_base_dn?: string | null
  ldap_bind_dn?: string | null
  ldap_bind_password_env?: string | null
  ldap_user_search_filter?: string | null
  allowed_groups: string[]
  start_tls: boolean
}

export interface AuthProviderSummary {
  id: string
  name: string
  kind: AuthProviderKind
  preset: AuthProviderPreset
  enabled: boolean
  description?: string | null
  accepts_password: boolean
  uses_redirect: boolean
  created_at: string
  updated_at: string
}

export interface AuthProviderDetailResponse {
  summary: AuthProviderSummary
  config: AuthProviderConfig
}

export interface AuthProviderListResponse {
  generated_at: string
  providers: AuthProviderSummary[]
}

export interface PublicAuthProviderSummary {
  id: string
  name: string
  kind: AuthProviderKind
  preset: AuthProviderPreset
  sign_in_label: string
  accepts_password: boolean
  uses_redirect: boolean
  login_path?: string | null
}

export interface PublicAuthProviderListResponse {
  generated_at: string
  providers: PublicAuthProviderSummary[]
}

export interface IdentityClusterMember {
  entity: EntitySummary
  confidence: number
  evidence: string[]
  match_keys: string[]
}

export interface IdentityClusterResource {
  resource: EntitySummary
  permissions: string[]
  contributing_identities: EntitySummary[]
  max_risk_score: number
  path_count: number
}

export interface IdentityClustersResponse {
  generated_at: string
  total_clusters: number
  clusters: IdentityClusterSummary[]
}

export interface IdentityClusterDetailResponse {
  cluster: IdentityClusterSummary
  members: IdentityClusterMember[]
  top_resources: IdentityClusterResource[]
}
