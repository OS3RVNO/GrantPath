import type {
  AccessReviewCampaignDetailResponse,
  AccessReviewCampaignListResponse,
  AccessReviewRemediationPlan,
  AdminUserListResponse,
  AdminUserSummary,
  AppRole,
  AuditEventsResponse,
  AuthProviderConfig,
  AuthProviderDetailResponse,
  AuthProviderListResponse,
  BenchmarkResponse,
  CatalogResponse,
  ChangesResponse,
  ConnectorBlueprintResponse,
  ConnectorRuntimeResponse,
  ConnectorSupportMatrixResponse,
  EntityDetailResponse,
  ExposureAnalyticsResponse,
  ExplainResponse,
  FeatureInventoryResponse,
  GraphSubgraphResponse,
  IdentityClusterDetailResponse,
  IdentityClustersResponse,
  ImportedSourceDetailResponse,
  ImportedSourceListResponse,
  ImportedSourceBundle,
  JobCenterResponse,
  MfaSetupResponse,
  MfaStatusResponse,
  MvpReadinessResponse,
  OverviewResponse,
  OperationalFlowResponse,
  PlatformPostureResponse,
  PrincipalAccessResponse,
  PublicAuthProviderListResponse,
  QueryPerformanceResponse,
  ReportScheduleDetailResponse,
  ReportScheduleListResponse,
  RiskFindingsResponse,
  ResourceAccessResponse,
  RuntimeStatusResponse,
  ScanRunsResponse,
  ScanTarget,
  SearchResult,
  SessionResponse,
  SetupStatusResponse,
  WhatIfResponse,
  WorkspaceListResponse,
  WorkspaceSummary,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const CSRF_HEADER = 'X-EIP-CSRF-Token'
let csrfToken: string | null = null

function captureCsrfToken(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return
  }
  if ('csrf_token' in payload) {
    const nextToken = payload.csrf_token
    csrfToken = typeof nextToken === 'string' && nextToken.length > 0 ? nextToken : null
  }
}

function isMutationRequest(method?: string) {
  return ['POST', 'PUT', 'PATCH', 'DELETE'].includes((method ?? 'GET').toUpperCase())
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (isMutationRequest(init?.method) && csrfToken) {
    headers.set(CSRF_HEADER, csrfToken)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers,
    ...init,
  })

  if (!response.ok) {
    if (response.status === 401) {
      csrfToken = null
    }
    const detail = await response.text()
    let parsedDetail: string | null = null
    try {
      const payload = JSON.parse(detail) as { detail?: string }
      parsedDetail = payload.detail ?? null
    } catch {
      parsedDetail = null
    }
    throw new Error(parsedDetail || detail || `Request failed: ${response.status}`)
  }

  const payload = (await response.json()) as T
  captureCsrfToken(payload)
  return payload
}

export function fetchBootstrapStatus() {
  return request<SessionResponse['bootstrap']>('/api/auth/bootstrap-status')
}

export function fetchSetupStatus() {
  return request<SetupStatusResponse>('/api/setup/status')
}

export function setupLocalAdmin(payload: {
  tenant_name?: string
  username: string
  password: string
}) {
  return request<SetupStatusResponse>('/api/setup/local-admin', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchSession() {
  return request<SessionResponse>('/api/auth/session')
}

export function fetchWorkspaces() {
  return request<WorkspaceListResponse>('/api/workspaces')
}

export function createWorkspace(payload: {
  name: string
  slug?: string
  description?: string
  environment: 'on-prem' | 'cloud' | 'hybrid'
}) {
  return request<WorkspaceSummary>('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWorkspace(
  workspaceId: string,
  payload: Partial<{
    name: string
    description: string
    environment: 'on-prem' | 'cloud' | 'hybrid'
  }>,
) {
  return request<WorkspaceSummary>(`/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function activateWorkspace(workspaceId: string) {
  return request<WorkspaceSummary>(`/api/workspaces/${encodeURIComponent(workspaceId)}/activate`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function login(username: string, password: string, providerId?: string) {
  return request<SessionResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password, provider_id: providerId }),
  })
}

export function logout() {
  return request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }).then((payload) => {
    csrfToken = null
    return payload
  })
}

export function changePassword(currentPassword: string, newPassword: string) {
  return request<{ ok: boolean }>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
}

export function fetchMfaStatus() {
  return request<MfaStatusResponse>('/api/auth/mfa/status')
}

export function beginMfaSetup() {
  return request<MfaSetupResponse>('/api/auth/mfa/setup', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function confirmMfaSetup(code: string) {
  return request<{ ok: boolean }>('/api/auth/mfa/enable', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
}

export function disableMfa(currentPassword: string, code: string) {
  return request<{ ok: boolean }>('/api/auth/mfa/disable', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      code,
    }),
  }).then((payload) => {
    csrfToken = null
    return payload
  })
}

export function verifyMfaChallenge(challengeToken: string, code: string) {
  return request<SessionResponse>('/api/auth/mfa/verify', {
    method: 'POST',
    body: JSON.stringify({
      challenge_token: challengeToken,
      code,
    }),
  })
}

export function fetchPublicAuthProviders() {
  return request<PublicAuthProviderListResponse>('/api/auth/providers/public')
}

export function fetchAuthProviders() {
  return request<AuthProviderListResponse>('/api/auth/providers')
}

export function fetchAdminUsers() {
  return request<AdminUserListResponse>('/api/admin-users')
}

export function updateAdminUserRoles(username: string, roles: AppRole[]) {
  return request<AdminUserSummary>(
    `/api/admin-users/${encodeURIComponent(username)}/roles`,
    {
      method: 'PATCH',
      body: JSON.stringify({ roles }),
    },
  )
}

export function createAuthProvider(payload: {
  name: string
  enabled: boolean
  config: AuthProviderConfig
}) {
  return request<AuthProviderDetailResponse>('/api/auth/providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAuthProvider(
  providerId: string,
  payload: Partial<{
    name: string
    enabled: boolean
    config: AuthProviderConfig
  }>,
) {
  return request<AuthProviderDetailResponse>(`/api/auth/providers/${encodeURIComponent(providerId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteAuthProvider(providerId: string) {
  return request<{ ok: boolean }>(`/api/auth/providers/${encodeURIComponent(providerId)}`, {
    method: 'DELETE',
  })
}

export function fetchRuntimeStatus() {
  return request<RuntimeStatusResponse>('/api/runtime')
}

export function fetchTargets() {
  return request<ScanTarget[]>('/api/targets')
}

export function createTarget(payload: {
  name: string
  path: string
  platform: 'auto' | 'windows' | 'linux'
  connection_mode: 'local' | 'ssh'
  host?: string
  port: number
  username?: string
  secret_env?: string
  key_path?: string
  recursive: boolean
  max_depth: number
  max_entries: number
  include_hidden: boolean
  enabled: boolean
  notes?: string
}) {
  return request<ScanTarget>('/api/targets', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateTarget(
  targetId: string,
  payload: Partial<{
    name: string
    path: string
    platform: 'auto' | 'windows' | 'linux'
    connection_mode: 'local' | 'ssh'
    host?: string
    port: number
    username?: string
    secret_env?: string
    key_path?: string
    recursive: boolean
    max_depth: number
    max_entries: number
    include_hidden: boolean
    enabled: boolean
    notes?: string
  }>,
) {
  return request<ScanTarget>(`/api/targets/${encodeURIComponent(targetId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function fetchScans() {
  return request<ScanRunsResponse>('/api/scans')
}

export function runScan() {
  return request<ScanRunsResponse['latest']>('/api/scans/run', { method: 'POST' })
}

export function runTargetScan(targetId: string) {
  return request<ScanRunsResponse['latest']>(
    `/api/targets/${encodeURIComponent(targetId)}/scan`,
    { method: 'POST' },
  )
}

export function fetchOverview() {
  return request<OverviewResponse>('/api/overview')
}

export function fetchCatalog() {
  return request<CatalogResponse>('/api/catalog')
}

export function fetchConnectorBlueprints() {
  return request<ConnectorBlueprintResponse>('/api/connector-blueprints')
}

export function fetchConnectorRuntime() {
  return request<ConnectorRuntimeResponse>('/api/connectors/runtime')
}

export function fetchConnectorSupportMatrix() {
  return request<ConnectorSupportMatrixResponse>('/api/connectors/support-matrix')
}

export function fetchPlatformPosture() {
  return request<PlatformPostureResponse>('/api/platform/posture')
}

export function fetchOperationalFlow() {
  return request<OperationalFlowResponse>('/api/operational-flow')
}

export function fetchJobCenter() {
  return request<JobCenterResponse>('/api/jobs/center')
}

export function fetchExposureAnalytics() {
  return request<ExposureAnalyticsResponse>('/api/analytics/exposure')
}

export function fetchQueryPerformance() {
  return request<QueryPerformanceResponse>('/api/analytics/query-performance')
}

export function fetchMvpReadiness() {
  return request<MvpReadinessResponse>('/api/mvp/readiness')
}

export function fetchFeatureInventory() {
  return request<FeatureInventoryResponse>('/api/mvp/inventory')
}

export function fetchAuditEvents(limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) })
  return request<AuditEventsResponse>(`/api/audit/events?${params.toString()}`)
}

export function fetchImportedSources() {
  return request<ImportedSourceListResponse>('/api/imported-sources')
}

export function fetchAccessReviews() {
  return request<AccessReviewCampaignListResponse>('/api/access-reviews')
}

export function createAccessReview(payload: {
  name: string
  description?: string
  min_risk_score: number
  privileged_only: boolean
  max_items: number
}) {
  return request<AccessReviewCampaignDetailResponse>('/api/access-reviews', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchAccessReview(campaignId: string) {
  return request<AccessReviewCampaignDetailResponse>(
    `/api/access-reviews/${encodeURIComponent(campaignId)}`,
  )
}

export function updateAccessReviewDecision(
  campaignId: string,
  itemId: string,
  payload: {
    decision: 'pending' | 'keep' | 'revoke' | 'needs_follow_up'
    decision_note?: string
  },
) {
  return request<AccessReviewCampaignDetailResponse>(
    `/api/access-reviews/${encodeURIComponent(campaignId)}/items/${encodeURIComponent(itemId)}/decision`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function fetchAccessReviewRemediation(campaignId: string, itemId: string) {
  return request<AccessReviewRemediationPlan>(
    `/api/access-reviews/${encodeURIComponent(campaignId)}/items/${encodeURIComponent(itemId)}/remediation`,
  )
}

export function fetchReportSchedules() {
  return request<ReportScheduleListResponse>('/api/report-schedules')
}

export function fetchReportSchedule(scheduleId: string) {
  return request<ReportScheduleDetailResponse>(
    `/api/report-schedules/${encodeURIComponent(scheduleId)}`,
  )
}

export function createReportSchedule(payload: {
  name: string
  description?: string
  enabled: boolean
  cadence: 'hourly' | 'daily' | 'weekly' | 'monthly'
  timezone: string
  hour: number
  minute: number
  day_of_week?: number | null
  day_of_month?: number | null
  config: Record<string, unknown>
  delivery: Record<string, unknown>
}) {
  return request<ReportScheduleDetailResponse>('/api/report-schedules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateReportSchedule(
  scheduleId: string,
  payload: Record<string, unknown>,
) {
  return request<ReportScheduleDetailResponse>(
    `/api/report-schedules/${encodeURIComponent(scheduleId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function deleteReportSchedule(scheduleId: string) {
  return request<{ ok: boolean }>(`/api/report-schedules/${encodeURIComponent(scheduleId)}`, {
    method: 'DELETE',
  })
}

export function runReportSchedule(scheduleId: string) {
  return request<ReportScheduleDetailResponse>(
    `/api/report-schedules/${encodeURIComponent(scheduleId)}/run`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

export function createImportedSource(payload: ImportedSourceBundle) {
  return request<ImportedSourceDetailResponse>('/api/imported-sources', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateImportedSource(sourceId: string, payload: { enabled?: boolean }) {
  return request<ImportedSourceDetailResponse>(`/api/imported-sources/${encodeURIComponent(sourceId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteImportedSource(sourceId: string) {
  return request<{ ok: boolean }>(`/api/imported-sources/${encodeURIComponent(sourceId)}`, {
    method: 'DELETE',
  })
}

export function fetchIdentityClusters() {
  return request<IdentityClustersResponse>('/api/identity-clusters')
}

export function fetchIdentityClusterDetail(clusterId: string) {
  return request<IdentityClusterDetailResponse>(
    `/api/identity-clusters/${encodeURIComponent(clusterId)}`,
  )
}

export function fetchBenchmark(mode: 'real' | 'synthetic' = 'real', scale = 10, iterations = 2) {
  const params = new URLSearchParams({
    mode,
    scale: String(scale),
    iterations: String(iterations),
  })
  return request<BenchmarkResponse>(`/api/benchmark?${params.toString()}`)
}

export function fetchSearch(query: string) {
  const params = new URLSearchParams({ q: query })
  return request<SearchResult[]>(`/api/search?${params.toString()}`)
}

export function fetchResourceAccess(
  resourceId: string,
  options?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  return request<ResourceAccessResponse>(
    `/api/resources/${encodeURIComponent(resourceId)}/access${params.size ? `?${params.toString()}` : ''}`,
  )
}

export function fetchResourceExposure(
  resourceId: string,
  options?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  return request<ResourceAccessResponse>(
    `/api/resources/${encodeURIComponent(resourceId)}/exposure${params.size ? `?${params.toString()}` : ''}`,
  )
}

export function fetchPrincipalAccess(
  principalId: string,
  options?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  return request<PrincipalAccessResponse>(
    `/api/principals/${encodeURIComponent(principalId)}/resources${params.size ? `?${params.toString()}` : ''}`,
  )
}

export function fetchUserAccess(
  principalId: string,
  options?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  return request<PrincipalAccessResponse>(
    `/api/users/${encodeURIComponent(principalId)}/access${params.size ? `?${params.toString()}` : ''}`,
  )
}

export function fetchExplanation(principalId: string, resourceId: string) {
  return request<ExplainResponse>('/api/explain', {
    method: 'POST',
    body: JSON.stringify({
      principal_id: principalId,
      resource_id: resourceId,
    }),
  })
}

export function fetchEntityDetail(entityId: string) {
  return request<EntityDetailResponse>(
    `/api/entities/${encodeURIComponent(entityId)}`,
  )
}

export function fetchGraphSubgraph(
  entityId: string,
  depth = 1,
  options?: { maxNodes?: number; maxEdges?: number },
) {
  const params = new URLSearchParams({
    entity_id: entityId,
    depth: String(depth),
  })
  if (typeof options?.maxNodes === 'number') {
    params.set('max_nodes', String(options.maxNodes))
  }
  if (typeof options?.maxEdges === 'number') {
    params.set('max_edges', String(options.maxEdges))
  }
  return request<GraphSubgraphResponse>(`/api/graph/subgraph?${params.toString()}`)
}

export function fetchWhatIf(edgeId: string, focusResourceId?: string | null) {
  return request<WhatIfResponse>('/api/what-if', {
    method: 'POST',
    body: JSON.stringify({
      edge_id: edgeId,
      focus_resource_id: focusResourceId ?? null,
    }),
  })
}

export function fetchWhatIfAlias(edgeId: string, focusResourceId?: string | null) {
  return request<WhatIfResponse>('/api/whatif', {
    method: 'POST',
    body: JSON.stringify({
      edge_id: edgeId,
      focus_resource_id: focusResourceId ?? null,
    }),
  })
}

export function fetchRisks(limit = 25) {
  const params = new URLSearchParams({ limit: String(limit) })
  return request<RiskFindingsResponse>(`/api/risks?${params.toString()}`)
}

export function fetchChanges(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) })
  return request<ChangesResponse>(`/api/changes?${params.toString()}`)
}

export function buildReportUrl(params: {
  format: 'html' | 'pdf' | 'xlsx'
  principalId: string
  resourceId: string
  scenarioEdgeId: string
  focusResourceId?: string | null
  locale?: string
}) {
  const query = new URLSearchParams({
    principal_id: params.principalId,
    resource_id: params.resourceId,
    scenario_edge_id: params.scenarioEdgeId,
  })

  if (params.focusResourceId) {
    query.set('focus_resource_id', params.focusResourceId)
  }
  if (params.locale) {
    query.set('locale', params.locale)
  }

  return `${API_BASE}/api/reports/access-review.${params.format}?${query.toString()}`
}

export function buildReviewCampaignReportUrl(params: {
  format: 'html' | 'pdf' | 'xlsx'
  campaignId: string
  locale?: string
}) {
  const query = new URLSearchParams({
    campaign_id: params.campaignId,
  })
  if (params.locale) {
    query.set('locale', params.locale)
  }
  return `${API_BASE}/api/reports/review-campaign.${params.format}?${query.toString()}`
}
