import {
  startTransition,
  useDeferredValue,
  useEffect,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'

import './App.css'
import {
  PRODUCT_CATEGORY,
  PRODUCT_DEFAULT_TENANT_NAME,
  PRODUCT_DEFAULT_TENANT_PLACEHOLDER,
  PRODUCT_NAME,
} from './branding'
import {
  beginMfaSetup,
  buildReportUrl,
  buildReviewCampaignReportUrl,
  activateWorkspace,
  createAccessReview,
  createAuthProvider,
  createWorkspace,
  changePassword,
  createTarget,
  createImportedSource,
  deleteAuthProvider,
  deleteImportedSource,
  disableMfa,
  fetchAdminUsers,
  fetchMfaStatus,
  fetchMvpReadiness,
  fetchAuditEvents,
  fetchAccessReview,
  fetchAccessReviewRemediation,
  fetchAccessReviews,
  fetchAuthProviders,
  fetchBenchmark,
  fetchCatalog,
  fetchConnectorBlueprints,
  fetchConnectorRuntime,
  fetchConnectorSupportMatrix,
  fetchExposureAnalytics,
  fetchEntityDetail,
  fetchExplanation,
  fetchFeatureInventory,
  fetchGraphSubgraph,
  fetchIdentityClusterDetail,
  fetchIdentityClusters,
  fetchImportedSources,
  fetchJobCenter,
  fetchOperationalFlow,
  fetchOverview,
  fetchPlatformPosture,
  fetchPublicAuthProviders,
  fetchQueryPerformance,
  fetchRisks,
  fetchResourceAccess,
  fetchRuntimeStatus,
  fetchScans,
  fetchSearch,
  fetchSession,
  fetchSetupStatus,
  fetchTargets,
  fetchChanges,
  fetchWhatIf,
  fetchWorkspaces,
  login,
  logout,
  runScan,
  runTargetScan,
  setupLocalAdmin,
  updateAdminUserRoles,
  verifyMfaChallenge,
  updateAccessReviewDecision,
  updateAuthProvider,
  updateImportedSource,
  updateTarget,
  updateWorkspace,
  confirmMfaSetup,
} from './api'
import { SearchBox } from './components/SearchBox'
import { LanguageSwitcher } from './components/LanguageSwitcher'
import { HomeDashboard } from './components/workspace/HomeDashboard'
import { InvestigateWorkspace } from './components/workspace/InvestigateWorkspace'
import { ReportSchedulesPanel } from './components/workspace/ReportSchedulesPanel'
import { WorkspaceNavigation } from './components/workspace/WorkspaceNavigation'
import { useI18n } from './i18n'
import type {
  AccessReviewCampaignDetailResponse,
  AccessReviewCampaignListResponse,
  AccessReviewRemediationPlan,
  AdminUserListResponse,
  AppRole,
  AuditEventsResponse,
  AuthProviderListResponse,
  AuthProviderPreset,
  AuthProviderConfig,
  BenchmarkResponse,
  BootstrapStatus,
  CatalogResponse,
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
  ImportedSourceListResponse,
  JobCenterResponse,
  MfaSetupResponse,
  MfaStatusResponse,
  MvpReadinessResponse,
  OperationalFlowResponse,
  OverviewResponse,
  PlatformPostureResponse,
  QueryPerformanceResponse,
  RiskFindingsResponse,
  ResourceAccessResponse,
  RuntimeStatusResponse,
  ScanRunsResponse,
  ScanTarget,
  SearchResult,
  SessionResponse,
  SetupStatusResponse,
  ChangesResponse,
  PublicAuthProviderListResponse,
  Tone,
  WhatIfResponse,
  WorkspaceListResponse,
} from './types'

type WorkspaceView = 'home' | 'investigate' | 'govern' | 'sources' | 'operations'
type InvestigateSection = 'explain' | 'exposure' | 'whatif'
type GovernSection = 'reviews' | 'remediation' | 'schedules'
type SourcesSection = 'auth' | 'collection' | 'imports' | 'identity'
type OperationsSection = 'status' | 'platform' | 'audit'
type GraphDensityProfile = 'compact' | 'expanded'

const WORKSPACE_VIEWS: Array<{
  id: WorkspaceView
  label: string
  title: string
  description: string
}> = [
  {
    id: 'home',
    label: 'Home',
    title: 'Executive command center',
    description:
      'Start from a short operational dashboard with top exposure, quick actions and recent platform signals before drilling into a workflow.',
  },
  {
    id: 'investigate',
    label: 'Investigate',
    title: 'Focus on access questions',
    description:
      'Use the explain, exposure and what-if views to answer who has access, why it exists and what changes would do.',
  },
  {
    id: 'govern',
    label: 'Govern',
    title: 'Run reviews and remediation',
    description:
      'Keep decisions, revoke plans and review evidence together so the governance loop stays clear and deterministic.',
  },
  {
    id: 'sources',
    label: 'Sources',
    title: 'Manage identities and collection',
    description:
      'Configure administrators, sign-in providers, monitored targets, offline bundles and cross-source identity linking in one place.',
  },
  {
    id: 'operations',
    label: 'Operations',
    title: 'Track readiness and performance',
    description:
      'Monitor scan health, runtime posture, connector readiness, benchmarks and administrator activity without cluttering the investigation flow.',
  },
]

const GOVERN_SECTIONS: Array<{ id: GovernSection; label: string }> = [
  { id: 'reviews', label: 'Reviews' },
  { id: 'remediation', label: 'Remediation' },
  { id: 'schedules', label: 'Schedules' },
]

const INVESTIGATE_SECTIONS: Array<{ id: InvestigateSection; label: string }> = [
  { id: 'explain', label: 'Explain' },
  { id: 'exposure', label: 'Exposure' },
  { id: 'whatif', label: 'What-If' },
]

const SOURCES_SECTIONS: Array<{ id: SourcesSection; label: string }> = [
  { id: 'auth', label: 'Auth' },
  { id: 'collection', label: 'Collection' },
  { id: 'imports', label: 'Imports' },
  { id: 'identity', label: 'Identity' },
]

const OPERATIONS_SECTIONS: Array<{ id: OperationsSection; label: string }> = [
  { id: 'status', label: 'Status' },
  { id: 'platform', label: 'Platform' },
  { id: 'audit', label: 'Audit' },
]

function toneLabel(tone: Tone) {
  if (tone === 'critical') {
    return 'Critical'
  }
  if (tone === 'warn') {
    return 'Watch'
  }
  if (tone === 'good') {
    return 'Healthy'
  }
  return 'Info'
}

function kindLabel(kind: string) {
  return kind.replace('_', ' ')
}

function platformLabel(platform: string) {
  if (platform === 'auto') {
    return 'Auto'
  }
  return platform.toUpperCase()
}

function connectionModeLabel(mode: string) {
  if (mode === 'ssh') {
    return 'SSH remote'
  }
  return 'Local path'
}

function implementationLabel(status: string) {
  if (status === 'live') {
    return 'Live collector'
  }
  if (status === 'partial') {
    return 'Partial runtime'
  }
  return 'Blueprint only'
}

function supportTierLabel(value: string) {
  if (value === 'supported') {
    return 'Supported'
  }
  if (value === 'pilot') {
    return 'Pilot ready'
  }
  if (value === 'experimental') {
    return 'Experimental'
  }
  return 'Blueprint only'
}

function validationLevelLabel(value: string) {
  if (value === 'runtime_verified') {
    return 'Runtime verified'
  }
  if (value === 'config_validated') {
    return 'Config validated'
  }
  if (value === 'doc_aligned') {
    return 'Documentation aligned'
  }
  return 'Planned'
}

function recommendedUsageLabel(value: string) {
  if (value === 'production') {
    return 'Production'
  }
  if (value === 'pilot') {
    return 'Pilot'
  }
  if (value === 'lab') {
    return 'Lab'
  }
  return 'Design only'
}

function appRoleLabel(role: AppRole) {
  if (role === 'connector_admin') {
    return 'Connector Admin'
  }
  if (role === 'executive_read_only') {
    return 'Executive Read-Only'
  }
  if (role === 'investigator') {
    return 'Investigator'
  }
  if (role === 'auditor') {
    return 'Auditor'
  }
  if (role === 'viewer') {
    return 'Viewer'
  }
  return 'Admin'
}

function runtimeRoleLabel(role: string) {
  if (role === 'api') {
    return 'API node'
  }
  if (role === 'worker') {
    return 'Worker node'
  }
  return 'Combined node'
}

function platformStateLabel(state: string) {
  if (state === 'active') {
    return 'Active'
  }
  if (state === 'configured') {
    return 'Configured'
  }
  if (state === 'error') {
    return 'Attention'
  }
  if (state === 'disabled') {
    return 'Disabled'
  }
  return 'Optional'
}

function jobLaneStateLabel(state: string) {
  if (state === 'running') {
    return 'Running'
  }
  if (state === 'scheduled') {
    return 'Scheduled'
  }
  if (state === 'attention') {
    return 'Attention'
  }
  if (state === 'disabled') {
    return 'Disabled'
  }
  return 'Idle'
}

function backgroundWorkerStateLabel(state: string) {
  if (state === 'local') {
    return 'Local worker'
  }
  if (state === 'remote') {
    return 'Remote worker'
  }
  if (state === 'standby') {
    return 'Standby'
  }
  return 'Missing worker'
}

function indexRefreshModeLabel(mode: string) {
  if (mode === 'delta') {
    return 'Delta'
  }
  if (mode === 'carry_forward') {
    return 'Carry-forward'
  }
  if (mode === 'existing') {
    return 'Existing'
  }
  return 'Full rebuild'
}

function graphProfileLimits(profile: GraphDensityProfile) {
  if (profile === 'expanded') {
    return { maxNodes: 280, maxEdges: 640 }
  }
  return { maxNodes: 120, maxEdges: 240 }
}

function reviewDecisionLabel(value: string) {
  if (value === 'keep') {
    return 'Keep'
  }
  if (value === 'revoke') {
    return 'Revoke'
  }
  if (value === 'needs_follow_up') {
    return 'Follow up'
  }
  return 'Pending'
}

const IMPORT_BUNDLE_TEMPLATE = `{
  "name": "Entra export",
  "source": "Microsoft Graph export",
  "environment": "cloud",
  "description": "Offline bundle imported without external credentials.",
  "entities": [
    {
      "id": "user_alice_cloud",
      "name": "alice.wong@contoso.com",
      "kind": "user",
      "source": "Microsoft Graph",
      "environment": "cloud",
      "description": "Cloud identity for Alice Wong.",
      "criticality": 2,
      "risk_score": 34,
      "tags": ["graph", "entra", "user"]
    }
  ],
  "relationships": [],
  "connectors": [],
  "insights": []
}`

function App() {
  const { locale, t, formatDateTime: formatLocaleDateTime } = useI18n()
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null)
  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null)
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusResponse | null>(null)
  const [authProviders, setAuthProviders] = useState<AuthProviderListResponse | null>(null)
  const [publicAuthProviders, setPublicAuthProviders] = useState<PublicAuthProviderListResponse | null>(null)
  const [targets, setTargets] = useState<ScanTarget[]>([])
  const [scans, setScans] = useState<ScanRunsResponse | null>(null)
  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [resourceAccess, setResourceAccess] = useState<ResourceAccessResponse | null>(null)
  const [resourceAccessLoading, setResourceAccessLoading] = useState(false)
  const [resourceAccessOffset, setResourceAccessOffset] = useState(0)
  const [resourceAccessPageSize, setResourceAccessPageSize] = useState(25)
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null)
  const [simulation, setSimulation] = useState<WhatIfResponse | null>(null)
  const [entityDetail, setEntityDetail] = useState<EntityDetailResponse | null>(null)
  const [blueprints, setBlueprints] = useState<ConnectorBlueprintResponse | null>(null)
  const [connectorRuntime, setConnectorRuntime] = useState<ConnectorRuntimeResponse | null>(null)
  const [connectorSupportMatrix, setConnectorSupportMatrix] =
    useState<ConnectorSupportMatrixResponse | null>(null)
  const [platformPosture, setPlatformPosture] = useState<PlatformPostureResponse | null>(null)
  const [exposureAnalytics, setExposureAnalytics] = useState<ExposureAnalyticsResponse | null>(null)
  const [queryPerformance, setQueryPerformance] = useState<QueryPerformanceResponse | null>(null)
  const [jobCenter, setJobCenter] = useState<JobCenterResponse | null>(null)
  const [riskFindings, setRiskFindings] = useState<RiskFindingsResponse | null>(null)
  const [recentChanges, setRecentChanges] = useState<ChangesResponse | null>(null)
  const [mfaStatus, setMfaStatus] = useState<MfaStatusResponse | null>(null)
  const [mfaSetup, setMfaSetup] = useState<MfaSetupResponse | null>(null)
  const [mvpReadiness, setMvpReadiness] = useState<MvpReadinessResponse | null>(null)
  const [featureInventory, setFeatureInventory] = useState<FeatureInventoryResponse | null>(null)
  const [operationalFlow, setOperationalFlow] = useState<OperationalFlowResponse | null>(null)
  const [auditEvents, setAuditEvents] = useState<AuditEventsResponse | null>(null)
  const [adminUsers, setAdminUsers] = useState<AdminUserListResponse | null>(null)
  const [workspaceInventory, setWorkspaceInventory] = useState<WorkspaceListResponse | null>(null)
  const [graphSubgraph, setGraphSubgraph] = useState<GraphSubgraphResponse | null>(null)
  const [showDenseGraph, setShowDenseGraph] = useState(false)
  const [graphDepth, setGraphDepth] = useState(1)
  const [graphDensityProfile, setGraphDensityProfile] = useState<GraphDensityProfile>('compact')
  const [accessReviews, setAccessReviews] = useState<AccessReviewCampaignListResponse | null>(null)
  const [selectedAccessReviewId, setSelectedAccessReviewId] = useState('')
  const [accessReviewDetail, setAccessReviewDetail] =
    useState<AccessReviewCampaignDetailResponse | null>(null)
  const [accessReviewRemediation, setAccessReviewRemediation] =
    useState<AccessReviewRemediationPlan | null>(null)
  const [importedSources, setImportedSources] = useState<ImportedSourceListResponse | null>(null)
  const [identityClusters, setIdentityClusters] = useState<IdentityClustersResponse | null>(null)
  const [identityClusterDetail, setIdentityClusterDetail] =
    useState<IdentityClusterDetailResponse | null>(null)
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null)
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('home')
  const [investigateSection, setInvestigateSection] =
    useState<InvestigateSection>('explain')
  const [governSection, setGovernSection] = useState<GovernSection>('reviews')
  const [sourcesSection, setSourcesSection] = useState<SourcesSection>('auth')
  const [operationsSection, setOperationsSection] = useState<OperationsSection>('status')
  const [selectedPrincipalId, setSelectedPrincipalId] = useState('')
  const [selectedResourceId, setSelectedResourceId] = useState('')
  const [selectedScenarioEdgeId, setSelectedScenarioEdgeId] = useState('')
  const [selectedClusterId, setSelectedClusterId] = useState('')
  const [scenarioFocusResourceId, setScenarioFocusResourceId] = useState<string | null>(null)
  const [focusedEntityId, setFocusedEntityId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [credentials, setCredentials] = useState({ username: 'admin', password: '' })
  const [selectedPasswordProvider, setSelectedPasswordProvider] = useState('')
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '' })
  const [mfaChallenge, setMfaChallenge] = useState<{
    username: string
    authSource: string
    challengeToken: string
  } | null>(null)
  const [mfaChallengeCode, setMfaChallengeCode] = useState('')
  const [mfaSetupCode, setMfaSetupCode] = useState('')
  const [mfaDisableForm, setMfaDisableForm] = useState({ currentPassword: '', code: '' })
  const [setupDraft, setSetupDraft] = useState({
    tenant_name: '',
    username: 'admin',
    password: '',
  })
  const [workspaceDraft, setWorkspaceDraft] = useState<{
    name: string
    slug: string
    description: string
    environment: 'on-prem' | 'cloud' | 'hybrid'
  }>({
    name: '',
    slug: '',
    description: '',
    environment: 'on-prem',
  })
  const [workspaceEditDraft, setWorkspaceEditDraft] = useState<{
    name: string
    description: string
    environment: 'on-prem' | 'cloud' | 'hybrid'
  }>({
    name: '',
    description: '',
    environment: 'on-prem',
  })
  const [authProviderDraft, setAuthProviderDraft] = useState<{
    name: string
    kind: 'ldap' | 'oidc'
    preset: AuthProviderPreset
    enabled: boolean
    description: string
    ldap_server_uri: string
    ldap_base_dn: string
    ldap_bind_dn: string
    ldap_bind_password_env: string
    ldap_user_search_filter: string
    allowed_groups: string
    issuer_url: string
    discovery_url: string
    client_id: string
    client_secret_env: string
    allowed_domains: string
    allowed_emails: string
    scopes: string
  }>({
    name: '',
    kind: 'oidc',
    preset: 'microsoft',
    enabled: true,
    description: '',
    ldap_server_uri: '',
    ldap_base_dn: '',
    ldap_bind_dn: '',
    ldap_bind_password_env: '',
    ldap_user_search_filter: '',
    allowed_groups: '',
    issuer_url: '',
    discovery_url: '',
    client_id: '',
    client_secret_env: '',
    allowed_domains: '',
    allowed_emails: '',
    scopes: '',
  })
  const [targetDraft, setTargetDraft] = useState<{
    name: string
    path: string
    platform: 'auto' | 'windows' | 'linux'
    connection_mode: 'local' | 'ssh'
    host: string
    port: number
    username: string
    secret_env: string
    key_path: string
    recursive: boolean
    max_depth: number
    max_entries: number
    include_hidden: boolean
    enabled: boolean
    notes: string
  }>({
    name: '',
    path: '',
    platform: 'auto' as const,
    connection_mode: 'local' as const,
    host: '',
    port: 22,
    username: '',
    secret_env: '',
    key_path: '',
    recursive: true,
    max_depth: 2,
    max_entries: 400,
    include_hidden: false,
    enabled: true,
    notes: '',
  })
  const [booting, setBooting] = useState(true)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [importDraft, setImportDraft] = useState(IMPORT_BUNDLE_TEMPLATE)
  const [accessReviewDraft, setAccessReviewDraft] = useState({
    name: 'Quarterly privileged access review',
    description: 'Focus on high-risk and privileged effective access paths.',
    min_risk_score: 75,
    privileged_only: true,
    max_items: 20,
  })

  const deferredSearchQuery = useDeferredValue(searchQuery)
  function clearWorkspaceState() {
    setRuntimeStatus(null)
    setTargets([])
    setScans(null)
    setOverview(null)
    setCatalog(null)
    setBlueprints(null)
    setConnectorRuntime(null)
    setConnectorSupportMatrix(null)
    setMvpReadiness(null)
    setFeatureInventory(null)
    setOperationalFlow(null)
    setExposureAnalytics(null)
    setQueryPerformance(null)
    setJobCenter(null)
    setAuditEvents(null)
    setAdminUsers(null)
    setWorkspaceInventory(null)
    setGraphSubgraph(null)
    setShowDenseGraph(false)
    setGraphDepth(1)
    setGraphDensityProfile('compact')
    setImportedSources(null)
    setIdentityClusters(null)
    setIdentityClusterDetail(null)
    setAuthProviders(null)
    setResourceAccess(null)
    setResourceAccessLoading(false)
    setResourceAccessOffset(0)
    setResourceAccessPageSize(25)
    setExplanation(null)
    setSimulation(null)
    setEntityDetail(null)
    setBenchmark(null)
    setSearchQuery('')
  }

  function setSignedOutSession(setupRequired: boolean) {
    setMfaChallenge(null)
    setMfaStatus(null)
    setMfaSetup(null)
    setMfaSetupCode('')
    setMfaDisableForm({ currentPassword: '', code: '' })
    setSession({
      authenticated: false,
      roles: [],
      capabilities: [],
      setup_required: setupRequired,
      must_change_password: false,
      bootstrap,
    })
    clearWorkspaceState()
  }

  function uiErrorMessage(err: unknown, fallback: string) {
    return err instanceof Error && err.message ? err.message : t(fallback)
  }

  function hasCapability(capability: string) {
    return Boolean(session?.capabilities?.includes(capability) || session?.capabilities?.includes('admin.manage'))
  }

  function uiMessage(message: string | null) {
    if (!message) {
      return null
    }

    const legacyMessageMap: Record<string, string> = {
      'Setup completato. Workspace pronto.': t(
        'Initial setup completed. The workspace is now ready for your first scan.',
      ),
      'Password aggiornata. Effettua di nuovo il login.': t(
        'Password updated. Sign in again to continue.',
      ),
      'Chiave MFA generata. Aggiungila nel tuo autenticatore e conferma con un codice TOTP.':
        t(
          'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.',
        ),
      "Verifica il codice del tuo autenticatore per completare l'accesso.": t(
        'Check your authenticator code to complete the sign-in.',
      ),
      'Verifica il codice del tuo autenticatore per completare l’accesso.': t(
        'Check your authenticator code to complete the sign-in.',
      ),
      "MFA attivata con successo per l'account locale.": t(
        'MFA enabled successfully for the local account.',
      ),
      'MFA attivata con successo per l’account locale.': t(
        'MFA enabled successfully for the local account.',
      ),
      'MFA attivata con successo per lâ€™account locale.': t(
        'MFA enabled successfully for the local account.',
      ),
    }

    return legacyMessageMap[message] ?? message
  }

  function ensureCapability(capability: string, message: string) {
    if (hasCapability(capability)) {
      return true
    }
    setError(t(message))
    return false
  }

  const workspaceViews = WORKSPACE_VIEWS.map((view) => ({
    ...view,
    label: t(view.label),
    title: t(view.title),
    description: t(view.description),
  }))
  const investigateSections = INVESTIGATE_SECTIONS.map((section) => ({
    ...section,
    label: t(section.label),
  }))
  const governSections = GOVERN_SECTIONS.map((section) => ({
    ...section,
    label: t(section.label),
  }))
  const sourcesSections = SOURCES_SECTIONS.map((section) => ({
    ...section,
    label: t(section.label),
  }))
  const operationsSections = OPERATIONS_SECTIONS.map((section) => ({
    ...section,
    label: t(section.label),
  }))
  const scenarioOptions = catalog?.scenarios ?? overview?.scenarios ?? []
  const principalOptions = catalog?.principals ?? []
  const resourceOptions = catalog?.resources ?? []
  const activeScenario =
    scenarioOptions.find((scenario) => scenario.edge_id === selectedScenarioEdgeId) ?? null
  const activeWorkspaceView =
    workspaceViews.find((view) => view.id === workspaceView) ?? workspaceViews[0]
  const showHomeView = workspaceView === 'home'
  const showInvestigateView = workspaceView === 'investigate'
  const showGovernView = workspaceView === 'govern'
  const showSourcesView = workspaceView === 'sources'
  const showOperationsView = workspaceView === 'operations'
  const canSimulate = hasCapability('investigate.simulate')
  const canManageGovernance = hasCapability('governance.manage')
  const canManageSources = hasCapability('sources.manage')
  const canManageAdmins = hasCapability('admin.manage')
  const secondaryTabs = showInvestigateView
    ? investigateSections
    : showSourcesView
    ? sourcesSections
    : showGovernView
      ? governSections
      : showOperationsView
        ? operationsSections
        : []
  const topHotspots = overview?.hotspots.slice(0, 4) ?? []
  const topInsights = overview?.insights.slice(0, 4) ?? []
  const recentHistory = overview?.history.slice(-4) ?? []
  const toneLabelValue = (tone: Tone) => t(toneLabel(tone))
  const kindLabelValue = (kind: string) => t(kindLabel(kind))

  function handleSelectWorkspace(nextViewId: string) {
    const nextView = nextViewId as WorkspaceView
    setWorkspaceView(nextView)
    if (nextView === 'investigate') {
      setInvestigateSection('explain')
      return
    }
    if (nextView === 'govern') {
      setGovernSection('reviews')
      return
    }
    if (nextView === 'sources') {
      setSourcesSection('auth')
      return
    }
    if (nextView === 'operations') {
      setOperationsSection('status')
    }
  }

  function activeSecondaryTabId() {
    if (showInvestigateView) {
      return investigateSection
    }
    if (showSourcesView) {
      return sourcesSection
    }
    if (showGovernView) {
      return governSection
    }
    if (showOperationsView) {
      return operationsSection
    }
    return null
  }

  function handleSelectSecondaryTab(tabId: string) {
    if (showInvestigateView) {
      setInvestigateSection(tabId as InvestigateSection)
    } else if (showSourcesView) {
      setSourcesSection(tabId as SourcesSection)
    } else if (showGovernView) {
      setGovernSection(tabId as GovernSection)
    } else if (showOperationsView) {
      setOperationsSection(tabId as OperationsSection)
    }
  }

  function openWorkspaceDestination(workspace: string, section?: string | null) {
    handleSelectWorkspace(workspace)
    if (!section) {
      return
    }
    if (workspace === 'investigate') {
      setInvestigateSection(section as InvestigateSection)
    } else if (workspace === 'sources') {
      setSourcesSection(section as SourcesSection)
    } else if (workspace === 'govern') {
      setGovernSection(section as GovernSection)
    } else if (workspace === 'operations') {
      setOperationsSection(section as OperationsSection)
    }
  }

  async function loadWorkspace() {
    const [
      runtimePayload,
      workspacesPayload,
      authProvidersPayload,
      targetsPayload,
      scansPayload,
      overviewPayload,
      catalogPayload,
      blueprintPayload,
      connectorRuntimePayload,
      connectorSupportMatrixPayload,
      platformPosturePayload,
      exposureAnalyticsPayload,
      queryPerformancePayload,
      riskFindingsPayload,
      recentChangesPayload,
      mfaStatusPayload,
      mvpReadinessPayload,
      featureInventoryPayload,
      operationalFlowPayload,
      jobCenterPayload,
      auditEventsPayload,
      accessReviewsPayload,
      importedSourcesPayload,
      identityClustersPayload,
    ] = await Promise.all([
      fetchRuntimeStatus(),
      fetchWorkspaces(),
      fetchAuthProviders(),
      fetchTargets(),
      fetchScans(),
      fetchOverview(),
      fetchCatalog(),
      fetchConnectorBlueprints(),
      fetchConnectorRuntime(),
      fetchConnectorSupportMatrix(),
      fetchPlatformPosture(),
      fetchExposureAnalytics(),
      fetchQueryPerformance(),
      fetchRisks(),
      fetchChanges(),
      fetchMfaStatus(),
      fetchMvpReadiness(),
      fetchFeatureInventory(),
      fetchOperationalFlow(),
      fetchJobCenter(),
      fetchAuditEvents(20),
      fetchAccessReviews(),
      fetchImportedSources(),
      fetchIdentityClusters(),
    ])

    setRuntimeStatus(runtimePayload)
    setWorkspaceInventory(workspacesPayload)
    setAuthProviders(authProvidersPayload)
    setTargets(targetsPayload)
    setScans(scansPayload)
    setOverview(overviewPayload)
    setCatalog(catalogPayload)
    setBlueprints(blueprintPayload)
    setConnectorRuntime(connectorRuntimePayload)
    setConnectorSupportMatrix(connectorSupportMatrixPayload)
    setPlatformPosture(platformPosturePayload)
    setExposureAnalytics(exposureAnalyticsPayload)
    setQueryPerformance(queryPerformancePayload)
    setRiskFindings(riskFindingsPayload)
    setRecentChanges(recentChangesPayload)
    setMfaStatus(mfaStatusPayload)
    setMvpReadiness(mvpReadinessPayload)
    setFeatureInventory(featureInventoryPayload)
    setOperationalFlow(operationalFlowPayload)
    setJobCenter(jobCenterPayload)
    setAuditEvents(auditEventsPayload)
    setAccessReviews(accessReviewsPayload)
    setImportedSources(importedSourcesPayload)
    setIdentityClusters(identityClustersPayload)
    const activeWorkspace =
      workspacesPayload.workspaces.find(
        (workspace) => workspace.id === workspacesPayload.active_workspace_id,
      ) ?? null
    if (activeWorkspace) {
      setWorkspaceEditDraft({
        name: activeWorkspace.name,
        description: activeWorkspace.description ?? '',
        environment: activeWorkspace.environment,
      })
    }

    const nextPrincipalId =
      overviewPayload.default_principal_id ?? catalogPayload.principals[0]?.id ?? ''
    const nextResourceId =
      overviewPayload.default_resource_id ?? catalogPayload.resources[0]?.id ?? ''
    const nextScenarioId =
      overviewPayload.default_scenario_edge_id ?? catalogPayload.scenarios[0]?.edge_id ?? ''
    const nextScenario =
      catalogPayload.scenarios.find((scenario) => scenario.edge_id === nextScenarioId) ?? null

    setSelectedPrincipalId((current) =>
      catalogPayload.principals.some((principal) => principal.id === current)
        ? current
        : nextPrincipalId,
    )
    setSelectedResourceId((current) =>
      catalogPayload.resources.some((resource) => resource.id === current)
        ? current
        : nextResourceId,
    )
    setSelectedScenarioEdgeId((current) =>
      catalogPayload.scenarios.some((scenario) => scenario.edge_id === current)
        ? current
        : nextScenarioId,
    )
    setSelectedClusterId((current) =>
      identityClustersPayload.clusters.some((cluster) => cluster.id === current)
        ? current
        : (identityClustersPayload.clusters[0]?.id ?? ''),
    )
    setSelectedAccessReviewId((current) =>
      accessReviewsPayload.campaigns.some((campaign) => campaign.id === current)
        ? current
        : (accessReviewsPayload.campaigns[0]?.id ?? ''),
    )
    setScenarioFocusResourceId((current) =>
      catalogPayload.resources.some((resource) => resource.id === current)
        ? current
        : (nextScenario?.focus_resource_id ?? nextResourceId ?? null),
    )
    setFocusedEntityId((current) => current || nextResourceId || nextPrincipalId || null)
  }

  useEffect(() => {
    let active = true

    async function bootstrapApp() {
      try {
        const [sessionPayload, initialSetupStatus, publicProvidersPayload] = await Promise.all([
          fetchSession(),
          fetchSetupStatus(),
          fetchPublicAuthProviders(),
        ])
        if (!active) {
          return
        }

        setSession(sessionPayload)
        setBootstrap(sessionPayload.bootstrap ?? null)
        setSetupStatus(initialSetupStatus)
        setPublicAuthProviders(publicProvidersPayload)

        if (
          sessionPayload.authenticated &&
          !sessionPayload.must_change_password &&
          !sessionPayload.setup_required
        ) {
          await loadWorkspace()
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to load the platform.')
        }
      } finally {
        if (active) {
          setBooting(false)
        }
      }
    }

    void bootstrapApp()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (deferredSearchQuery.trim().length < 2 || !session?.authenticated) {
      setSearchResults([])
      return
    }

    let active = true
    setSearchLoading(true)
    void fetchSearch(deferredSearchQuery)
      .then((results) => {
        if (active) {
          setSearchResults(results)
        }
      })
      .catch(() => {
        if (active) {
          setSearchResults([])
        }
      })
      .finally(() => {
        if (active) {
          setSearchLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [deferredSearchQuery, session?.authenticated])

  useEffect(() => {
    if (!session?.authenticated || !selectedResourceId) {
      setResourceAccess(null)
      setResourceAccessLoading(false)
      return
    }

    let active = true
    setResourceAccessLoading(true)
    void fetchResourceAccess(selectedResourceId, {
      limit: resourceAccessPageSize,
      offset: resourceAccessOffset,
    })
      .then((payload) => {
        if (active) {
          setResourceAccess(payload)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to load resource access.')
        }
      })
      .finally(() => {
        if (active) {
          setResourceAccessLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [resourceAccessOffset, resourceAccessPageSize, selectedResourceId, session?.authenticated])

  useEffect(() => {
    setResourceAccessOffset(0)
  }, [selectedResourceId])

  useEffect(() => {
    if (!session?.authenticated || !selectedPrincipalId || !selectedResourceId) {
      setExplanation(null)
      return
    }

    let active = true
    void fetchExplanation(selectedPrincipalId, selectedResourceId)
      .then((payload) => {
        if (active) {
          setExplanation(payload)
        }
      })
      .catch((err) => {
        if (active) {
          setExplanation(null)
          setError(err instanceof Error ? err.message : 'Unable to explain access.')
        }
      })

    return () => {
      active = false
    }
  }, [selectedPrincipalId, selectedResourceId, session?.authenticated])

  useEffect(() => {
    if (!session?.authenticated || !selectedScenarioEdgeId || !canSimulate) {
      setSimulation(null)
      return
    }

    let active = true
    void fetchWhatIf(selectedScenarioEdgeId, scenarioFocusResourceId)
      .then((payload) => {
        if (active) {
          setSimulation(payload)
        }
      })
      .catch((err) => {
        if (active) {
          setSimulation(null)
          setError(err instanceof Error ? err.message : 'Unable to simulate the scenario.')
        }
      })

    return () => {
      active = false
    }
  }, [canSimulate, scenarioFocusResourceId, selectedScenarioEdgeId, session?.authenticated])

  useEffect(() => {
    if (!session?.authenticated || !focusedEntityId || !showDenseGraph) {
      setGraphSubgraph(null)
      return
    }

    const { maxNodes, maxEdges } = graphProfileLimits(graphDensityProfile)
    let active = true
    void fetchGraphSubgraph(focusedEntityId, graphDepth, { maxNodes, maxEdges })
      .then((payload) => {
        if (active) {
          setGraphSubgraph(payload)
        }
      })
      .catch(() => {
        if (active) {
          setGraphSubgraph(null)
        }
      })
    void fetchEntityDetail(focusedEntityId)
      .then((payload) => {
        if (active) {
          setEntityDetail(payload)
        }
      })
      .catch(() => {
        if (active) {
          setEntityDetail(null)
        }
      })

    return () => {
      active = false
    }
  }, [focusedEntityId, graphDensityProfile, graphDepth, session?.authenticated, showDenseGraph])

  useEffect(() => {
    if (!session?.authenticated || !selectedClusterId) {
      setIdentityClusterDetail(null)
      return
    }

    let active = true
    void fetchIdentityClusterDetail(selectedClusterId)
      .then((payload) => {
        if (active) {
          setIdentityClusterDetail(payload)
        }
      })
      .catch(() => {
        if (active) {
          setIdentityClusterDetail(null)
        }
      })

    return () => {
      active = false
    }
  }, [selectedClusterId, session?.authenticated])

  useEffect(() => {
    if (!session?.authenticated || !selectedAccessReviewId) {
      setAccessReviewDetail(null)
      setAccessReviewRemediation(null)
      return
    }

    let active = true
    void fetchAccessReview(selectedAccessReviewId)
      .then((payload) => {
        if (active) {
          setAccessReviewDetail(payload)
          setAccessReviewRemediation(null)
        }
      })
      .catch(() => {
        if (active) {
          setAccessReviewDetail(null)
          setAccessReviewRemediation(null)
        }
      })

    return () => {
      active = false
    }
  }, [selectedAccessReviewId, session?.authenticated])

  useEffect(() => {
    if (!session?.authenticated || !canManageAdmins) {
      setAdminUsers(null)
      return
    }

    let active = true
    void fetchAdminUsers()
      .then((payload) => {
        if (active) {
          setAdminUsers(payload)
        }
      })
      .catch((err) => {
        if (active) {
          setAdminUsers(null)
          setError(err instanceof Error ? err.message : 'Unable to load administrator roles.')
        }
      })

    return () => {
      active = false
    }
  }, [canManageAdmins, session?.authenticated])

  function handleSearchSelect(result: SearchResult) {
    startTransition(() => {
      setWorkspaceView('investigate')
      setInvestigateSection('explain')
      setFocusedEntityId(result.entity.id)
      setSearchQuery(result.entity.name)
      if (result.entity.kind === 'resource') {
        setSelectedResourceId(result.entity.id)
        setScenarioFocusResourceId(result.entity.id)
      } else {
        setSelectedPrincipalId(result.entity.id)
      }
    })
  }

  function handleScenarioChange(nextEdgeId: string) {
    const nextScenario =
      scenarioOptions.find((scenario) => scenario.edge_id === nextEdgeId) ?? null
    startTransition(() => {
      setSelectedScenarioEdgeId(nextEdgeId)
      setScenarioFocusResourceId(nextScenario?.focus_resource_id ?? selectedResourceId)
    })
  }

  async function handleCreateAccessReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('governance.manage', 'Your application role cannot create access reviews.')) {
      return
    }
    setBusyAction('create-access-review')
    setError(null)
    try {
      const detail = await createAccessReview(accessReviewDraft)
      const campaigns = await fetchAccessReviews()
      setAccessReviews(campaigns)
      setAccessReviewDetail(detail)
      setSelectedAccessReviewId(detail.summary.id)
      setWorkspaceView('govern')
      setGovernSection('reviews')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create the access review.')
    } finally {
      setBusyAction(null)
    }
  }

  async function handleAccessReviewDecision(
    itemId: string,
    decision: 'keep' | 'revoke' | 'needs_follow_up',
  ) {
    if (!selectedAccessReviewId) {
      return
    }
    if (
      !ensureCapability(
        'governance.manage',
        'Your application role cannot change access review decisions.',
      )
    ) {
      return
    }
    setBusyAction(`review-decision-${itemId}-${decision}`)
    setError(null)
    try {
      const detail = await updateAccessReviewDecision(selectedAccessReviewId, itemId, {
        decision,
      })
      setAccessReviewDetail(detail)
      setAccessReviews(await fetchAccessReviews())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update the review decision.')
    } finally {
      setBusyAction(null)
    }
  }

  async function handleOpenRemediation(itemId: string) {
    if (!selectedAccessReviewId) {
      return
    }
    setBusyAction(`review-remediation-${itemId}`)
    setError(null)
    try {
      const remediation = await fetchAccessReviewRemediation(selectedAccessReviewId, itemId)
      setAccessReviewRemediation(remediation)
      setWorkspaceView('govern')
      setGovernSection('remediation')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load the remediation plan.')
    } finally {
      setBusyAction(null)
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusyAction('login')
    setError(null)
    setNotice(null)
    try {
      const payload = await login(
        credentials.username,
        credentials.password,
        selectedPasswordProvider || undefined,
      )
      if (payload.mfa_required && payload.mfa_challenge_token && payload.username) {
        setMfaChallenge({
          username: payload.username,
          authSource: payload.auth_source ?? 'local',
          challengeToken: payload.mfa_challenge_token,
        })
        setMfaChallengeCode('')
        setCredentials((current) => ({ ...current, password: '' }))
        setNotice('Verifica il codice del tuo autenticatore per completare l’accesso.')
        setNotice(t('Check your authenticator code to complete the sign-in.'))
        return
      }
      setMfaChallenge(null)
      setSession(payload)
      setBootstrap(payload.bootstrap ?? null)
      if (!payload.must_change_password && !payload.setup_required) {
        await loadWorkspace()
      }
      setCredentials((current) => ({ ...current, password: '' }))
    } catch (err) {
      setError(uiErrorMessage(err, 'Login failed.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSetupLocalAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusyAction('setup-admin')
    setError(null)
    setNotice(null)
    try {
      await setupLocalAdmin({
        tenant_name: setupDraft.tenant_name || undefined,
        username: setupDraft.username,
        password: setupDraft.password,
      })
      const sessionPayload = await login(setupDraft.username, setupDraft.password)
      setSession(sessionPayload)
      setBootstrap(sessionPayload.bootstrap ?? null)
      setSetupStatus({
        setup_required: false,
        local_admin_configured: true,
        auth_provider_count: authProviders?.providers.length ?? 0,
        tenant_name: setupDraft.tenant_name || setupStatus?.tenant_name || PRODUCT_DEFAULT_TENANT_NAME,
        recommended_flow: 'Platform initialized. You can now configure LDAP or OAuth2 sign-in providers.',
      })
      await loadWorkspace()
      setNotice('Setup completato. Workspace pronto.')
      setNotice(
        t('Initial setup completed. The workspace is now ready for your first scan.'),
      )
      setCredentials({ username: setupDraft.username, password: '' })
      setSetupDraft((current) => ({ ...current, password: '' }))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to complete the initial setup.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusyAction('password')
    setError(null)
    setNotice(null)
    try {
      await changePassword(passwordForm.current, passwordForm.next)
      const payload = await fetchSession()
      setSession(payload)
      setPasswordForm({ current: '', next: '' })
      setNotice('Password aggiornata. Effettua di nuovo il login.')
      setNotice(t('Password updated. Sign in again to continue.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Password change failed.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleVerifyMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!mfaChallenge) {
      return
    }
    setBusyAction('mfa-verify')
    setError(null)
    setNotice(null)
    try {
      const payload = await verifyMfaChallenge(mfaChallenge.challengeToken, mfaChallengeCode)
      setMfaChallenge(null)
      setSession(payload)
      setBootstrap(payload.bootstrap ?? null)
      setMfaChallengeCode('')
      if (!payload.must_change_password && !payload.setup_required) {
        await loadWorkspace()
      }
    } catch (err) {
      setError(uiErrorMessage(err, 'MFA verification failed.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleBeginMfaSetup() {
    setBusyAction('mfa-setup')
    setError(null)
    setNotice(null)
    try {
      setWorkspaceView('sources')
      setSourcesSection('auth')
      const payload = await beginMfaSetup()
      setMfaSetup(payload)
      const statusPayload = await fetchMfaStatus()
      setMfaStatus(statusPayload)
      setNotice('Chiave MFA generata. Aggiungila nel tuo autenticatore e conferma con un codice TOTP.')
      setNotice(
        t(
          'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.',
        ),
      )
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to prepare MFA setup.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleConfirmMfaSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusyAction('mfa-enable')
    setError(null)
    setNotice(null)
    try {
      await confirmMfaSetup(mfaSetupCode)
      const statusPayload = await fetchMfaStatus()
      setMfaStatus(statusPayload)
      setSession((current) => (current ? { ...current, mfa_enabled: true } : current))
      setMfaSetup(null)
      setMfaSetupCode('')
      setNotice(t('MFA enabled successfully for the local account.'))
      setNotice('MFA attivata con successo per l’account locale.')
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to enable MFA.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleDisableMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusyAction('mfa-disable')
    setError(null)
    setNotice(null)
    try {
      await disableMfa(mfaDisableForm.currentPassword, mfaDisableForm.code)
      setMfaSetup(null)
      setMfaSetupCode('')
      setMfaDisableForm({ currentPassword: '', code: '' })
      setMfaStatus(null)
      setSignedOutSession(false)
      setNotice(t('MFA disabled. Sign in again to continue.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to disable MFA.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleLogout() {
    setBusyAction('logout')
    try {
      await logout()
      setSignedOutSession(setupStatus?.setup_required ?? false)
      setNotice(null)
    } finally {
      setBusyAction(null)
    }
  }

  function buildAuthProviderConfig(): AuthProviderConfig {
    if (authProviderDraft.kind === 'ldap') {
      return {
        kind: 'ldap',
        preset: 'custom',
        description: authProviderDraft.description || null,
        ldap_server_uri: authProviderDraft.ldap_server_uri || null,
        ldap_base_dn: authProviderDraft.ldap_base_dn || null,
        ldap_bind_dn: authProviderDraft.ldap_bind_dn || null,
        ldap_bind_password_env: authProviderDraft.ldap_bind_password_env || null,
        ldap_user_search_filter: authProviderDraft.ldap_user_search_filter || null,
        allowed_groups: authProviderDraft.allowed_groups
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        issuer_url: null,
        discovery_url: null,
        client_id: null,
        client_secret_env: null,
        scopes: [],
        allowed_domains: [],
        allowed_emails: [],
        username_attribute: null,
        email_attribute: null,
        start_tls: false,
      }
    }
    return {
      kind: 'oidc',
      preset: authProviderDraft.preset,
      description: authProviderDraft.description || null,
      issuer_url: authProviderDraft.issuer_url || null,
      discovery_url: authProviderDraft.discovery_url || null,
      client_id: authProviderDraft.client_id || null,
      client_secret_env: authProviderDraft.client_secret_env || null,
      scopes: authProviderDraft.scopes
        .split(/[,\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
      allowed_domains: authProviderDraft.allowed_domains
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      allowed_emails: authProviderDraft.allowed_emails
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      username_attribute: null,
      email_attribute: null,
      ldap_server_uri: null,
      ldap_base_dn: null,
      ldap_bind_dn: null,
      ldap_bind_password_env: null,
      ldap_user_search_filter: null,
      allowed_groups: [],
      start_tls: false,
    }
  }

  async function handleCreateAuthProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('sources.manage', 'Your application role cannot manage sign-in providers.')) {
      return
    }
    setBusyAction('create-auth-provider')
    setError(null)
    setNotice(null)
    try {
      await createAuthProvider({
        name: authProviderDraft.name,
        enabled: authProviderDraft.enabled,
        config: buildAuthProviderConfig(),
      })
      setAuthProviderDraft({
        name: '',
        kind: 'oidc',
        preset: 'microsoft',
        enabled: true,
        description: '',
        ldap_server_uri: '',
        ldap_base_dn: '',
        ldap_bind_dn: '',
        ldap_bind_password_env: '',
        ldap_user_search_filter: '',
        allowed_groups: '',
        issuer_url: '',
        discovery_url: '',
        client_id: '',
        client_secret_env: '',
        allowed_domains: '',
        allowed_emails: '',
        scopes: '',
      })
      setPublicAuthProviders(await fetchPublicAuthProviders())
      setAuthProviders(await fetchAuthProviders())
      setNotice(t('Authentication provider created. You can now enable it for sign-in.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to create the auth provider.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleToggleAuthProvider(providerId: string, enabled: boolean) {
    if (!ensureCapability('sources.manage', 'Your application role cannot manage sign-in providers.')) {
      return
    }
    setBusyAction(`toggle-auth-provider-${providerId}`)
    setError(null)
    setNotice(null)
    try {
      await updateAuthProvider(providerId, { enabled: !enabled })
      setPublicAuthProviders(await fetchPublicAuthProviders())
      setAuthProviders(await fetchAuthProviders())
      setNotice(
        enabled
          ? t('Authentication provider disabled.')
          : t('Authentication provider enabled.'),
      )
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to update the auth provider.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleDeleteAuthProvider(providerId: string) {
    if (!ensureCapability('sources.manage', 'Your application role cannot manage sign-in providers.')) {
      return
    }
    setBusyAction(`delete-auth-provider-${providerId}`)
    setError(null)
    setNotice(null)
    try {
      await deleteAuthProvider(providerId)
      setPublicAuthProviders(await fetchPublicAuthProviders())
      setAuthProviders(await fetchAuthProviders())
      setNotice(t('Authentication provider removed.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to delete the auth provider.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleActivateWorkspace(workspaceId: string) {
    if (!ensureCapability('admin.manage', 'Your application role cannot manage workspaces.')) {
      return
    }
    if (!workspaceId || workspaceId === session?.active_workspace_id) {
      return
    }
    setBusyAction(`activate-workspace-${workspaceId}`)
    setError(null)
    setNotice(null)
    try {
      await activateWorkspace(workspaceId)
      const sessionPayload = await fetchSession()
      setSession(sessionPayload)
      setBootstrap(sessionPayload.bootstrap ?? null)
      await loadWorkspace()
      setWorkspaceView('home')
      setNotice(t('Workspace activated. The control plane has been refreshed.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to activate the workspace.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleCreateWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('admin.manage', 'Your application role cannot manage workspaces.')) {
      return
    }
    setBusyAction('create-workspace')
    setError(null)
    setNotice(null)
    try {
      await createWorkspace({
        name: workspaceDraft.name,
        slug: workspaceDraft.slug || undefined,
        description: workspaceDraft.description || undefined,
        environment: workspaceDraft.environment,
      })
      setWorkspaceDraft({
        name: '',
        slug: '',
        description: '',
        environment: 'on-prem',
      })
      await loadWorkspace()
      setNotice(
        t(
          'Workspace created. Switch to it when you are ready to isolate another organization or environment.',
        ),
      )
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to create the workspace.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleUpdateWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('admin.manage', 'Your application role cannot manage workspaces.')) {
      return
    }
    if (!session?.active_workspace_id) {
      return
    }
    setBusyAction('update-workspace')
    setError(null)
    setNotice(null)
    try {
      await updateWorkspace(session.active_workspace_id, {
        name: workspaceEditDraft.name,
        description: workspaceEditDraft.description || undefined,
        environment: workspaceEditDraft.environment,
      })
      const sessionPayload = await fetchSession()
      setSession(sessionPayload)
      setBootstrap(sessionPayload.bootstrap ?? null)
      await loadWorkspace()
      setNotice(t('Workspace details updated.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to update the workspace.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleToggleAdminRole(username: string, role: AppRole, enabled: boolean) {
    if (!ensureCapability('admin.manage', 'Your application role cannot manage administrator roles.')) {
      return
    }
    const currentRoles = adminUsers?.users.find((item) => item.username === username)?.roles ?? []
    const nextRoles = enabled
      ? currentRoles.filter((item) => item !== role)
      : [...currentRoles, role]
    setBusyAction(`admin-role-${username}-${role}`)
    setError(null)
    setNotice(null)
    try {
      await updateAdminUserRoles(username, nextRoles)
      setAdminUsers(await fetchAdminUsers())
      const sessionPayload = await fetchSession()
      setSession(sessionPayload)
      setNotice(
        enabled
          ? t('Administrator role removed.')
          : t('Administrator role assigned.'),
      )
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to update administrator roles.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleRunScan(targetId?: string) {
    if (!ensureCapability('sources.manage', 'Your application role cannot run collection scans.')) {
      return
    }
    setBusyAction(targetId ? `scan-${targetId}` : 'scan-all')
    setError(null)
    setNotice(null)
    try {
      if (targetId) {
        await runTargetScan(targetId)
      } else {
        await runScan()
      }
      setBenchmark(null)
      await loadWorkspace()
      setNotice(
        targetId
          ? t('Target scan completed. The workspace has been refreshed with the latest data.')
          : t('Full scan completed. The workspace has been refreshed with the latest data.'),
      )
    } catch (err) {
      setError(uiErrorMessage(err, 'Scan failed.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleToggleTarget(target: ScanTarget) {
    if (!ensureCapability('sources.manage', 'Your application role cannot manage monitored targets.')) {
      return
    }
    setBusyAction(`toggle-${target.id}`)
    setError(null)
    setNotice(null)
    try {
      await updateTarget(target.id, { enabled: !target.enabled })
      setBenchmark(null)
      await loadWorkspace()
      setNotice(target.enabled ? t('Target disabled.') : t('Target enabled.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to update target.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleCreateTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('sources.manage', 'Your application role cannot manage monitored targets.')) {
      return
    }
    setBusyAction('create-target')
    setError(null)
    setNotice(null)
    try {
      await createTarget({
        ...targetDraft,
        host: targetDraft.connection_mode === 'ssh' ? targetDraft.host || undefined : undefined,
        username:
          targetDraft.connection_mode === 'ssh' ? targetDraft.username || undefined : undefined,
        secret_env:
          targetDraft.connection_mode === 'ssh' ? targetDraft.secret_env || undefined : undefined,
        key_path:
          targetDraft.connection_mode === 'ssh' ? targetDraft.key_path || undefined : undefined,
        notes: targetDraft.notes || undefined,
      })
      setTargetDraft({
        name: '',
        path: '',
        platform: 'auto',
        connection_mode: 'local',
        host: '',
        port: 22,
        username: '',
        secret_env: '',
        key_path: '',
        recursive: true,
        max_depth: 2,
        max_entries: 400,
        include_hidden: false,
        enabled: true,
        notes: '',
      })
      setBenchmark(null)
      await loadWorkspace()
      setNotice(t('Target added. Run a scan when you are ready to collect live data.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to add target.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleImportSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ensureCapability('sources.manage', 'Your application role cannot manage imported sources.')) {
      return
    }
    setBusyAction('import-source')
    setError(null)
    try {
      const parsed = JSON.parse(importDraft)
      await createImportedSource(parsed)
      setImportDraft('')
      setBenchmark(null)
      await loadWorkspace()
      setNotice(t('Source bundle imported and merged into the workspace.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to import the source bundle.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleToggleImportedSource(sourceId: string, enabled: boolean) {
    if (!ensureCapability('sources.manage', 'Your application role cannot manage imported sources.')) {
      return
    }
    setBusyAction(`import-toggle-${sourceId}`)
    setError(null)
    try {
      await updateImportedSource(sourceId, { enabled: !enabled })
      setBenchmark(null)
      await loadWorkspace()
      setNotice(enabled ? t('Imported source disabled.') : t('Imported source enabled.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to update imported source.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleDeleteImportedSource(sourceId: string) {
    if (!ensureCapability('sources.manage', 'Your application role cannot manage imported sources.')) {
      return
    }
    setBusyAction(`import-delete-${sourceId}`)
    setError(null)
    try {
      await deleteImportedSource(sourceId)
      setBenchmark(null)
      await loadWorkspace()
      setNotice(t('Imported source removed from the workspace.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to delete imported source.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleImportFileSelect(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    try {
      const text = await file.text()
      setImportDraft(text)
      setNotice(t('Import file loaded into the editor. Review it before importing.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to read the selected file.'))
    } finally {
      event.target.value = ''
    }
  }

  async function handleRunBenchmark() {
    setBusyAction('benchmark')
    setError(null)
    setNotice(null)
    try {
      setWorkspaceView('operations')
      setOperationsSection('status')
      const payload = await fetchBenchmark('real', 1, 1)
      setBenchmark(payload)
      setNotice(t('Benchmark completed. Review the latest collection and query timings.'))
    } catch (err) {
      setError(uiErrorMessage(err, 'Unable to run the benchmark.'))
    } finally {
      setBusyAction(null)
    }
  }

  if (booting) {
    return (
      <main className="shell shell--loading">
        <div className="loading-card">
          <LanguageSwitcher />
          <div className="eyebrow">{PRODUCT_NAME}</div>
          <h1>{t('Loading the live control plane...')}</h1>
          <p>
            {t('Preparing administrator context, monitored targets and the latest access snapshot.')}
          </p>
        </div>
      </main>
    )
  }

  if (!session?.authenticated) {
    if (setupStatus?.setup_required) {
      return (
        <main className="shell shell--auth">
          <section className="auth-panel">
            <LanguageSwitcher />
            <div className="eyebrow">{t('Initial Setup')}</div>
            <h1>{t('Create the local application administrator')}</h1>
            <p className="hero-text">
              {t(
                'Start with a local break-glass administrator for the platform. After the first access, you can enable LDAP domain sign-in or OAuth2/OIDC providers such as Microsoft, Google, GitHub, Okta or Keycloak.',
              )}
            </p>

            <div className="auth-meta">
              <div className="summary-chip">
                <span>{t('Tenant')}</span>
                <strong>{setupStatus.tenant_name}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Recommended flow')}</span>
                <strong>{setupStatus.recommended_flow}</strong>
              </div>
            </div>

            <form className="auth-form" onSubmit={handleSetupLocalAdmin}>
              <label className="field">
                <span>{t('Tenant name')}</span>
                <input
                  value={setupDraft.tenant_name}
                  onChange={(event) =>
                    setSetupDraft((current) => ({ ...current, tenant_name: event.target.value }))
                  }
                  placeholder={PRODUCT_DEFAULT_TENANT_PLACEHOLDER}
                />
              </label>
              <label className="field">
                <span>{t('Admin username')}</span>
                <input
                  value={setupDraft.username}
                  onChange={(event) =>
                    setSetupDraft((current) => ({ ...current, username: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Admin password')}</span>
                <input
                  type="password"
                  value={setupDraft.password}
                  onChange={(event) =>
                    setSetupDraft((current) => ({ ...current, password: event.target.value }))
                  }
                />
              </label>
              <button
                className="primary-action"
                type="submit"
                disabled={busyAction === 'setup-admin'}
              >
                {busyAction === 'setup-admin'
                  ? t('Creating administrator...')
                  : t('Complete setup')}
              </button>
            </form>

            {error ? <div className="error-banner">{error}</div> : null}
            {notice ? <div className="notice-banner">{uiMessage(notice)}</div> : null}
          </section>
        </main>
      )
    }

    if (mfaChallenge) {
      return (
        <main className="shell shell--auth">
          <section className="auth-panel">
            <LanguageSwitcher />
            <div className="eyebrow">{t('Two-Factor Authentication')}</div>
            <h1>{t('Complete administrator sign-in')}</h1>
            <p className="hero-text">
              {t(
                'This local administrator is protected with built-in TOTP MFA. Enter the current code from your authenticator app to finish the sign-in flow.',
              )}
            </p>

            <div className="auth-meta">
              <div className="summary-chip">
                <span>{t('Administrator')}</span>
                <strong>{mfaChallenge.username}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Auth source')}</span>
                <strong>{mfaChallenge.authSource}</strong>
              </div>
            </div>

            <form className="auth-form" onSubmit={handleVerifyMfa}>
              <label className="field">
                <span>{t('Authenticator code')}</span>
                <input
                  inputMode="numeric"
                  value={mfaChallengeCode}
                  onChange={(event) => setMfaChallengeCode(event.target.value)}
                  placeholder="123456"
                />
              </label>
              <button className="primary-action" type="submit" disabled={busyAction === 'mfa-verify'}>
                {busyAction === 'mfa-verify' ? t('Verifying...') : t('Complete sign-in')}
              </button>
            </form>

            <button
              className="secondary-action"
              type="button"
              onClick={() => {
                setMfaChallenge(null)
                setMfaChallengeCode('')
                setNotice(null)
              }}
            >
              {t('Back to sign-in')}
            </button>

            {error ? <div className="error-banner">{error}</div> : null}
            {notice ? <div className="notice-banner">{uiMessage(notice)}</div> : null}
          </section>
        </main>
      )
    }

    return (
      <main className="shell shell--auth">
        <section className="auth-panel">
          <LanguageSwitcher />
          <div className="eyebrow">{t('Administrator Access')}</div>
          <h1>{t('Sign in to the live access platform')}</h1>
          <p className="hero-text">
            {t(
              'The application reads the real host filesystem and monitored targets. Sign in with the local application administrator, an LDAP-backed domain identity, or a configured OAuth2/OIDC provider. Keycloak is supported as an optional OIDC provider, not as a mandatory dependency.',
            )}
          </p>

          <div className="auth-meta">
            <div className="summary-chip">
              <span>{t('Local admin')}</span>
              <strong>{bootstrap?.admin_username ?? 'admin'}</strong>
            </div>
            <div className="summary-chip">
              <span>{t('Providers')}</span>
              <strong>
                {publicAuthProviders?.providers.length
                  ? t('{count} sign-in option(s)', { count: publicAuthProviders.providers.length })
                  : t('Local sign-in only')}
              </strong>
            </div>
          </div>
          <p className="auth-note">
            {t(
              'Local application accounts can use built-in TOTP MFA. Federated providers such as Keycloak, Entra ID or Okta should enforce MFA in the identity provider.',
            )}
          </p>

          <form className="auth-form" onSubmit={handleLogin}>
            <label className="field">
              <span>{t('Username')}</span>
              <input
                value={credentials.username}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, username: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>{t('Password')}</span>
              <input
                type="password"
                value={credentials.password}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, password: event.target.value }))
                }
              />
            </label>
            {publicAuthProviders?.providers.some((provider) => provider.accepts_password) ? (
              <label className="field">
                <span>{t('Password provider')}</span>
                <select
                  value={selectedPasswordProvider}
                  onChange={(event) => setSelectedPasswordProvider(event.target.value)}
                >
                  <option value="">{t('Local application account')}</option>
                  {publicAuthProviders.providers
                    .filter((provider) => provider.accepts_password)
                    .map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.name}
                      </option>
                    ))}
                </select>
              </label>
            ) : null}
            <button className="primary-action" type="submit" disabled={busyAction === 'login'}>
              {busyAction === 'login'
                ? t('Signing in...')
                : selectedPasswordProvider
                  ? t('Sign in with domain credentials')
                  : t('Sign in as application administrator')}
            </button>
          </form>

          {publicAuthProviders?.providers.some((provider) => provider.uses_redirect) ? (
          <div className="auth-provider-grid">
            {publicAuthProviders.providers
                .filter((provider) => provider.uses_redirect && provider.login_path)
                .map((provider) => (
                  <a key={provider.id} className="secondary-action auth-provider-link" href={provider.login_path ?? '#'}>
                    {provider.sign_in_label}
                  </a>
                ))}
            </div>
          ) : null}

          {error ? <div className="error-banner">{error}</div> : null}
          {notice ? <div className="notice-banner">{uiMessage(notice)}</div> : null}
        </section>
      </main>
    )
  }

  if (session.must_change_password) {
    return (
      <main className="shell shell--auth">
        <section className="auth-panel">
          <LanguageSwitcher />
          <div className="eyebrow">{t('Password Rotation Required')}</div>
          <h1>{t('Rotate the bootstrap administrator password')}</h1>
          <p className="hero-text">
            {t(
              'This deployment keeps the workspace locked until the first-run administrator secret is replaced with a permanent password.',
            )}
          </p>

          <div className="auth-meta">
            <div className="summary-chip">
              <span>{t('Administrator')}</span>
              <strong>{session.username ?? bootstrap?.admin_username ?? 'admin'}</strong>
            </div>
            <div className="summary-chip">
              <span>{t('Security gate')}</span>
              <strong>{t('Workspace access locked')}</strong>
            </div>
          </div>

          <form className="auth-form" onSubmit={handlePasswordChange}>
              <label className="field">
              <span>{t('Current password')}</span>
              <input
                type="password"
                value={passwordForm.current}
                onChange={(event) =>
                  setPasswordForm((current) => ({ ...current, current: event.target.value }))
                }
              />
            </label>
              <label className="field">
              <span>{t('New password')}</span>
              <input
                type="password"
                value={passwordForm.next}
                onChange={(event) =>
                  setPasswordForm((current) => ({ ...current, next: event.target.value }))
                }
              />
            </label>
            <button className="primary-action" type="submit" disabled={busyAction === 'password'}>
              {busyAction === 'password' ? t('Updating...') : t('Rotate password')}
            </button>
          </form>

          <button
            className="secondary-action"
            type="button"
            onClick={() => void handleLogout()}
            disabled={busyAction === 'logout'}
          >
            {busyAction === 'logout' ? t('Signing out...') : t('Sign out')}
          </button>

          {error ? <div className="error-banner">{error}</div> : null}
          {notice ? <div className="notice-banner">{uiMessage(notice)}</div> : null}
        </section>
      </main>
    )
  }

  const historyMax = Math.max(
    ...(overview?.history.map((point) => point.privileged_paths) ?? [1]),
  )
  const reportActions =
    selectedPrincipalId && selectedResourceId && selectedScenarioEdgeId
      ? [
          {
            label: t('Download PDF'),
            href: buildReportUrl({
              format: 'pdf',
              principalId: selectedPrincipalId,
              resourceId: selectedResourceId,
              scenarioEdgeId: selectedScenarioEdgeId,
              focusResourceId: scenarioFocusResourceId,
              locale,
            }),
          },
          {
            label: t('Export Excel'),
            href: buildReportUrl({
              format: 'xlsx',
              principalId: selectedPrincipalId,
              resourceId: selectedResourceId,
              scenarioEdgeId: selectedScenarioEdgeId,
              focusResourceId: scenarioFocusResourceId,
              locale,
            }),
          },
          {
            label: t('Open HTML'),
            href: buildReportUrl({
              format: 'html',
              principalId: selectedPrincipalId,
              resourceId: selectedResourceId,
              scenarioEdgeId: selectedScenarioEdgeId,
              focusResourceId: scenarioFocusResourceId,
              locale,
            }),
          },
        ]
      : []

  return (
    <main className="shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow">{PRODUCT_CATEGORY}</div>
          <h1>{overview?.tenant ?? PRODUCT_DEFAULT_TENANT_NAME}</h1>
          <p className="hero-text">
            {t(
              'Production-facing control plane for live filesystem access, explainable paths and operator-ready reporting.',
            )}
          </p>
          <div className="hero-meta">
            <span>{t('Admin session: {value}', { value: session.username ?? 'admin' })}</span>
            <span>
              {t('Roles: {value}', {
                value: (session.roles ?? []).map((role) => t(appRoleLabel(role))).join(', ') || t('n/d'),
              })}
            </span>
            <span>
              {t('Workspace: {value}', {
                value: session.active_workspace_name ?? t('n/d'),
              })}
            </span>
            <span>{t('Host: {value}', { value: runtimeStatus?.host ?? t('n/d') })}</span>
            <span>
              {t('Runtime role: {value}', {
                value: t(runtimeRoleLabel(runtimeStatus?.runtime_role ?? 'all')),
              })}
            </span>
            <span>{t('Snapshot: {value}', { value: formatLocaleDateTime(overview?.generated_at) })}</span>
            <span>
              {t('Freshness: {value}', {
                value: t(runtimeStatus?.freshness_status ?? 'empty'),
              })}
            </span>
            <span>{t('Targets active: {value}', { value: runtimeStatus?.active_target_count ?? 0 })}</span>
            <span>
              {t('Background worker: {value}', {
                value: t(backgroundWorkerStateLabel(runtimeStatus?.background_worker_state ?? 'missing')),
              })}
            </span>
            <span>
              {t('Last successful scan: {value}', {
                value: formatLocaleDateTime(runtimeStatus?.last_successful_scan_at),
              })}
            </span>
            <span>
              {t('Raw batches: {value}', {
                value: runtimeStatus?.raw_batch_count ?? 0,
              })}
            </span>
            <span>
              {t('Index rows: {value}', {
                value: runtimeStatus?.materialized_access_rows ?? 0,
              })}
            </span>
            <span>
              {runtimeStatus?.scheduler_enabled
                ? t('Scheduler: every {value}s', {
                    value: runtimeStatus.scheduler_interval_seconds ?? 0,
                  })
                : t('Scheduler: manual')}
            </span>
          </div>
          <div className="hero-actions">
            <button
              className="primary-action"
              type="button"
              onClick={() => void handleRunScan()}
              disabled={busyAction === 'scan-all' || !canManageSources}
            >
              {busyAction === 'scan-all' ? t('Scanning...') : t('Scan enabled targets')}
            </button>
            <button
              className="secondary-action"
              type="button"
              onClick={() => void handleLogout()}
              disabled={busyAction === 'logout'}
            >
              {busyAction === 'logout' ? t('Signing out...') : t('Logout')}
            </button>
            <LanguageSwitcher compact />
          </div>
        </div>
        <SearchBox
          query={searchQuery}
          loading={searchLoading}
          results={searchResults}
          onQueryChange={setSearchQuery}
          onSelect={handleSearchSelect}
        />
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="workspace-layout">
        <WorkspaceNavigation
          activeView={activeWorkspaceView}
          views={workspaceViews}
          activeViewId={workspaceView}
          onSelectView={handleSelectWorkspace}
          secondaryTabs={secondaryTabs}
          activeSecondaryTabId={activeSecondaryTabId()}
          onSelectSecondaryTab={handleSelectSecondaryTab}
        />

        <div className="workspace-content">
          {showHomeView ? (
            <HomeDashboard
              metrics={overview?.metrics ?? []}
              hotspots={topHotspots}
              insights={topInsights}
              history={recentHistory}
              historyMax={historyMax}
              mvpReadiness={mvpReadiness}
              featureInventory={featureInventory}
              operationalFlow={operationalFlow}
              riskFindings={riskFindings?.findings ?? []}
              recentChanges={recentChanges?.changes ?? []}
              onOpenInvestigate={() => handleSelectWorkspace('investigate')}
              onOpenGovern={() => handleSelectWorkspace('govern')}
              onOpenSources={() => handleSelectWorkspace('sources')}
              onOpenOperations={() => handleSelectWorkspace('operations')}
              onOpenReadinessAction={openWorkspaceDestination}
              toneLabel={toneLabelValue}
            />
          ) : showInvestigateView ? (
            <section className="report-bar">
              <div>
                <div className="eyebrow">{t('Executive Output')}</div>
                <strong>
                  {t(
                    'Download a polished report for the selected principal, resource and scenario.',
                  )}
                </strong>
              </div>
              <div className="report-actions">
                {reportActions.map((action) => (
                  <a
                    key={action.label}
                    className="report-action"
                    href={action.href}
                    target={action.label === t('Open HTML') ? '_blank' : undefined}
                    rel={action.label === t('Open HTML') ? 'noreferrer' : undefined}
                  >
                    {action.label}
                  </a>
                ))}
              </div>
            </section>
          ) : (
            <section className="workspace-focus">
              <div>
                <div className="eyebrow">{t('Current Focus')}</div>
                <strong>{activeWorkspaceView.title}</strong>
                <p className="admin-copy">{activeWorkspaceView.description}</p>
              </div>
              <div className="report-actions">
                {showSourcesView ? (
                  <button
                    className="report-action report-action--button"
                    type="button"
                    onClick={() => void handleRunScan()}
                    disabled={busyAction === 'scan-all'}
                  >
                    {busyAction === 'scan-all' ? t('Scanning...') : t('Scan enabled targets')}
                  </button>
                ) : null}
                {showOperationsView ? (
                  <button
                    className="report-action report-action--button"
                    type="button"
                    onClick={() => void handleRunBenchmark()}
                    disabled={busyAction === 'benchmark'}
                  >
                    {busyAction === 'benchmark'
                      ? t('Running benchmark...')
                      : benchmark
                        ? t('Refresh benchmark')
                        : t('Run benchmark')}
                  </button>
                ) : null}
                {showGovernView && selectedAccessReviewId ? (
                  <a
                    className="report-action"
                    href={buildReviewCampaignReportUrl({
                      format: 'pdf',
                      campaignId: selectedAccessReviewId,
                      locale,
                    })}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t('Export current review')}
                  </a>
                ) : null}
              </div>
            </section>
          )}

      {!showHomeView ? (
      <section className={`workspace-grid ${showInvestigateView ? '' : 'workspace-grid--single'}`}>
        {showInvestigateView ? (
          <InvestigateWorkspace
            investigateSection={investigateSection}
            principalOptions={principalOptions}
            resourceOptions={resourceOptions}
            selectedPrincipalId={selectedPrincipalId}
            selectedResourceId={selectedResourceId}
            onSelectPrincipal={(principalId) => {
              startTransition(() => {
                setSelectedPrincipalId(principalId)
                setFocusedEntityId(principalId)
              })
            }}
            onSelectResource={(resourceId) => {
              startTransition(() => {
                setSelectedResourceId(resourceId)
                setScenarioFocusResourceId(resourceId)
                setFocusedEntityId(resourceId)
              })
            }}
            explanation={explanation}
            resourceAccess={resourceAccess}
            resourceAccessLoading={resourceAccessLoading}
            onChangeResourceAccessWindow={(offset, limit) => {
              setResourceAccessOffset(offset)
              setResourceAccessPageSize(limit)
            }}
            scenarioOptions={scenarioOptions}
            selectedScenarioEdgeId={selectedScenarioEdgeId}
            onSelectScenario={handleScenarioChange}
            scenarioFocusResourceId={scenarioFocusResourceId}
            onSelectScenarioFocusResource={setScenarioFocusResourceId}
            activeScenarioReason={activeScenario?.reason ?? null}
            canSimulate={canSimulate}
            simulation={simulation}
            entityDetail={entityDetail}
            graphSubgraph={graphSubgraph}
            showDenseGraph={showDenseGraph}
            onToggleDenseGraph={() => {
              setShowDenseGraph((current) => !current)
            }}
            graphDepth={graphDepth}
            onChangeGraphDepth={setGraphDepth}
            graphDensityProfile={graphDensityProfile}
            onChangeGraphDensityProfile={setGraphDensityProfile}
            history={overview?.history ?? []}
            historyMax={historyMax}
            insights={overview?.insights ?? []}
            toneLabel={toneLabelValue}
            kindLabel={kindLabelValue}
          />
        ) : null}

        {!showInvestigateView ? (
        <aside className="workspace-side">
          {showSourcesView && sourcesSection === 'auth' ? (
          <>
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Workspace')}</div>
                <h2>{t('Organizations and environments')}</h2>
              </div>
            </div>
            <p className="admin-copy">
              {t(
                'Use dedicated workspaces to isolate a customer, business unit or environment while keeping authentication and platform administration in one control plane.',
              )}
            </p>
            <div className="summary-strip summary-strip--stacked">
              {(workspaceInventory?.workspaces ?? []).map((workspace) => (
                <button
                  key={workspace.id}
                  type="button"
                  className={`summary-chip summary-chip--button ${
                    workspace.id === session?.active_workspace_id ? 'summary-chip--active' : ''
                  }`}
                  onClick={() => void handleActivateWorkspace(workspace.id)}
                  disabled={
                    !canManageAdmins ||
                    workspace.id === session?.active_workspace_id ||
                    busyAction === `activate-workspace-${workspace.id}`
                  }
                >
                  <span>
                    {workspace.environment} · {workspace.slug}
                  </span>
                  <strong>{workspace.name}</strong>
                </button>
              ))}
            </div>
            <form className="security-form security-form--muted" onSubmit={handleUpdateWorkspace}>
              <div className="table-primary">{t('Update active workspace')}</div>
              <label className="field">
                <span>{t('Workspace name')}</span>
                <input
                  type="text"
                  value={workspaceEditDraft.name}
                  onChange={(event) =>
                    setWorkspaceEditDraft((current) => ({ ...current, name: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Description')}</span>
                <input
                  type="text"
                  value={workspaceEditDraft.description}
                  onChange={(event) =>
                    setWorkspaceEditDraft((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Environment')}</span>
                <select
                  value={workspaceEditDraft.environment}
                  onChange={(event) =>
                    setWorkspaceEditDraft((current) => ({
                      ...current,
                      environment: event.target.value as 'on-prem' | 'cloud' | 'hybrid',
                    }))
                  }
                >
                  <option value="on-prem">{t('On-prem')}</option>
                  <option value="hybrid">{t('Hybrid')}</option>
                  <option value="cloud">{t('Cloud')}</option>
                </select>
              </label>
              <div className="target-card__actions">
                <button
                  className="mini-action mini-action--strong"
                  type="submit"
                  disabled={!canManageAdmins || busyAction === 'update-workspace'}
                >
                  {busyAction === 'update-workspace'
                    ? t('Updating...')
                    : t('Save workspace details')}
                </button>
              </div>
            </form>
            <form className="security-form security-form--muted" onSubmit={handleCreateWorkspace}>
              <div className="table-primary">{t('Create workspace')}</div>
              <label className="field">
                <span>{t('Workspace name')}</span>
                <input
                  type="text"
                  value={workspaceDraft.name}
                  onChange={(event) =>
                    setWorkspaceDraft((current) => ({ ...current, name: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Slug')}</span>
                <input
                  type="text"
                  value={workspaceDraft.slug}
                  onChange={(event) =>
                    setWorkspaceDraft((current) => ({ ...current, slug: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Description')}</span>
                <input
                  type="text"
                  value={workspaceDraft.description}
                  onChange={(event) =>
                    setWorkspaceDraft((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Environment')}</span>
                <select
                  value={workspaceDraft.environment}
                  onChange={(event) =>
                    setWorkspaceDraft((current) => ({
                      ...current,
                      environment: event.target.value as 'on-prem' | 'cloud' | 'hybrid',
                    }))
                  }
                >
                  <option value="on-prem">{t('On-prem')}</option>
                  <option value="hybrid">{t('Hybrid')}</option>
                  <option value="cloud">{t('Cloud')}</option>
                </select>
              </label>
              <div className="target-card__actions">
                <button
                  className="mini-action mini-action--strong"
                  type="submit"
                  disabled={!canManageAdmins || busyAction === 'create-workspace'}
                >
                  {busyAction === 'create-workspace'
                    ? t('Creating...')
                    : t('Create workspace')}
                </button>
              </div>
            </form>
          </article>
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Authentication')}</div>
                <h2>{t('Sign-in providers')}</h2>
              </div>
            </div>
            <article className="security-card">
              <div className="security-card__header">
                <div>
                  <div className="table-primary">{t('Local admin MFA')}</div>
                  <div className="table-secondary">
                    {mfaStatus?.available
                      ? t('Built-in TOTP for local application administrators')
                      : t('Provider-managed authentication')}
                  </div>
                </div>
                <span
                  className={`status-pill status-pill--${
                    mfaStatus?.enabled ? 'healthy' : mfaStatus?.available ? 'warning' : 'configured'
                  }`}
                >
                  {mfaStatus?.enabled
                    ? t('enabled')
                    : mfaStatus?.available
                      ? t('recommended')
                      : t('provider-managed')}
                </span>
              </div>
              <p className="admin-copy">
                {mfaStatus?.provider_hint
                  ? t(mfaStatus.provider_hint)
                  : t(
                      'Local administrators can use built-in TOTP MFA. Keycloak is optional and can enforce MFA upstream when configured as an OIDC provider.',
                    )}
              </p>
              {mfaStatus?.available ? (
                <div className="target-card__actions">
                  <button
                    type="button"
                    className="mini-action"
                    onClick={() => void handleBeginMfaSetup()}
                    disabled={busyAction === 'mfa-setup'}
                  >
                    {busyAction === 'mfa-setup'
                      ? t('Preparing...')
                      : mfaStatus.enabled
                        ? t('Re-generate setup')
                        : t('Enable MFA')}
                  </button>
                </div>
              ) : null}

              {mfaSetup ? (
                <form className="security-form" onSubmit={handleConfirmMfaSetup}>
                  <div className="security-secret">
                    <span>{t('Manual setup key')}</span>
                    <strong>{mfaSetup.manual_entry_key}</strong>
                  </div>
                  <div className="security-uri">{mfaSetup.provisioning_uri}</div>
                  <label className="field">
                    <span>{t('Authenticator code')}</span>
                    <input
                      inputMode="numeric"
                      value={mfaSetupCode}
                      onChange={(event) => setMfaSetupCode(event.target.value)}
                      placeholder="123456"
                    />
                  </label>
                  <button
                    type="submit"
                    className="mini-action mini-action--primary"
                    disabled={busyAction === 'mfa-enable'}
                  >
                    {busyAction === 'mfa-enable' ? t('Enabling...') : t('Confirm MFA')}
                  </button>
                </form>
              ) : null}

              {mfaStatus?.enabled ? (
                <form className="security-form security-form--muted" onSubmit={handleDisableMfa}>
                  <label className="field">
                    <span>{t('Current password')}</span>
                    <input
                      type="password"
                      value={mfaDisableForm.currentPassword}
                      onChange={(event) =>
                        setMfaDisableForm((current) => ({
                          ...current,
                          currentPassword: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>{t('Current TOTP code')}</span>
                    <input
                      inputMode="numeric"
                      value={mfaDisableForm.code}
                      onChange={(event) =>
                        setMfaDisableForm((current) => ({ ...current, code: event.target.value }))
                      }
                      placeholder="123456"
                    />
                  </label>
                  <button
                    type="submit"
                    className="mini-action"
                    disabled={busyAction === 'mfa-disable'}
                  >
                    {busyAction === 'mfa-disable' ? t('Disabling...') : t('Disable MFA')}
                  </button>
                </form>
              ) : null}
            </article>
            {canManageAdmins && adminUsers ? (
              <article className="security-card">
                <div className="security-card__header">
                  <div>
                    <div className="table-primary">{t('Application roles')}</div>
                    <div className="table-secondary">
                      {t('Assign least-privilege roles to local and federated administrators.')}
                    </div>
                  </div>
                  <span className="status-pill status-pill--configured">
                    {t('{count} accounts', { count: adminUsers.users.length })}
                  </span>
                </div>
                <div className="list-stack">
                  {adminUsers.users.map((adminUser) => (
                    <article key={adminUser.username} className="target-card">
                      <div className="target-card__header">
                        <div>
                          <div className="table-primary">
                            {adminUser.display_name || adminUser.username}
                          </div>
                          <div className="table-secondary">
                            {adminUser.username} | {adminUser.auth_source}
                          </div>
                        </div>
                        <span
                          className={`status-pill status-pill--${
                            adminUser.must_change_password ? 'warning' : 'healthy'
                          }`}
                        >
                          {adminUser.must_change_password ? t('rotation required') : t('active')}
                        </span>
                      </div>
                      <div className="target-card__meta">
                        <span>{t('Created')}: {adminUser.created_at.slice(0, 10)}</span>
                        <span>{adminUser.mfa_enabled ? t('MFA enabled') : t('MFA not enabled')}</span>
                      </div>
                      <div className="role-toggle-grid">
                        {(
                          [
                            'viewer',
                            'investigator',
                            'auditor',
                            'connector_admin',
                            'executive_read_only',
                            'admin',
                          ] as AppRole[]
                        ).map((role) => {
                          const enabled = adminUser.roles.includes(role)
                          return (
                            <label key={role} className="role-toggle">
                              <input
                                type="checkbox"
                                checked={enabled}
                                onChange={() =>
                                  void handleToggleAdminRole(adminUser.username, role, enabled)
                                }
                                disabled={busyAction === `admin-role-${adminUser.username}-${role}`}
                              />
                              <span>{t(appRoleLabel(role))}</span>
                            </label>
                          )
                        })}
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            ) : null}
            <div className="list-stack">
              {authProviders?.providers.map((provider) => (
                <article key={provider.id} className="target-card">
                  <div className="target-card__header">
                    <div>
                      <div className="table-primary">{provider.name}</div>
                      <div className="table-secondary">
                        {provider.kind.toUpperCase()} · {t(provider.preset)}
                      </div>
                    </div>
                    <span className={`status-pill status-pill--${provider.enabled ? 'healthy' : 'idle'}`}>
                      {provider.enabled ? t('enabled') : t('disabled')}
                    </span>
                  </div>
                  <div className="target-card__meta">
                    <span>{provider.accepts_password ? t('Password sign-in') : t('Browser redirect')}</span>
                    <span>{provider.created_at.slice(0, 10)}</span>
                  </div>
                  {provider.description ? <p className="admin-copy">{t(provider.description)}</p> : null}
                  {canManageSources ? (
                    <div className="target-card__actions">
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() => void handleToggleAuthProvider(provider.id, provider.enabled)}
                      >
                        {provider.enabled ? t('Disable') : t('Enable')}
                      </button>
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() => void handleDeleteAuthProvider(provider.id)}
                      >
                        {t('Remove')}
                      </button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>

            {canManageSources ? (
            <form className="target-form" onSubmit={handleCreateAuthProvider}>
              <label className="field">
                <span>{t('Provider name')}</span>
                <input
                  value={authProviderDraft.name}
                  onChange={(event) =>
                    setAuthProviderDraft((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder="Contoso Entra ID"
                />
              </label>
              <div className="control-grid control-grid--tight">
                <label className="field">
                  <span>{t('Type')}</span>
                  <select
                    value={authProviderDraft.kind}
                    onChange={(event) =>
                      setAuthProviderDraft((current) => ({
                        ...current,
                        kind: event.target.value as 'ldap' | 'oidc',
                      }))
                    }
                  >
                    <option value="oidc">{t('OAuth2 / OIDC')}</option>
                    <option value="ldap">{t('LDAP / Domain')}</option>
                  </select>
                </label>
                {authProviderDraft.kind === 'oidc' ? (
                  <label className="field">
                    <span>{t('Preset')}</span>
                    <select
                      value={authProviderDraft.preset}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          preset: event.target.value as AuthProviderPreset,
                        }))
                      }
                    >
                      <option value="microsoft">Microsoft</option>
                      <option value="google">Google</option>
                      <option value="github">GitHub</option>
                      <option value="okta">Okta</option>
                      <option value="keycloak">Keycloak</option>
                      <option value="custom">Custom OIDC</option>
                    </select>
                  </label>
                ) : null}
              </div>
              {authProviderDraft.kind === 'ldap' ? (
                <div className="target-remote-grid">
                  <label className="field">
                    <span>{t('LDAP server URI')}</span>
                    <input
                      value={authProviderDraft.ldap_server_uri}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          ldap_server_uri: event.target.value,
                        }))
                      }
                      placeholder="ldaps://dc01.example.internal:636"
                    />
                  </label>
                  <label className="field">
                    <span>{t('Base DN')}</span>
                    <input
                      value={authProviderDraft.ldap_base_dn}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          ldap_base_dn: event.target.value,
                        }))
                      }
                      placeholder="DC=example,DC=internal"
                    />
                  </label>
                  <label className="field field--full">
                    <span>{t('Service bind DN')}</span>
                    <input
                      value={authProviderDraft.ldap_bind_dn}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          ldap_bind_dn: event.target.value,
                        }))
                      }
                      placeholder="CN=eip-reader,OU=Service Accounts,DC=example,DC=internal"
                    />
                  </label>
                  <label className="field">
                    <span>{t('Bind secret env var')}</span>
                    <input
                      value={authProviderDraft.ldap_bind_password_env}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          ldap_bind_password_env: event.target.value,
                        }))
                      }
                      placeholder="EIP_LDAP_BIND_PASSWORD"
                    />
                  </label>
                  <label className="field field--full">
                    <span>{t('Allowed groups')}</span>
                    <input
                      value={authProviderDraft.allowed_groups}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          allowed_groups: event.target.value,
                        }))
                      }
                      placeholder="CN=EIP Admins,OU=Groups,DC=example,DC=internal"
                    />
                  </label>
                </div>
              ) : (
                <div className="target-remote-grid">
                  <label className="field">
                    <span>{t('Issuer URL')}</span>
                    <input
                      value={authProviderDraft.issuer_url}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          issuer_url: event.target.value,
                        }))
                      }
                      placeholder="https://login.microsoftonline.com/common/v2.0"
                    />
                  </label>
                  <label className="field">
                    <span>{t('Discovery URL')}</span>
                    <input
                      value={authProviderDraft.discovery_url}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          discovery_url: event.target.value,
                        }))
                      }
                      placeholder="https://accounts.google.com/.well-known/openid-configuration"
                    />
                  </label>
                  <label className="field">
                    <span>{t('Client ID')}</span>
                    <input
                      value={authProviderDraft.client_id}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          client_id: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>{t('Client secret env var')}</span>
                    <input
                      value={authProviderDraft.client_secret_env}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          client_secret_env: event.target.value,
                        }))
                      }
                      placeholder="EIP_OIDC_CLIENT_SECRET"
                    />
                  </label>
                  <label className="field field--full">
                    <span>{t('Allowed email domains')}</span>
                    <input
                      value={authProviderDraft.allowed_domains}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          allowed_domains: event.target.value,
                        }))
                      }
                      placeholder="example.com, contoso.com"
                    />
                  </label>
                  <label className="field field--full">
                    <span>{t('Scopes')}</span>
                    <input
                      value={authProviderDraft.scopes}
                      onChange={(event) =>
                        setAuthProviderDraft((current) => ({
                          ...current,
                          scopes: event.target.value,
                        }))
                      }
                      placeholder="openid profile email"
                    />
                  </label>
                </div>
              )}
              <button
                className="primary-action"
                type="submit"
                disabled={busyAction === 'create-auth-provider'}
              >
                {busyAction === 'create-auth-provider' ? t('Saving...') : t('Add sign-in provider')}
              </button>
            </form>
            ) : (
              <p className="admin-copy">
                {t('Your current application role can review sign-in providers but cannot change them.')}
              </p>
            )}
          </article>

          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Monitored Targets')}</div>
                <h2>{t('Filesystem scope')}</h2>
              </div>
            </div>
            <div className="list-stack">
              {targets.map((target) => (
                <article key={target.id} className="target-card">
                  <div className="target-card__header">
                    <div>
                      <div className="table-primary">{target.name}</div>
                      <div className="table-secondary">{target.path}</div>
                    </div>
                    <span className={`status-pill status-pill--${target.last_status}`}>
                      {t(target.last_status)}
                    </span>
                  </div>
                  <div className="target-card__meta">
                    <span>{connectionModeLabel(target.connection_mode)}</span>
                    <span>{platformLabel(target.platform)}</span>
                    {target.connection_mode === 'ssh' && target.host ? (
                      <span>
                        {target.username ? `${target.username}@` : ''}
                        {target.host}:{target.port}
                      </span>
                    ) : null}
                    <span>{t('depth {value}', { value: target.max_depth })}</span>
                    <span>{t('{value} entries', { value: target.max_entries })}</span>
                  </div>
                  {canManageSources ? (
                    <div className="target-card__actions">
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() => void handleToggleTarget(target)}
                      >
                        {target.enabled ? t('Disable') : t('Enable')}
                      </button>
                      <button
                        type="button"
                        className="mini-action mini-action--strong"
                        onClick={() => void handleRunScan(target.id)}
                        disabled={busyAction === `scan-${target.id}`}
                      >
                        {busyAction === `scan-${target.id}` ? t('Scanning...') : t('Scan now')}
                      </button>
                    </div>
                  ) : null}
                  {target.last_error ? <div className="target-card__error">{t(target.last_error)}</div> : null}
                </article>
              ))}
            </div>

            {canManageSources ? (
            <form className="target-form" onSubmit={handleCreateTarget}>
              <label className="field">
                <span>{t('Target name')}</span>
                <input
                  value={targetDraft.name}
                  onChange={(event) =>
                    setTargetDraft((current) => ({ ...current, name: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>{t('Filesystem path')}</span>
                <input
                  value={targetDraft.path}
                  onChange={(event) =>
                    setTargetDraft((current) => ({ ...current, path: event.target.value }))
                  }
                  placeholder={
                    targetDraft.connection_mode === 'ssh'
                      ? '/srv/data or /var/www'
                      : 'C:\\Share or /mnt/data'
                  }
                />
              </label>
              <div className="control-grid control-grid--tight">
                <label className="field">
                  <span>{t('Connection')}</span>
                  <select
                    value={targetDraft.connection_mode}
                    onChange={(event) =>
                      setTargetDraft((current) => ({
                        ...current,
                        connection_mode: event.target.value as 'local' | 'ssh',
                        platform:
                          event.target.value === 'ssh' && current.platform === 'windows'
                            ? 'linux'
                            : current.platform,
                      }))
                    }
                  >
                    <option value="local">{t('Local / mounted')}</option>
                    <option value="ssh">{t('Remote Linux via SSH')}</option>
                  </select>
                </label>
                <label className="field">
                  <span>{t('Platform')}</span>
                  <select
                    value={targetDraft.platform}
                    onChange={(event) =>
                      setTargetDraft((current) => ({
                        ...current,
                        platform: event.target.value as 'auto' | 'windows' | 'linux',
                      }))
                    }
                  >
                    <option value="auto">Auto</option>
                    <option value="windows">Windows</option>
                    <option value="linux">Linux</option>
                  </select>
                </label>
              </div>

              {targetDraft.connection_mode === 'ssh' ? (
                <div className="target-remote-grid">
                  <label className="field">
                    <span>{t('SSH host')}</span>
                    <input
                      value={targetDraft.host}
                      onChange={(event) =>
                        setTargetDraft((current) => ({ ...current, host: event.target.value }))
                      }
                      placeholder="server01.example.internal"
                    />
                  </label>
                  <label className="field">
                    <span>{t('SSH username')}</span>
                    <input
                      value={targetDraft.username}
                      onChange={(event) =>
                        setTargetDraft((current) => ({ ...current, username: event.target.value }))
                      }
                      placeholder="scanner"
                    />
                  </label>
                  <label className="field">
                    <span>{t('Port')}</span>
                    <input
                      type="number"
                      min={1}
                      max={65535}
                      value={targetDraft.port}
                      onChange={(event) =>
                        setTargetDraft((current) => ({
                          ...current,
                          port: Number(event.target.value),
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>{t('Password env var')}</span>
                    <input
                      value={targetDraft.secret_env}
                      onChange={(event) =>
                        setTargetDraft((current) => ({
                          ...current,
                          secret_env: event.target.value,
                        }))
                      }
                      placeholder="EIP_SSH_TARGET_PASSWORD"
                    />
                  </label>
                  <label className="field field--full">
                    <span>{t('Private key path')}</span>
                    <input
                      value={targetDraft.key_path}
                      onChange={(event) =>
                        setTargetDraft((current) => ({ ...current, key_path: event.target.value }))
                      }
                      placeholder="C:\\Keys\\scanner.pem or /home/eip/.ssh/id_ed25519"
                    />
                  </label>
                </div>
              ) : null}

              <div className="control-grid control-grid--tight">
                <label className="field">
                  <span>{t('Max depth')}</span>
                  <input
                    type="number"
                    min={0}
                    max={16}
                    value={targetDraft.max_depth}
                    onChange={(event) =>
                      setTargetDraft((current) => ({
                        ...current,
                        max_depth: Number(event.target.value),
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>{t('Max entries')}</span>
                  <input
                    type="number"
                    min={25}
                    max={10000}
                    value={targetDraft.max_entries}
                    onChange={(event) =>
                      setTargetDraft((current) => ({
                        ...current,
                        max_entries: Number(event.target.value),
                      }))
                    }
                  />
                </label>
              </div>
              <p className="admin-copy">
                {t(
                  'Local mode covers host paths, mounted volumes and UNC shares reachable by the server. SSH mode is designed for remote Linux targets. Linux collectors read POSIX ACLs with getfacl when available.',
                )}
              </p>
              <button
                className="primary-action"
                type="submit"
                disabled={busyAction === 'create-target'}
              >
                {busyAction === 'create-target' ? t('Adding...') : t('Add monitored target')}
              </button>
            </form>
            ) : (
              <p className="admin-copy">
                {t('Your current application role can review monitored targets but cannot change them.')}
              </p>
            )}
          </article>
          </>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Pipeline')}</div>
                <h2>{t('Index refresh')}</h2>
              </div>
            </div>
            {runtimeStatus?.index_refresh ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Mode')}</span>
                    <strong>{t(indexRefreshModeLabel(runtimeStatus.index_refresh.mode))}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Reused rows')}</span>
                    <strong>{runtimeStatus.index_refresh.reused_access_rows}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Recomputed rows')}</span>
                    <strong>{runtimeStatus.index_refresh.recomputed_access_rows}</strong>
                  </div>
                </div>
                <div className="detail-grid">
                  <div className="detail-item">
                    <span>{t('Impacted principals')}</span>
                    <strong>{runtimeStatus.index_refresh.impacted_principals}</strong>
                  </div>
                  <div className="detail-item">
                    <span>{t('Impacted resources')}</span>
                    <strong>{runtimeStatus.index_refresh.impacted_resources}</strong>
                  </div>
                  <div className="detail-item">
                    <span>{t('Group closure refresh')}</span>
                    <strong>
                      {runtimeStatus.index_refresh.carried_forward_group_closure
                        ? t('Carry-forward')
                        : t('{count} principals', {
                            count: runtimeStatus.index_refresh.recomputed_group_closure_principals,
                          })}
                    </strong>
                  </div>
                  <div className="detail-item">
                    <span>{t('Hierarchy refresh')}</span>
                    <strong>
                      {runtimeStatus.index_refresh.carried_forward_resource_hierarchy
                        ? t('Carry-forward')
                        : t('{count} resources', {
                            count: runtimeStatus.index_refresh.recomputed_resource_hierarchy_resources,
                          })}
                    </strong>
                  </div>
                </div>
                {runtimeStatus.index_refresh.previous_snapshot_at ? (
                  <p className="table-secondary">
                    {t('Previous snapshot: {value}', {
                      value: formatLocaleDateTime(runtimeStatus.index_refresh.previous_snapshot_at),
                    })}
                  </p>
                ) : null}
                {runtimeStatus.index_refresh.fallback_reasons.length ? (
                  <div className="list-stack">
                    {runtimeStatus.index_refresh.fallback_reasons.map((reason) => (
                      <div key={reason} className="list-row list-row--static">
                        <div className="table-secondary">{t(reason)}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="table-secondary">
                    {t(
                      'Access index refresh uses carry-forward when the graph is unchanged and delta recomputation when the impacted scope stays small.',
                    )}
                  </p>
                )}
              </>
            ) : (
              <div className="empty-state">
                {t('The next successful scan will publish an index refresh summary.')}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Observability')}</div>
                <h2>{t('Query performance')}</h2>
              </div>
            </div>
            {queryPerformance?.metrics.length ? (
              <div className="list-stack">
                {queryPerformance.metrics.slice(0, 8).map((metric) => (
                  <div key={metric.operation} className="list-row list-row--static">
                    <div>
                      <div className="table-primary">{metric.operation}</div>
                      <div className="table-secondary">
                        {t('avg {average} ms | p95 {p95} ms', {
                          average: metric.average_ms,
                          p95: metric.p95_ms,
                        })}
                      </div>
                      <div className="table-secondary">
                        {t('{count} calls | {errors} errors', {
                          count: metric.calls,
                          errors: metric.error_count,
                        })}
                        {metric.last_seen_at
                          ? ` | ${t('Last seen: {value}', {
                              value: formatLocaleDateTime(metric.last_seen_at),
                            })}`
                          : ''}
                      </div>
                    </div>
                    <span className="risk-pill">{metric.max_ms}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                {t('Query performance metrics appear after operators use search, explain and exposure APIs.')}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Latest Scan')}</div>
                <h2>{t('Operational status')}</h2>
              </div>
            </div>
            {scans?.latest ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Finished')}</span>
                    <strong>{formatLocaleDateTime(scans.latest.finished_at)}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Duration')}</span>
                    <strong>{scans.latest.duration_ms?.toFixed(1)} ms</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Warnings')}</span>
                    <strong>{scans.latest.warning_count}</strong>
                  </div>
                </div>
                <div className="list-stack">
                  {scans.latest.notes.slice(0, 4).map((note) => (
                    <div key={note} className="list-row list-row--static">
                      <div className="table-secondary">{t(note)}</div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">{t('No live scan recorded yet.')}</div>
            )}
          </article>
          ) : null}

          {showGovernView && governSection === 'reviews' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Governance')}</div>
                <h2>{t('Access reviews')}</h2>
              </div>
              {selectedAccessReviewId ? (
                <div className="panel__actions">
                  <a
                    className="mini-action"
                    href={buildReviewCampaignReportUrl({
                      format: 'html',
                      campaignId: selectedAccessReviewId,
                      locale,
                    })}
                    target="_blank"
                    rel="noreferrer"
                  >
                    HTML
                  </a>
                  <a
                    className="mini-action"
                    href={buildReviewCampaignReportUrl({
                      format: 'pdf',
                      campaignId: selectedAccessReviewId,
                      locale,
                    })}
                    target="_blank"
                    rel="noreferrer"
                  >
                    PDF
                  </a>
                  <a
                    className="mini-action"
                    href={buildReviewCampaignReportUrl({
                      format: 'xlsx',
                      campaignId: selectedAccessReviewId,
                      locale,
                    })}
                    target="_blank"
                    rel="noreferrer"
                  >
                    XLSX
                  </a>
                </div>
              ) : null}
            </div>
            <div className="list-stack">
              {accessReviews?.campaigns.slice(0, 4).map((campaign) => (
                <button
                  key={campaign.id}
                  type="button"
                  className={`list-row ${
                    selectedAccessReviewId === campaign.id ? 'list-row--selected' : 'list-row--static'
                  }`}
                  onClick={() => setSelectedAccessReviewId(campaign.id)}
                >
                  <div>
                    <div className="table-primary">{campaign.name}</div>
                    <div className="table-secondary">
                      {t('{value} pending', { value: campaign.pending_items })} |{' '}
                      {t('{value} revoke', { value: campaign.revoke_count })} | risk &gt;= {campaign.min_risk_score}
                    </div>
                  </div>
                  <span className={`status-pill status-pill--${campaign.status === 'completed' ? 'healthy' : 'warning'}`}>
                    {t(campaign.status)}
                  </span>
                </button>
              ))}
            </div>

            {canManageGovernance ? (
            <form className="target-form" onSubmit={handleCreateAccessReview}>
              <label className="field field--full">
                <span>{t('Review campaign name')}</span>
                <input
                  value={accessReviewDraft.name}
                  onChange={(event) =>
                    setAccessReviewDraft((current) => ({ ...current, name: event.target.value }))
                  }
                />
              </label>
              <label className="field field--full">
                <span>{t('Description')}</span>
                <input
                  value={accessReviewDraft.description}
                  onChange={(event) =>
                    setAccessReviewDraft((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                />
              </label>
              <div className="control-grid control-grid--tight">
                <label className="field">
                  <span>{t('Min risk')}</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={accessReviewDraft.min_risk_score}
                    onChange={(event) =>
                      setAccessReviewDraft((current) => ({
                        ...current,
                        min_risk_score: Number(event.target.value),
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>{t('Max items')}</span>
                  <input
                    type="number"
                    min={1}
                    max={200}
                    value={accessReviewDraft.max_items}
                    onChange={(event) =>
                      setAccessReviewDraft((current) => ({
                        ...current,
                        max_items: Number(event.target.value),
                      }))
                    }
                  />
                </label>
              </div>
              <label className="field field--checkbox">
                <input
                  type="checkbox"
                  checked={accessReviewDraft.privileged_only}
                  onChange={(event) =>
                    setAccessReviewDraft((current) => ({
                      ...current,
                      privileged_only: event.target.checked,
                    }))
                  }
                />
                <span>{t('Only include privileged effective access')}</span>
              </label>
              <button
                className="primary-action"
                type="submit"
                disabled={busyAction === 'create-access-review'}
              >
                {busyAction === 'create-access-review'
                  ? t('Generating...')
                  : t('Create review campaign')}
              </button>
            </form>
            ) : (
              <p className="admin-copy">
                {t('Your current application role can review governance evidence but cannot create or decide campaigns.')}
              </p>
            )}

            {accessReviewDetail ? (
              <div className="cluster-detail">
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Items')}</span>
                    <strong>{accessReviewDetail.summary.total_items}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Pending')}</span>
                    <strong>{accessReviewDetail.summary.pending_items}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Snapshot')}</span>
                    <strong>{formatLocaleDateTime(accessReviewDetail.summary.snapshot_generated_at)}</strong>
                  </div>
                </div>
                <div className="cluster-resource-list">
                  {accessReviewDetail.items.slice(0, 6).map((item) => (
                    <article key={item.id} className="target-card">
                      <div className="target-card__header">
                        <div>
                          <div className="table-primary">
                            {item.principal.name} → {item.resource.name}
                          </div>
                          <div className="table-secondary">
                            {item.permissions.map((permission) => t(permission)).join(', ')} |{' '}
                            {t(item.access_mode)} | {t('risk {value}', { value: item.risk_score })}
                          </div>
                        </div>
                        <span
                          className={`status-pill status-pill--${
                            item.decision === 'revoke'
                              ? 'critical'
                              : item.decision === 'keep'
                                ? 'healthy'
                                : item.decision === 'needs_follow_up'
                                  ? 'warning'
                                  : 'disabled'
                          }`}
                        >
                          {reviewDecisionLabel(item.decision)}
                        </span>
                      </div>
                      <div className="table-secondary">{t(item.why)}</div>
                      {item.suggested_remediation ? (
                        <div className="connector-runtime-note">{t(item.suggested_remediation)}</div>
                      ) : null}
                      <div className="target-card__actions">
                        {canManageGovernance ? (
                          <>
                            <button
                              type="button"
                              className="mini-action"
                              onClick={() => void handleAccessReviewDecision(item.id, 'keep')}
                              disabled={busyAction === `review-decision-${item.id}-keep`}
                            >
                              {t('Keep')}
                            </button>
                            <button
                              type="button"
                              className="mini-action mini-action--strong"
                              onClick={() => void handleAccessReviewDecision(item.id, 'revoke')}
                              disabled={busyAction === `review-decision-${item.id}-revoke`}
                            >
                              {t('Revoke')}
                            </button>
                            <button
                              type="button"
                              className="mini-action"
                              onClick={() => void handleAccessReviewDecision(item.id, 'needs_follow_up')}
                              disabled={busyAction === `review-decision-${item.id}-needs_follow_up`}
                            >
                              {t('Follow up')}
                            </button>
                          </>
                        ) : null}
                        <button
                          type="button"
                          className="mini-action"
                          onClick={() => void handleOpenRemediation(item.id)}
                          disabled={busyAction === `review-remediation-${item.id}`}
                        >
                          {t('Remediation')}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <div className="empty-state">
                {t(
                  'Create or select a campaign to review high-risk access with deterministic decisions.',
                )}
              </div>
            )}
          </article>
          ) : null}

          {showGovernView && governSection === 'remediation' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Remediation')}</div>
                <h2>{t('Deterministic change plan')}</h2>
              </div>
            </div>
            {accessReviewRemediation ? (
              <>
                <p className="entity-description">{t(accessReviewRemediation.summary)}</p>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Impacted principals')}</span>
                    <strong>{accessReviewRemediation.impacted_principals}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Impacted resources')}</span>
                    <strong>{accessReviewRemediation.impacted_resources}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Privileged paths removed')}</span>
                    <strong>{accessReviewRemediation.privileged_paths_removed}</strong>
                  </div>
                </div>
                <div className="list-stack">
                  {accessReviewRemediation.steps.map((step) => (
                    <div key={step.order} className="list-row list-row--static">
                      <div>
                        <div className="table-primary">
                          {step.order}. {t(step.title)}
                        </div>
                        <div className="table-secondary">{t(step.detail)}</div>
                      </div>
                      <span className="kind-pill">{t(step.impact)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                {t(
                  'Open a remediation plan from any review item to see a staged and explainable change path.',
                )}
              </div>
            )}
          </article>
          ) : null}

          {showGovernView && governSection === 'schedules' ? (
          <ReportSchedulesPanel
            principalOptions={principalOptions}
            resourceOptions={resourceOptions}
            scenarioOptions={scenarioOptions}
            accessReviews={accessReviews?.campaigns ?? []}
            canManage={canManageGovernance}
          />
          ) : null}

          {showSourcesView && sourcesSection === 'imports' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Offline Sources')}</div>
                <h2>{t('Import local JSON bundles')}</h2>
              </div>
            </div>
            <div className="list-stack">
              {importedSources?.sources.map((source) => (
                <article key={source.id} className="target-card">
                  <div className="target-card__header">
                    <div>
                      <div className="table-primary">{source.name}</div>
                      <div className="table-secondary">
                        {source.source} | {source.environment}
                      </div>
                    </div>
                    <span className={`status-pill status-pill--${source.enabled ? 'healthy' : 'disabled'}`}>
                      {source.enabled ? 'enabled' : 'disabled'}
                    </span>
                  </div>
                  <div className="target-card__meta">
                    <span>{source.entity_count} entities</span>
                    <span>{source.relationship_count} links</span>
                    <span>{source.connector_count} connectors</span>
                  </div>
                  {source.description ? <div className="table-secondary">{source.description}</div> : null}
                  {canManageSources ? (
                    <div className="target-card__actions">
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() => void handleToggleImportedSource(source.id, source.enabled)}
                        disabled={busyAction === `import-toggle-${source.id}`}
                      >
                        {source.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() => void handleDeleteImportedSource(source.id)}
                        disabled={busyAction === `import-delete-${source.id}`}
                      >
                        {busyAction === `import-delete-${source.id}` ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>

            {canManageSources ? (
            <form className="target-form" onSubmit={handleImportSource}>
              <label className="field">
                <span>{t('Load JSON file')}</span>
                <input type="file" accept=".json,application/json" onChange={handleImportFileSelect} />
              </label>
              <label className="field">
                <span>{t('Bundle JSON')}</span>
                <textarea
                  className="import-textarea"
                  value={importDraft}
                  onChange={(event) => setImportDraft(event.target.value)}
                  spellCheck={false}
                />
              </label>
              <p className="admin-copy">
                Use this for offline exports, local inventories or entitlement datasets you do not
                want to pull from paid or registered services directly.
              </p>
              <button
                className="primary-action"
                type="submit"
                disabled={busyAction === 'import-source'}
              >
                {busyAction === 'import-source' ? t('Importing...') : t('Import local source')}
              </button>
            </form>
            ) : (
              <p className="admin-copy">
                {t('Your current application role can review imported bundles but cannot change them.')}
              </p>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'platform' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Platform')}</div>
                <h2>{t('Enterprise posture')}</h2>
              </div>
            </div>
            {platformPosture ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Storage')}</span>
                    <strong>{platformPosture.storage_backend}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Search')}</span>
                    <strong>{platformPosture.search_backend}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Cache')}</span>
                    <strong>{platformPosture.cache_backend}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Analytics')}</span>
                    <strong>{platformPosture.analytics_backend}</strong>
                  </div>
                </div>
                <div className="connector-list">
                  {platformPosture.components.map((component) => (
                    <article key={component.id} className="connector-runtime-card">
                      <div className="connector-row">
                        <div>
                          <div className="table-primary">{component.name}</div>
                          <div className="table-secondary">{component.summary}</div>
                        </div>
                        <div
                          className={`status-pill status-pill--${
                            component.state === 'error'
                              ? 'critical'
                              : component.state === 'active'
                                ? 'healthy'
                                : component.state === 'configured'
                                  ? 'warning'
                                  : 'disabled'
                          }`}
                        >
                          {platformStateLabel(component.state)}
                        </div>
                      </div>
                      <div className="target-card__meta">
                        <span>{component.category}</span>
                        <span>{component.connected ? t('connected') : t('not connected')}</span>
                        <span>{component.configured ? t('Configured') : t('Optional')}</span>
                      </div>
                      {component.details.length ? (
                        <div className="connector-runtime-section">
                          <div className="table-secondary">{t('Operational details')}</div>
                          <div className="connector-runtime-env">
                            {component.details.slice(0, 4).map((item) => (
                              <span key={item} className="step-pill">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {component.documentation_url ? (
                        <div className="blueprint-card__links">
                          <a
                            className="mini-link"
                            href={component.documentation_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {t('Official documentation')}
                          </a>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
                {exposureAnalytics ? (
                  <div className="connector-support-matrix">
                    <div className="panel__header">
                      <div>
                        <div className="eyebrow">{t('Materialized analytics')}</div>
                        <h2>{t('Exposure summaries')}</h2>
                      </div>
                    </div>
                    <div className="connector-list">
                      <article className="connector-runtime-card">
                        <div className="connector-row">
                          <div>
                            <div className="table-primary">{t('Top exposed resources')}</div>
                            <div className="table-secondary">
                              {t('Materialized summaries from the resource exposure index.')}
                            </div>
                          </div>
                        </div>
                        <div className="list-stack">
                          {exposureAnalytics.resource_summaries.slice(0, 5).map((item) => (
                            <article key={item.resource.id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{item.resource.name}</div>
                                <div className="table-secondary">
                                  {t('{count} principals', { count: item.principal_count })} |{' '}
                                  {t('{count} privileged', {
                                    count: item.privileged_principal_count,
                                  })}{' '}
                                  | {t('Complexity')} {item.average_path_complexity}
                                </div>
                              </div>
                              <span className="risk-pill">{item.exposure_score}</span>
                            </article>
                          ))}
                        </div>
                      </article>
                      <article className="connector-runtime-card">
                        <div className="connector-row">
                          <div>
                            <div className="table-primary">{t('Top exposed principals')}</div>
                            <div className="table-secondary">
                              {t('Materialized summaries from the principal access index.')}
                            </div>
                          </div>
                        </div>
                        <div className="list-stack">
                          {exposureAnalytics.principal_summaries.slice(0, 5).map((item) => (
                            <article key={item.principal.id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{item.principal.name}</div>
                                <div className="table-secondary">
                                  {t('{count} resources', { count: item.resource_count })} |{' '}
                                  {t('{count} privileged', {
                                    count: item.privileged_resource_count,
                                  })}{' '}
                                  | {t('Complexity')} {item.average_path_complexity}
                                </div>
                              </div>
                              <span className="risk-pill">{item.exposure_score}</span>
                            </article>
                          ))}
                        </div>
                      </article>
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                {t('Platform posture becomes available after administrator authentication.')}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Operational Flow')}</div>
                <h2>{t('Readiness and next actions')}</h2>
              </div>
            </div>
            {operationalFlow ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Overall status')}</span>
                    <strong>{platformStateLabel(operationalFlow.overall_status === 'ready' ? 'active' : operationalFlow.overall_status === 'action_required' ? 'error' : 'configured')}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Completion')}</span>
                    <strong>{operationalFlow.completion_percent}%</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Open actions')}</span>
                    <strong>{operationalFlow.next_actions.length}</strong>
                  </div>
                </div>
                <div className="list-stack">
                  {operationalFlow.steps.map((step) => (
                    <article key={step.id} className="list-row list-row--static">
                      <div>
                        <div className="table-primary">{t(step.title)}</div>
                        <div className="table-secondary">{t(step.detail)}</div>
                        <div className="table-secondary">{t(step.recommended_action)}</div>
                      </div>
                      <span
                        className={`status-pill status-pill--${
                          step.status === 'ready'
                            ? 'healthy'
                            : step.status === 'action_required'
                              ? 'critical'
                              : 'warning'
                        }`}
                      >
                        {step.status === 'ready'
                          ? t('Ready')
                          : step.status === 'action_required'
                            ? t('Action')
                            : t('Progress')}
                      </span>
                    </article>
                  ))}
                </div>
                {operationalFlow.next_actions.length ? (
                  <div className="connector-runtime-section">
                    <div className="table-secondary">{t('Recommended next actions')}</div>
                    <div className="connector-runtime-env">
                      {operationalFlow.next_actions.map((item) => (
                        <span key={item} className="step-pill">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                {t('Operational readiness is calculated after authentication.')}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Job Center')}</div>
                <h2>{t('Background work and worker lanes')}</h2>
              </div>
            </div>
            {jobCenter ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Overall status')}</span>
                    <strong>{t(jobCenter.overall_status)}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Worker lanes')}</span>
                    <strong>{jobCenter.lanes.length}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Recent jobs')}</span>
                    <strong>{jobCenter.recent_jobs.length}</strong>
                  </div>
                </div>
                <div className="connector-list">
                  {jobCenter.lanes.map((lane) => (
                    <article key={lane.id} className="connector-runtime-card">
                      <div className="connector-row">
                        <div>
                          <div className="table-primary">{t(lane.name)}</div>
                          <div className="table-secondary">{t(lane.summary)}</div>
                        </div>
                        <div
                          className={`status-pill status-pill--${
                            lane.state === 'running'
                              ? 'healthy'
                              : lane.state === 'scheduled'
                                ? 'configured'
                                : lane.state === 'attention'
                                  ? 'critical'
                                  : 'disabled'
                          }`}
                        >
                          {t(jobLaneStateLabel(lane.state))}
                        </div>
                      </div>
                      <div className="target-card__meta">
                        <span>{lane.kind === 'scan' ? t('Collection') : t('Report delivery')}</span>
                        <span>{t('{count} queued', { count: lane.queue_depth })}</span>
                        <span>{t('{count} work items', { count: lane.active_work_items })}</span>
                        <span>{lane.scheduler_enabled ? t('Scheduler enabled') : t('Scheduler manual')}</span>
                        <span>{t(backgroundWorkerStateLabel(lane.execution_mode))}</span>
                      </div>
                      <div className="connector-runtime-section">
                        <div className="table-secondary">{t('Operational details')}</div>
                        <div className="connector-runtime-env">
                          {lane.worker_role ? (
                            <span className="step-pill">
                              {t('Worker role: {value}', {
                                value: t(runtimeRoleLabel(lane.worker_role)),
                              })}
                            </span>
                          ) : null}
                          {lane.worker_host ? (
                            <span className="step-pill">
                              {t('Worker host: {value}', { value: lane.worker_host })}
                            </span>
                          ) : null}
                          {lane.worker_last_seen_at ? (
                            <span className="step-pill">
                              {t('Worker heartbeat: {value}', {
                                value: formatLocaleDateTime(lane.worker_last_seen_at),
                              })}
                            </span>
                          ) : null}
                          {lane.last_completed_at ? (
                            <span className="step-pill">
                              {t('Last completed: {value}', {
                                value: formatLocaleDateTime(lane.last_completed_at),
                              })}
                            </span>
                          ) : null}
                          {lane.next_due_at ? (
                            <span className="step-pill">
                              {t('Next due: {value}', {
                                value: formatLocaleDateTime(lane.next_due_at),
                              })}
                            </span>
                          ) : null}
                          {lane.last_status ? (
                            <span className="step-pill">{t('Last status: {value}', { value: lane.last_status })}</span>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                {jobCenter.recent_jobs.length ? (
                  <div className="list-stack">
                    {jobCenter.recent_jobs.slice(0, 8).map((job) => (
                      <article key={job.id} className="list-row list-row--static">
                        <div>
                          <div className="table-primary">{job.label}</div>
                          <div className="table-secondary">{t(job.summary)}</div>
                          <div className="table-secondary">
                            {formatLocaleDateTime(job.started_at)}
                            {job.finished_at ? ` -> ${formatLocaleDateTime(job.finished_at)}` : ''}
                          </div>
                        </div>
                        <span
                          className={`status-pill status-pill--${
                            job.status === 'success' || job.status === 'healthy'
                              ? 'healthy'
                              : job.status === 'partial' || job.status === 'warning'
                                ? 'warning'
                                : job.status === 'running'
                                  ? 'configured'
                                  : 'critical'
                          }`}
                        >
                          {t(job.status)}
                        </span>
                      </article>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                {t('Background work becomes visible after administrator authentication.')}
              </div>
            )}
          </article>
          ) : null}

          {showSourcesView && sourcesSection === 'collection' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Connectors')}</div>
                <h2>{t('Official integration posture')}</h2>
              </div>
            </div>
            <div className="connector-list">
              {connectorRuntime?.connectors.map((connector) => (
                <article key={connector.id} className="connector-runtime-card">
                  <div className="connector-row">
                    <div>
                      <div className="table-primary">{connector.surface}</div>
                      <div className="table-secondary">{connector.description}</div>
                    </div>
                    <div className={`status-pill status-pill--${connector.status}`}>
                      {connector.status}
                    </div>
                  </div>
                    <div className="target-card__meta">
                      <span>{connector.collection_mode}</span>
                      <span>{implementationLabel(connector.implementation_status)}</span>
                      <span>{connector.source}</span>
                      <span>{t('{count} entities', { count: connector.entity_count })}</span>
                      <span>{t('{count} links', { count: connector.relationship_count })}</span>
                    </div>
                  {connector.supported_entities.length ? (
                    <div className="connector-runtime-section">
                      <div className="table-secondary">{t('Supported entities')}</div>
                      <div className="connector-runtime-env">
                        {connector.supported_entities.slice(0, 4).map((item) => (
                          <span key={item} className="step-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {connector.required_env.length ? (
                    <div className="connector-runtime-section">
                      <div className="table-secondary">{t('Required environment')}</div>
                      <div className="connector-runtime-env">
                        {connector.required_env.slice(0, 4).map((item) => (
                          <span key={item} className="step-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {connector.required_permissions.length ? (
                    <div className="connector-runtime-section">
                      <div className="table-secondary">{t('Required permissions')}</div>
                      <div className="connector-runtime-env">
                        {connector.required_permissions.slice(0, 3).map((item) => (
                          <span key={item} className="step-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {connector.current_runtime_coverage[0] ? (
                    <div className="table-secondary connector-runtime-note">
                      Current coverage: {connector.current_runtime_coverage[0]}
                    </div>
                  ) : null}
                  {connector.official_limitations[0] ? (
                    <div className="table-secondary connector-runtime-note">
                      Official limitation: {connector.official_limitations[0]}
                    </div>
                  ) : null}
                  {connector.notes[0] ? (
                    <div className="table-secondary connector-runtime-note">{connector.notes[0]}</div>
                  ) : null}
                </article>
              ))}
            </div>
            {connectorSupportMatrix ? (
              <div className="connector-support-matrix">
                <div className="panel__header">
                  <div>
                    <div className="eyebrow">{t('Support Matrix')}</div>
                    <h2>{t('Operational trust per connector surface')}</h2>
                  </div>
                  <div className="panel__stats">
                    <span>
                      {connectorSupportMatrix.counts_by_tier.supported ?? 0} {t('supported')}
                    </span>
                    <span>
                      {connectorSupportMatrix.counts_by_tier.pilot ?? 0} {t('pilot')}
                    </span>
                    <span>
                      {connectorSupportMatrix.counts_by_tier.blueprint ?? 0} {t('blueprints')}
                    </span>
                  </div>
                </div>
                <p className="admin-copy">{t(connectorSupportMatrix.primary_scope)}</p>
                <div className="connector-list">
                  {connectorSupportMatrix.entries.map((entry) => (
                    <article key={entry.id} className="connector-runtime-card">
                      <div className="connector-row">
                        <div>
                          <div className="table-primary">{entry.name}</div>
                          <div className="table-secondary">{t(entry.summary)}</div>
                        </div>
                        <div
                          className={`status-pill status-pill--${
                            entry.support_tier === 'supported'
                              ? 'healthy'
                              : entry.support_tier === 'pilot' || entry.support_tier === 'experimental'
                                ? 'warning'
                                : 'disabled'
                          }`}
                        >
                          {t(supportTierLabel(entry.support_tier))}
                        </div>
                      </div>
                      <div className="target-card__meta">
                        <span>{t(entry.category)}</span>
                        <span>{t(validationLevelLabel(entry.validation_level))}</span>
                        <span>{t(recommendedUsageLabel(entry.recommended_usage))}</span>
                        <span>{implementationLabel(entry.implementation_status)}</span>
                      </div>
                      {entry.evidence.length ? (
                        <div className="connector-runtime-section">
                          <div className="table-secondary">{t('Evidence')}</div>
                          <div className="connector-runtime-env">
                            {entry.evidence.slice(0, 3).map((item) => (
                              <span key={item} className="step-pill">
                                {t(item)}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {entry.current_gaps.length ? (
                        <div className="connector-runtime-section">
                          <div className="table-secondary">{t('Current gaps')}</div>
                          <div className="connector-runtime-env">
                            {entry.current_gaps.slice(0, 2).map((item) => (
                              <span key={item} className="step-pill step-pill--warn">
                                {t(item)}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {entry.next_actions.length ? (
                        <div className="table-secondary connector-runtime-note">
                          {t('Next action')}: {t(entry.next_actions[0])}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
          ) : null}

          {showSourcesView && sourcesSection === 'identity' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Identity Fabric')}</div>
                <h2>{t('Cross-source linked identities')}</h2>
              </div>
            </div>
            {identityClusters && identityClusters.clusters.length > 0 ? (
              <>
                <div className="list-stack">
                  {identityClusters.clusters.slice(0, 4).map((cluster) => (
                    <button
                      key={cluster.id}
                      type="button"
                      className={`list-row ${
                        selectedClusterId === cluster.id ? 'list-row--selected' : 'list-row--static'
                      }`}
                      onClick={() => setSelectedClusterId(cluster.id)}
                    >
                      <div>
                        <div className="table-primary">{cluster.display_name}</div>
                        <div className="table-secondary">
                          {cluster.source_count} sources | {cluster.combined_resource_count} resources
                        </div>
                      </div>
                      <span className="risk-pill">risk {cluster.max_risk_score}</span>
                    </button>
                  ))}
                </div>

                {identityClusterDetail ? (
                  <div className="cluster-detail">
                    <div className="summary-strip summary-strip--stacked">
                      {identityClusterDetail.cluster.match_keys.map((key) => (
                        <span key={key} className="step-pill">
                          {key}
                        </span>
                      ))}
                    </div>

                    <div className="cluster-subsection">
                      <div className="table-primary">{t('Linked identities')}</div>
                      <div className="cluster-member-list">
                        {identityClusterDetail.members.map((member) => (
                          <button
                            key={member.entity.id}
                            type="button"
                            className="list-row"
                            onClick={() => {
                              startTransition(() => {
                                setSelectedPrincipalId(member.entity.id)
                                setFocusedEntityId(member.entity.id)
                              })
                            }}
                          >
                            <div>
                              <div className="table-primary">{member.entity.name}</div>
                              <div className="table-secondary">
                                {member.entity.source} |{' '}
                                {t('confidence {value}', { value: member.confidence })}
                              </div>
                            </div>
                            <span className="kind-pill">{member.entity.environment}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="cluster-subsection">
                      <div className="table-primary">{t('Combined access footprint')}</div>
                      <div className="cluster-resource-list">
                        {identityClusterDetail.top_resources.slice(0, 4).map((resource) => (
                          <button
                            key={resource.resource.id}
                            type="button"
                            className="list-row"
                            onClick={() => {
                              startTransition(() => {
                                setSelectedResourceId(resource.resource.id)
                                setFocusedEntityId(resource.resource.id)
                              })
                            }}
                          >
                            <div>
                              <div className="table-primary">{resource.resource.name}</div>
                              <div className="table-secondary">
                                {t('{count} linked identities | {permissions}', {
                                  count: resource.contributing_identities.length,
                                  permissions: resource.permissions.join(', '),
                                })}
                              </div>
                            </div>
                            <span className="risk-pill">
                              {t('risk {value}', { value: resource.max_risk_score })}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                {t(
                  'Connect at least two identity sources for the same organization to unlock cross-source correlation and a unified user footprint.',
                )}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'status' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Performance')}</div>
                <h2>{t('Real local benchmark')}</h2>
              </div>
              <button
                type="button"
                className="mini-action"
                onClick={() => void handleRunBenchmark()}
                disabled={busyAction === 'benchmark'}
              >
                {busyAction === 'benchmark'
                  ? t('Running...')
                  : benchmark
                    ? t('Refresh benchmark')
                    : t('Run benchmark')}
              </button>
            </div>
            {benchmark ? (
              <>
                <div className="summary-strip summary-strip--stacked">
                  <div className="summary-chip">
                    <span>{t('Mode')}</span>
                    <strong>{benchmark.snapshot.mode}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Scope')}</span>
                    <strong>{benchmark.snapshot.scope}</strong>
                  </div>
                  <div className="summary-chip">
                    <span>{t('Targets')}</span>
                    <strong>{benchmark.snapshot.target_count}</strong>
                  </div>
                </div>
                <div className="list-stack">
                  {benchmark.metrics.map((metric) => (
                    <div key={metric.name} className="list-row list-row--static">
                      <div>
                        <div className="table-primary">{metric.name}</div>
                        <div className="table-secondary">
                          {t('avg {average} ms | p95 {p95} ms', {
                            average: metric.average_ms,
                            p95: metric.p95_ms,
                          })}
                        </div>
                      </div>
                      <span className="risk-pill">
                        {t('{count} runs', { count: metric.iterations })}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                {t('Run the live benchmark on demand so normal workspace loading stays fast.')}
              </div>
            )}
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'platform' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Official Blueprint')}</div>
                <h2>{t('Cloud and IAM integration notes')}</h2>
              </div>
            </div>
            <div className="blueprint-list">
              {blueprints?.blueprints.map((blueprint) => (
                <article key={blueprint.id} className="blueprint-card">
                  <div className="insight-card__header">
                    <span>{blueprint.surface}</span>
                    <span className="kind-pill">{blueprint.collection_mode}</span>
                  </div>
                  <div className="target-card__meta">
                    <span>{implementationLabel(blueprint.implementation_status)}</span>
                    <span>{blueprint.vendor}</span>
                  </div>
                  <p>{blueprint.freshness}</p>
                  {blueprint.current_runtime_coverage[0] ? (
                    <div className="table-secondary blueprint-card__detail">
                      {t('Runtime')}: {blueprint.current_runtime_coverage[0]}
                    </div>
                  ) : null}
                  {blueprint.official_limitations[0] ? (
                    <div className="table-secondary blueprint-card__detail">
                      {t('Limitation')}: {blueprint.official_limitations[0]}
                    </div>
                  ) : null}
                  {blueprint.documentation_links[0] ? (
                    <div className="blueprint-card__links">
                      <a
                        className="mini-link"
                        href={blueprint.documentation_links[0].url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t('Official documentation')}
                      </a>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </article>
          ) : null}

          {showOperationsView && operationsSection === 'audit' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Audit Trail')}</div>
                <h2>{t('Recent administrator actions')}</h2>
              </div>
            </div>
            {auditEvents?.events.length ? (
              <div className="list-stack">
                {auditEvents.events.slice(0, 10).map((event) => (
                  <article key={event.id} className="list-row list-row--static">
                    <div>
                      <div className="table-primary">{event.summary}</div>
                      <div className="table-secondary">
                        {formatLocaleDateTime(event.occurred_at)} | {event.actor_username} | {event.action}
                      </div>
                    </div>
                    <span
                      className={`status-pill status-pill--${
                        event.status === 'success'
                          ? 'healthy'
                          : event.status === 'failed'
                            ? 'critical'
                            : 'warning'
                      }`}
                    >
                      {event.status}
                    </span>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">{t('No audit event has been recorded yet.')}</div>
            )}
          </article>
          ) : null}
        </aside>
        ) : null}
      </section>
      ) : null}
        </div>
      </section>
    </main>
  )
}

export default App
