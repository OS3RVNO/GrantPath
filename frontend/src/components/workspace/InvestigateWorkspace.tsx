import { Suspense, lazy, useState } from 'react'

import { AccessTable } from '../AccessTable'
import { useI18n } from '../../i18n'

import type {
  EntityDetailResponse,
  EntitySummary,
  ExplainResponse,
  GraphSubgraphResponse,
  HistoricalPoint,
  InsightNote,
  ResourceAccessResponse,
  Tone,
  WhatIfResponse,
  ScenarioChoice,
} from '../../types'

const AccessGraph = lazy(() =>
  import('../AccessGraph').then((module) => ({
    default: module.AccessGraph,
  })),
)

const GraphExplorer = lazy(() =>
  import('../GraphExplorer').then((module) => ({
    default: module.GraphExplorer,
  })),
)

const WhatIfFlow = lazy(() =>
  import('../WhatIfFlow').then((module) => ({
    default: module.WhatIfFlow,
  })),
)

type InvestigateSection = 'explain' | 'exposure' | 'whatif'
type EntityInsightKey = 'kind' | 'criticality' | 'risk'
type EntityPanelSection = 'overview' | 'grants' | 'risk' | 'changes'

interface InvestigateWorkspaceProps {
  investigateSection: InvestigateSection
  principalOptions: EntitySummary[]
  resourceOptions: EntitySummary[]
  selectedPrincipalId: string
  selectedResourceId: string
  onSelectPrincipal: (principalId: string) => void
  onSelectResource: (resourceId: string) => void
  explanation: ExplainResponse | null
  resourceAccess: ResourceAccessResponse | null
  resourceAccessLoading: boolean
  onChangeResourceAccessWindow: (offset: number, limit: number) => void
  scenarioOptions: ScenarioChoice[]
  selectedScenarioEdgeId: string
  onSelectScenario: (edgeId: string) => void
  scenarioFocusResourceId?: string | null
  onSelectScenarioFocusResource: (resourceId: string) => void
  activeScenarioReason?: string | null
  canSimulate: boolean
  simulation: WhatIfResponse | null
  entityDetail: EntityDetailResponse | null
  graphSubgraph: GraphSubgraphResponse | null
  showDenseGraph: boolean
  onToggleDenseGraph: () => void
  graphDepth: number
  onChangeGraphDepth: (depth: number) => void
  graphDensityProfile: 'compact' | 'expanded'
  onChangeGraphDensityProfile: (profile: 'compact' | 'expanded') => void
  history: HistoricalPoint[]
  historyMax: number
  insights: InsightNote[]
  toneLabel: (tone: Tone) => string
  kindLabel: (kind: string) => string
}

export function InvestigateWorkspace({
  investigateSection,
  principalOptions,
  resourceOptions,
  selectedPrincipalId,
  selectedResourceId,
  onSelectPrincipal,
  onSelectResource,
  explanation,
  resourceAccess,
  resourceAccessLoading,
  onChangeResourceAccessWindow,
  scenarioOptions,
  selectedScenarioEdgeId,
  onSelectScenario,
  scenarioFocusResourceId,
  onSelectScenarioFocusResource,
  activeScenarioReason,
  canSimulate,
  simulation,
  entityDetail,
  graphSubgraph,
  showDenseGraph,
  onToggleDenseGraph,
  graphDepth,
  onChangeGraphDepth,
  graphDensityProfile,
  onChangeGraphDensityProfile,
  history,
  historyMax,
  insights,
  toneLabel,
  kindLabel,
}: InvestigateWorkspaceProps) {
  const { t, formatDateTime } = useI18n()
  const [entityInsight, setEntityInsight] = useState<EntityInsightKey>('risk')
  const [entityPanelSection, setEntityPanelSection] = useState<EntityPanelSection>('overview')

  const entityInsightContent = (() => {
    if (!entityDetail) {
      return null
    }

    const tags = entityDetail.entity.tags.slice(0, 4)
    const inboundCount = entityDetail.inbound.length
    const outboundCount = entityDetail.outbound.length

    if (entityInsight === 'kind') {
      return {
        title: t('Why this entity matters'),
        body: t('{kind} discovered from {source} in the {environment} estate.', {
          kind: t(kindLabel(entityDetail.entity.kind)),
          source: entityDetail.entity.source,
          environment: entityDetail.entity.environment,
        }),
        bullets: [
          t('{count} inbound relationships reference this entity.', { count: inboundCount }),
          t('{count} outbound relationships originate from this entity.', { count: outboundCount }),
          tags.length
            ? t('Observed tags: {value}.', { value: tags.join(', ') })
            : t('No extra classification tags were attached.'),
        ],
      }
    }

    if (entityInsight === 'criticality') {
      return {
        title: t('How criticality is interpreted'),
        body:
          t('Criticality is the business importance score assigned by the normalization pipeline. Higher values usually indicate entities tied to sensitive resources, privileged routes or important operational scope.'),
        bullets: [
          t('Current score: {value}.', { value: entityDetail.entity.criticality }),
          tags.length
            ? t('Current classification signals: {value}.', { value: tags.join(', ') })
            : t('Current classification is based on the entity profile only.'),
          entityDetail.entity.owner
            ? t('Owner context: {value}.', { value: entityDetail.entity.owner })
            : t('No explicit owner was recorded for this entity.'),
        ],
      }
    }

    return {
      title: t('Why the risk score is elevated'),
      body:
        t('Risk is derived from effective permissions, privilege indicators, indirect grant paths and breadth of exposure. It is meant to explain urgency, not hide it behind a black-box score.'),
      bullets: [
        t('Current risk score: {value}.', { value: entityDetail.entity.risk_score }),
        t(
          '{inbound} inbound and {outbound} outbound relationships contribute to the current exposure graph.',
          { inbound: inboundCount, outbound: outboundCount },
        ),
        tags.length
          ? t('Important context: {value}.', { value: tags.join(', ') })
          : t('No special tags amplified the risk context for this entity.'),
      ],
    }
  })()

  function renderRiskHeadline(finding: EntityDetailResponse['risk_findings'][number]) {
    if (finding.category === 'overexposed-resource' && finding.resource) {
      return t('{value} is broadly exposed', { value: finding.resource.name })
    }
    if (
      (finding.category === 'indirect-privileged-access' ||
        finding.category === 'direct-privileged-access') &&
      finding.principal &&
      finding.resource
    ) {
      return t('{principal} reaches {resource} with privileged rights', {
        principal: finding.principal.name,
        resource: finding.resource.name,
      })
    }
    if (finding.category === 'broad-privileged-group' && finding.principal) {
      return t('{value} grants privileged access to a broad membership', {
        value: finding.principal.name,
      })
    }
    if (finding.category === 'excessive-nesting' && finding.principal && finding.resource) {
      return t('{principal} reaches {resource} through deep nesting', {
        principal: finding.principal.name,
        resource: finding.resource.name,
      })
    }
    return finding.headline
  }

  function renderRiskDetail(finding: EntityDetailResponse['risk_findings'][number]) {
    if (finding.category === 'overexposed-resource') {
      return t('{principals} privileged principals currently reach this resource.', {
        principals: finding.affected_principal_count,
      })
    }
    if (
      finding.category === 'indirect-privileged-access' ||
      finding.category === 'direct-privileged-access'
    ) {
      return t(
        'This entitlement is currently materialized as privileged effective access in the index.',
      )
    }
    if (finding.category === 'broad-privileged-group') {
      return t(
        '{principals} direct members are currently covered by this privileged group path.',
        {
          principals: finding.affected_principal_count,
        },
      )
    }
    if (finding.category === 'excessive-nesting') {
      return t(
        'This access depends on multiple nested groups before the effective grant is applied.',
      )
    }
    return finding.detail
  }

  function renderChangeSummary(change: EntityDetailResponse['recent_changes'][number]) {
    if (change.change_type === 'scan_completed') {
      return t(
        '{status} scan processed {resources} resources and {relationships} relationships across {targets} targets.',
        {
          status: t(change.status),
          resources: change.resource_count,
          relationships: change.relationship_count,
          targets: change.target_count,
        },
      )
    }
    return change.summary
  }

  return (
    <>
      <div className="workspace-main">
        {investigateSection === 'explain' ? (
          <article className="panel">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Question Studio')}</div>
                <h2>{t('Why does this access exist?')}</h2>
              </div>
            </div>

            <div className="control-grid">
              <label className="field">
                <span>{t('Principal')}</span>
                <select
                  value={selectedPrincipalId}
                  onChange={(event) => onSelectPrincipal(event.target.value)}
                >
                  {principalOptions.map((principal) => (
                    <option key={principal.id} value={principal.id}>
                      {principal.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>{t('Resource')}</span>
                <select
                  value={selectedResourceId}
                  onChange={(event) => onSelectResource(event.target.value)}
                >
                  {resourceOptions.map((resource) => (
                    <option key={resource.id} value={resource.id}>
                      {resource.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="summary-strip">
              <div className="summary-chip">
                <span>{t('Permissions')}</span>
                <strong>{explanation?.permissions.join(', ') ?? 'n/d'}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Paths')}</span>
                <strong>{explanation?.path_count ?? 0}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Risk')}</span>
                <strong>{explanation?.risk_score ?? 0}</strong>
              </div>
            </div>

            {!selectedResourceId ? (
              <div className="context-hint">
                {t('Select a resource from the catalog to materialize the explain path.')}
              </div>
            ) : explanation?.path_count === 0 ? (
              <div className="context-hint">
                {t(
                  'No effective access path is currently materialized for this principal-resource pair. Try another resource or switch to Exposure to inspect who currently reaches the resource.',
                )}
              </div>
            ) : null}

            <Suspense fallback={<div className="empty-state">{t('Loading graph view...')}</div>}>
              <AccessGraph graph={explanation?.graph} paths={explanation?.paths} />
            </Suspense>

            <div className="dense-graph-toggle">
              <button className="mini-action" type="button" onClick={onToggleDenseGraph}>
                {showDenseGraph ? t('Hide investigation graph') : t('Open investigation graph')}
              </button>
              {showDenseGraph ? (
                <div className="dense-graph-toggle__controls">
                  <label className="table-toolbar__page-size">
                    <span>{t('Depth')}</span>
                    <select
                      value={graphDepth}
                      onChange={(event) => onChangeGraphDepth(Number(event.target.value))}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                    </select>
                  </label>
                  <label className="table-toolbar__page-size">
                    <span>{t('Density')}</span>
                    <select
                      value={graphDensityProfile}
                      onChange={(event) =>
                        onChangeGraphDensityProfile(event.target.value as 'compact' | 'expanded')
                      }
                    >
                      <option value="compact">{t('Compact')}</option>
                      <option value="expanded">{t('Expanded')}</option>
                    </select>
                  </label>
                </div>
              ) : null}
            </div>

            {showDenseGraph ? (
              <Suspense fallback={<div className="empty-state">{t('Loading graph view...')}</div>}>
                <GraphExplorer
                  graph={graphSubgraph?.graph}
                  focusId={graphSubgraph?.focus.id ?? entityDetail?.entity.id ?? null}
                  truncated={graphSubgraph?.truncated ?? false}
                  nodeLimit={graphSubgraph?.node_limit ?? 0}
                  edgeLimit={graphSubgraph?.edge_limit ?? 0}
                />
              </Suspense>
            ) : null}

            <div className="path-list">
              {explanation?.paths.map((path, index) => (
                <article key={`${path.access_mode}-${index}`} className="path-card">
                  <div className="path-card__meta">
                    <span className="kind-pill">{t(path.access_mode)}</span>
                    <span className="risk-pill">{t('risk {value}', { value: path.risk_score })}</span>
                  </div>
                  <p>{t(path.narrative)}</p>
                  <div className="step-list">
                    {path.steps.map((step) => (
                      <span key={step.edge_id} className="step-pill">
                        {step.label}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </article>
        ) : null}

        {investigateSection === 'exposure' ? (
          <article className="panel">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Who Has Access')}</div>
                <h2>{resourceAccess?.resource.name ?? t('Selected resource')}</h2>
              </div>
              <div className="panel__stats">
                <span>{resourceAccess?.total_principals ?? 0} {t('principals')}</span>
                <span>{resourceAccess?.privileged_principal_count ?? 0} {t('privileged')}</span>
              </div>
            </div>
            <AccessTable
              records={resourceAccess?.records ?? []}
              totalCount={resourceAccess?.total_principals ?? 0}
              offset={resourceAccess?.offset ?? 0}
              limit={resourceAccess?.limit ?? 25}
              hasMore={resourceAccess?.has_more ?? false}
              loading={resourceAccessLoading}
              onPaginationChange={onChangeResourceAccessWindow}
            />
          </article>
        ) : null}

        {investigateSection === 'whatif' ? (
          <article className="panel">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('What If')}</div>
                <h2>{t('Blast radius simulation')}</h2>
              </div>
            </div>

            {!canSimulate ? (
              <div className="empty-state">
                {t('Your current application role can inspect access but cannot run what-if simulations.')}
              </div>
            ) : null}

            <div className="control-grid control-grid--tight">
              <label className="field field--wide">
                <span>{t('Change to simulate')}</span>
                <select
                  value={selectedScenarioEdgeId}
                  onChange={(event) => onSelectScenario(event.target.value)}
                  disabled={!canSimulate}
                >
                  {scenarioOptions.map((scenario) => (
                    <option key={scenario.edge_id} value={scenario.edge_id}>
                      {scenario.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>{t('Focus resource')}</span>
                <select
                  value={scenarioFocusResourceId ?? ''}
                  onChange={(event) => onSelectScenarioFocusResource(event.target.value)}
                  disabled={!canSimulate}
                >
                  {resourceOptions.map((resource) => (
                    <option key={resource.id} value={resource.id}>
                      {resource.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <p className="scenario-reason">
              {t(activeScenarioReason ?? simulation?.narrative ?? t('Scenario reasoning not available.'))}
            </p>

            <div className="impact-strip">
              <div className="impact-card">
                <span>{t('Impacted principals')}</span>
                <strong>{simulation?.impacted_principals ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Impacted resources')}</span>
                <strong>{simulation?.impacted_resources ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Removed paths')}</span>
                <strong>{simulation?.removed_paths ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Privileged removed')}</span>
                <strong>{simulation?.privileged_paths_removed ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Delta principals')}</span>
                <strong>{simulation?.recomputed_principals ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Delta resources')}</span>
                <strong>{simulation?.recomputed_resources ?? 0}</strong>
              </div>
              <div className="impact-card">
                <span>{t('Delta pairs')}</span>
                <strong>{simulation?.recomputed_pairs ?? 0}</strong>
              </div>
            </div>

            {canSimulate ? (
              <Suspense fallback={<div className="empty-state">{t('Loading simulation view...')}</div>}>
                <WhatIfFlow flow={simulation?.flow} />
              </Suspense>
            ) : null}
          </article>
        ) : null}
      </div>

      <aside className="workspace-side">
        {investigateSection === 'explain' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Focused Entity')}</div>
                <h2>{entityDetail?.entity.name ?? t('No entity selected')}</h2>
              </div>
            </div>
            {entityDetail ? (
              <>
                <p className="entity-description">{t(entityDetail.entity.description)}</p>
                <div className="workspace-subtabs workspace-subtabs--stacked workspace-subtabs--entity">
                  {(['overview', 'grants', 'risk', 'changes'] as const).map((section) => (
                    <button
                      key={section}
                      type="button"
                      className={`workspace-subtab ${
                        entityPanelSection === section ? 'workspace-subtab--active' : ''
                      }`}
                      onClick={() => setEntityPanelSection(section)}
                    >
                      {section === 'overview'
                        ? t('Access Overview')
                        : section === 'grants'
                          ? t('Grants and paths')
                          : section === 'risk'
                            ? t('Risk Findings')
                            : t('Change History')}
                    </button>
                  ))}
                </div>
                <div className="summary-strip summary-strip--stacked">
                  <button
                    type="button"
                    className={`summary-chip summary-chip--button ${
                      entityInsight === 'kind' ? 'summary-chip--active' : ''
                    }`}
                    onClick={() => setEntityInsight('kind')}
                  >
                    <span>{t('Kind')}</span>
                    <strong>{t(kindLabel(entityDetail.entity.kind))}</strong>
                  </button>
                  <button
                    type="button"
                    className={`summary-chip summary-chip--button ${
                      entityInsight === 'criticality' ? 'summary-chip--active' : ''
                    }`}
                    onClick={() => setEntityInsight('criticality')}
                  >
                    <span>{t('Criticality')}</span>
                    <strong>{entityDetail.entity.criticality}</strong>
                  </button>
                  <button
                    type="button"
                    className={`summary-chip summary-chip--button ${
                      entityInsight === 'risk' ? 'summary-chip--active' : ''
                    }`}
                    onClick={() => setEntityInsight('risk')}
                  >
                    <span>{t('Risk')}</span>
                    <strong>{entityDetail.entity.risk_score}</strong>
                  </button>
                </div>

                {entityPanelSection === 'overview' ? (
                  <>
                    {entityDetail.overview_metrics.length ? (
                      <div className="summary-strip summary-strip--stacked">
                        {entityDetail.overview_metrics.map((metric) => (
                          <div key={metric.title} className="summary-chip">
                            <span>{t(metric.title)}</span>
                            <strong>{metric.value}</strong>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {entityInsightContent ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('Why this matters')}</div>
                          <span className="kind-pill">
                            {entityInsight === 'kind'
                              ? t('Kind')
                              : entityInsight === 'criticality'
                                ? t('Criticality')
                                : t('Risk')}
                          </span>
                        </div>
                        <div className="table-primary">{entityInsightContent.title}</div>
                        <p className="entity-description">{t(entityInsightContent.body)}</p>
                        <div className="context-list">
                          {entityInsightContent.bullets.map((item) => (
                            <div key={item} className="context-list__item">
                              {t(item)}
                            </div>
                          ))}
                        </div>
                      </article>
                    ) : null}
                    {entityDetail.principal_access.length ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('User view')}</div>
                          <span className="kind-pill">{t('Access Overview')}</span>
                        </div>
                        <div className="list-stack">
                          {entityDetail.principal_access.slice(0, 4).map((record) => (
                            <div key={record.resource.id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{record.resource.name}</div>
                                <div className="table-secondary">{record.permissions.join(', ')}</div>
                              </div>
                              <span className="risk-pill">{record.risk_score}</span>
                            </div>
                          ))}
                        </div>
                      </article>
                    ) : null}
                    {entityDetail.resource_access.length ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('Resource view')}</div>
                          <span className="kind-pill">{t('Who Has Access')}</span>
                        </div>
                        <div className="list-stack">
                          {entityDetail.resource_access.slice(0, 4).map((record) => (
                            <div key={record.principal.id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{record.principal.name}</div>
                                <div className="table-secondary">{record.permissions.join(', ')}</div>
                              </div>
                              <span className="risk-pill">{record.risk_score}</span>
                            </div>
                          ))}
                        </div>
                      </article>
                    ) : null}
                  </>
                ) : null}

                {entityPanelSection === 'grants' ? (
                  <>
                    <article className="context-card">
                      <div className="context-card__header">
                        <div className="eyebrow">{t('Direct Grants')}</div>
                        <span className="kind-pill">{entityDetail.direct_grants.length}</span>
                      </div>
                      {entityDetail.direct_grants.length ? (
                        <div className="list-stack">
                          {entityDetail.direct_grants.slice(0, 6).map((step) => (
                            <div key={step.edge_id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{step.label}</div>
                                <div className="table-secondary">{step.permissions.join(', ') || step.rationale}</div>
                              </div>
                              <span className="kind-pill">{step.edge_kind}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">{t('No direct grant is currently modeled for this entity.')}</div>
                      )}
                    </article>
                    <article className="context-card">
                      <div className="context-card__header">
                        <div className="eyebrow">{t('Inherited Grants')}</div>
                        <span className="kind-pill">{entityDetail.inherited_grants.length}</span>
                      </div>
                      {entityDetail.inherited_grants.length ? (
                        <div className="list-stack">
                          {entityDetail.inherited_grants.slice(0, 6).map((step) => (
                            <div key={step.edge_id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{step.label}</div>
                                <div className="table-secondary">{step.permissions.join(', ') || step.rationale}</div>
                              </div>
                              <span className="kind-pill">{t('Inherited')}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">{t('No inherited grant is currently modeled for this entity.')}</div>
                      )}
                    </article>
                    {entityDetail.perspective === 'resource' ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('Inheritance Chain')}</div>
                          <span className="kind-pill">{entityDetail.resource_hierarchy.length}</span>
                        </div>
                        {entityDetail.resource_hierarchy.length ? (
                          <div className="list-stack">
                            {entityDetail.resource_hierarchy.slice(0, 6).map((record) => (
                              <div
                                key={`${record.ancestor.id}-${record.depth}`}
                                className="list-row list-row--static"
                              >
                                <div>
                                  <div className="table-primary">{record.ancestor.name}</div>
                                  <div className="table-secondary">
                                    {t('Depth')}: {record.depth}
                                  </div>
                                </div>
                                <span className="kind-pill">
                                  {record.inherits_acl ? t('Inherited') : t('Direct')}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="empty-state">
                            {t('No resource hierarchy closure is currently materialized for this entity.')}
                          </div>
                        )}
                      </article>
                    ) : null}
                    <article className="context-card">
                      <div className="context-card__header">
                        <div className="eyebrow">{t('Group Paths')}</div>
                        <span className="kind-pill">{entityDetail.group_paths.length}</span>
                      </div>
                      {entityDetail.group_paths.length ? (
                        <div className="list-stack">
                          {entityDetail.group_paths.slice(0, 6).map((step) => (
                            <div key={step.edge_id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{step.source.name} → {step.target.name}</div>
                                <div className="table-secondary">{step.rationale}</div>
                              </div>
                              <span className="kind-pill">{step.edge_kind}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">{t('No group path is currently modeled for this entity.')}</div>
                      )}
                    </article>
                    {entityDetail.perspective === 'principal' ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('Effective Groups')}</div>
                          <span className="kind-pill">{entityDetail.group_closure.length}</span>
                        </div>
                        {entityDetail.group_closure.length ? (
                          <div className="list-stack">
                            {entityDetail.group_closure.slice(0, 6).map((record) => (
                              <div
                                key={`${record.group.id}-${record.shortest_parent.id}`}
                                className="list-row list-row--static"
                              >
                                <div>
                                  <div className="table-primary">{record.group.name}</div>
                                  <div className="table-secondary">
                                    {t('Depth')}: {record.depth} | {t('Parent')}: {record.shortest_parent.name}
                                  </div>
                                </div>
                                <span className="kind-pill">
                                  {t('Paths')}: {record.path_count}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="empty-state">
                            {t('No effective group closure is currently materialized for this entity.')}
                          </div>
                        )}
                      </article>
                    ) : null}
                    <article className="context-card">
                      <div className="context-card__header">
                        <div className="eyebrow">{t('Role Paths')}</div>
                        <span className="kind-pill">{entityDetail.role_paths.length}</span>
                      </div>
                      {entityDetail.role_paths.length ? (
                        <div className="list-stack">
                          {entityDetail.role_paths.slice(0, 6).map((step) => (
                            <div key={step.edge_id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{step.source.name} -&gt; {step.target.name}</div>
                                <div className="table-secondary">{step.rationale}</div>
                              </div>
                              <span className="kind-pill">{step.edge_kind}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">{t('No role path is currently modeled for this entity.')}</div>
                      )}
                    </article>
                  </>
                ) : null}

                {entityPanelSection === 'risk' ? (
                  <>
                    {entityDetail.admin_rights.length ? (
                      <article className="context-card">
                        <div className="context-card__header">
                          <div className="eyebrow">{t('Admin Rights')}</div>
                          <span className="kind-pill">{entityDetail.admin_rights.length}</span>
                        </div>
                        <div className="list-stack">
                          {entityDetail.admin_rights.map((record) => (
                            <div key={record.resource.id} className="list-row list-row--static">
                              <div>
                                <div className="table-primary">{record.resource.name}</div>
                                <div className="table-secondary">{record.permissions.join(', ')}</div>
                              </div>
                              <span className="risk-pill">{record.risk_score}</span>
                            </div>
                          ))}
                        </div>
                      </article>
                    ) : null}
                    <article className="context-card">
                      <div className="context-card__header">
                        <div className="eyebrow">{t('Risk Findings')}</div>
                        <span className="kind-pill">{entityDetail.risk_findings.length}</span>
                      </div>
                      {entityDetail.risk_findings.length ? (
                        <div className="insight-list">
                          {entityDetail.risk_findings.map((finding) => (
                            <article key={finding.id} className={`insight-card insight-card--${finding.severity}`}>
                              <div className="insight-card__header">
                                <span>{renderRiskHeadline(finding)}</span>
                                <span className={`status-pill status-pill--${finding.severity}`}>
                                  {t(toneLabel(finding.severity))}
                                </span>
                              </div>
                              <p>{renderRiskDetail(finding)}</p>
                            </article>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">{t('No risk finding is currently linked to this entity.')}</div>
                      )}
                    </article>
                  </>
                ) : null}

                {entityPanelSection === 'changes' ? (
                  <article className="context-card">
                    <div className="context-card__header">
                      <div className="eyebrow">{t('Change History')}</div>
                      <span className="kind-pill">{entityDetail.recent_changes.length}</span>
                    </div>
                    {entityDetail.recent_changes.length ? (
                      <div className="list-stack">
                        {entityDetail.recent_changes.map((change) => (
                          <div key={change.id} className="list-row list-row--static">
                            <div>
                              <div className="table-primary">{renderChangeSummary(change)}</div>
                              <div className="table-secondary">{formatDateTime(change.occurred_at)}</div>
                            </div>
                            <span className={`status-pill status-pill--${change.status === 'failed' ? 'critical' : change.status === 'warning' ? 'warning' : 'healthy'}`}>
                              {t(change.status)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-state">{t('No recent change was recorded for the current environment.')}</div>
                    )}
                  </article>
                ) : null}
              </>
            ) : (
              <div className="empty-state">{t('Select any entity to inspect its neighborhood.')}</div>
            )}
          </article>
        ) : null}

        {investigateSection !== 'whatif' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Signals')}</div>
                <h2>{t('Privilege drift over recent scans')}</h2>
              </div>
            </div>
            <div className="history-chart">
              {history.map((point) => (
                <div key={point.day} className="history-bar-group">
                  <div
                    className="history-bar"
                    style={{
                      height: `${(point.privileged_paths / historyMax) * 120}px`,
                    }}
                  />
                  <span>{point.day.slice(5)}</span>
                </div>
              ))}
            </div>
          </article>
        ) : null}

        {investigateSection !== 'explain' ? (
          <article className="panel panel--compact">
            <div className="panel__header">
              <div>
                <div className="eyebrow">{t('Insights')}</div>
                <h2>{t('Operator notes')}</h2>
              </div>
            </div>
            <div className="insight-list">
              {insights.map((insight) => (
                <article key={insight.title} className={`insight-card insight-card--${insight.tone}`}>
                  <div className="insight-card__header">
                    <span>{t(insight.title)}</span>
                    <span className={`status-pill status-pill--${insight.tone}`}>
                      {t(toneLabel(insight.tone))}
                    </span>
                  </div>
                  <p>{t(insight.body)}</p>
                </article>
              ))}
            </div>
          </article>
        ) : null}
      </aside>
    </>
  )
}
