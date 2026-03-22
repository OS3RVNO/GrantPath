import { useState } from 'react'

import { MetricCard } from '../MetricCard'
import { useI18n } from '../../i18n'

import type {
  ChangeRecord,
  FeatureInventoryResponse,
  HistoricalPoint,
  Hotspot,
  InsightNote,
  MetricCard as MetricCardType,
  MvpReadinessResponse,
  OperationalFlowResponse,
  RiskFinding,
  Tone,
} from '../../types'

interface HomeDashboardProps {
  metrics: MetricCardType[]
  hotspots: Hotspot[]
  insights: InsightNote[]
  history: HistoricalPoint[]
  historyMax: number
  mvpReadiness: MvpReadinessResponse | null
  featureInventory: FeatureInventoryResponse | null
  operationalFlow: OperationalFlowResponse | null
  riskFindings: RiskFinding[]
  recentChanges: ChangeRecord[]
  onOpenInvestigate: () => void
  onOpenGovern: () => void
  onOpenSources: () => void
  onOpenOperations: () => void
  onOpenReadinessAction: (workspace: string, section?: string | null) => void
  toneLabel: (tone: Tone) => string
}

export function HomeDashboard({
  metrics,
  hotspots,
  insights,
  history,
  historyMax,
  mvpReadiness,
  featureInventory,
  operationalFlow,
  riskFindings,
  recentChanges,
  onOpenInvestigate,
  onOpenGovern,
  onOpenSources,
  onOpenOperations,
  onOpenReadinessAction,
  toneLabel,
}: HomeDashboardProps) {
  const { t, formatDateTime } = useI18n()
  const [selectedChecklistId, setSelectedChecklistId] = useState<string | null>(
    null,
  )
  const [selectedInventoryCategoryId, setSelectedInventoryCategoryId] = useState<string | null>(
    null,
  )
  const [selectedInventoryItemId, setSelectedInventoryItemId] = useState<string | null>(
    null,
  )
  const [selectedFlowStepId, setSelectedFlowStepId] = useState<string | null>(null)
  const hiddenAdminRights = riskFindings.filter((finding) =>
    finding.category.includes('privileged'),
  )
  const selectedChecklistItem =
    mvpReadiness?.checklist.find((item) => item.id === selectedChecklistId) ?? mvpReadiness?.checklist[0] ?? null
  const selectedInventoryCategory =
    featureInventory?.categories.find((category) => category.id === selectedInventoryCategoryId) ??
    featureInventory?.categories[0] ??
    null
  const selectedInventoryItem =
    selectedInventoryCategory?.items.find((item) => item.id === selectedInventoryItemId) ??
    selectedInventoryCategory?.items[0] ??
    null
  const selectedFlowStep =
    operationalFlow?.steps.find((step) => step.id === selectedFlowStepId) ??
    operationalFlow?.steps.find((step) => step.status !== 'ready') ??
    operationalFlow?.steps[0] ??
    null

  function operationalFlowDestination(stepId: string) {
    switch (stepId) {
      case 'bootstrap-admin':
      case 'sign-in-plane':
      case 'local-mfa':
        return { workspace: 'sources', section: 'auth' }
      case 'target-coverage':
      case 'raw-ingestion':
        return { workspace: 'sources', section: 'collection' }
      case 'materialized-index':
        return { workspace: 'investigate', section: 'explain' }
      case 'connector-readiness':
        return { workspace: 'operations', section: 'platform' }
      case 'governance-loop':
        return { workspace: 'govern', section: 'reviews' }
      default:
        return { workspace: 'operations', section: 'status' }
    }
  }

  function renderRiskHeadline(finding: RiskFinding) {
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

  function renderRiskDetail(finding: RiskFinding) {
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

  function renderChangeSummary(change: ChangeRecord) {
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
    if (change.change_type === 'access_drift_detected') {
      return t(
        'Detected {added} added, {removed} removed and {changed} changed entitlements across {principals} principals and {resources} resources.',
        {
          added: change.added_access_count,
          removed: change.removed_access_count,
          changed: change.changed_access_count,
          principals: change.affected_principal_count,
          resources: change.affected_resource_count,
        },
      )
    }
    return change.summary
  }

  return (
    <section className="home-grid">
      <article className="panel">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Command Center')}</div>
            <h2>{t('Start from the shortest path to action')}</h2>
          </div>
        </div>
        <p className="admin-copy">
          {t(
            'Use this home to monitor the platform quickly, then jump into the specific workspace only when you need to investigate, govern, manage sources or review operations.',
          )}
        </p>
        <div className="quick-action-grid">
          <button className="quick-action-card" type="button" onClick={onOpenInvestigate}>
            <span className="eyebrow">{t('Investigate')}</span>
            <strong>{t('Answer who has access and why')}</strong>
          </button>
          <button className="quick-action-card" type="button" onClick={onOpenGovern}>
            <span className="eyebrow">{t('Govern')}</span>
            <strong>{t('Run reviews and export evidence')}</strong>
          </button>
          <button className="quick-action-card" type="button" onClick={onOpenSources}>
            <span className="eyebrow">{t('Sources')}</span>
            <strong>{t('Manage auth, targets and imports')}</strong>
          </button>
          <button className="quick-action-card" type="button" onClick={onOpenOperations}>
            <span className="eyebrow">{t('Operations')}</span>
            <strong>{t('Track scan health and platform posture')}</strong>
          </button>
        </div>
      </article>

      <section className="metric-grid metric-grid--dashboard">
        {metrics.map((metric) => (
          <MetricCard key={metric.title} metric={metric} />
        ))}
      </section>

      <article className="panel">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Pilot launchpad')}</div>
            <h2>{t('Walk the shortest path from setup to first evidence')}</h2>
          </div>
          {operationalFlow ? (
            <div className="panel__stats">
              <span>{operationalFlow.completion_percent}% {t('complete')}</span>
              <span>{operationalFlow.next_actions.length} {t('Open actions')}</span>
            </div>
          ) : null}
        </div>
        <p className="admin-copy">
          {t(
            'Use this guided flow to complete the minimum viable setup, collect the first live snapshot, validate explainability and produce evidence an operator can trust.',
          )}
        </p>
        {operationalFlow ? (
          <div className="mvp-checklist">
            <div className="mvp-checklist__items">
              {operationalFlow.steps.map((step) => (
                <button
                  key={step.id}
                  type="button"
                  className={`mvp-checklist__item ${
                    selectedFlowStep?.id === step.id ? 'mvp-checklist__item--active' : ''
                  }`}
                  onClick={() => setSelectedFlowStepId(step.id)}
                >
                  <div>
                    <div className="table-primary">{t(step.title)}</div>
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
                      ? t('ready')
                      : step.status === 'action_required'
                        ? t('Action')
                        : t('Progress')}
                  </span>
                </button>
              ))}
            </div>
            {selectedFlowStep ? (
              <article className="context-card">
                <div className="context-card__header">
                  <div className="eyebrow">{t('Step-by-step rollout')}</div>
                  <span className="kind-pill">{t(selectedFlowStep.title)}</span>
                </div>
                <p className="entity-description">
                  {t(
                    'Use the recommended action below to keep the MVP rollout moving and generate your first trustworthy evidence.',
                  )}
                </p>
                <div className="context-list">
                  <div className="context-list__item">
                    {t('Recommended action: {value}', {
                      value: t(selectedFlowStep.recommended_action),
                    })}
                  </div>
                  <div className="context-list__item">
                    {t('Overall status')}: {t(selectedFlowStep.status === 'ready' ? 'Ready' : selectedFlowStep.status === 'action_required' ? 'Action' : 'Progress')}
                  </div>
                </div>
                <div className="panel__actions">
                  <button
                    type="button"
                    className="mini-action mini-action--primary"
                    onClick={() => {
                      const destination = operationalFlowDestination(selectedFlowStep.id)
                      onOpenReadinessAction(destination.workspace, destination.section)
                    }}
                  >
                    {t('Open next guided step')}
                  </button>
                </div>
              </article>
            ) : null}
          </div>
        ) : (
          <div className="empty-state">
            {t('Operational readiness is calculated after authentication.')}
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('MVP Readiness')}</div>
            <h2>{t('What still needs attention')}</h2>
          </div>
          {mvpReadiness ? (
            <div className="panel__stats">
              <span>{mvpReadiness.completion_percent}% {t('complete')}</span>
              <span>{t(mvpReadiness.freshness.status)}</span>
            </div>
          ) : null}
        </div>
        {mvpReadiness ? (
          <>
            <div className="summary-strip summary-strip--stacked">
              <div className="summary-chip">
                <span>{t('Status')}</span>
                <strong>{t(mvpReadiness.overall_status.replace('_', ' '))}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Freshness')}</span>
                <strong>{t(mvpReadiness.freshness.status)}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Scope')}</span>
                <strong>{mvpReadiness.primary_scope}</strong>
              </div>
            </div>

            <div className="mvp-checklist">
              <div className="mvp-checklist__items">
                {mvpReadiness.checklist.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`mvp-checklist__item ${
                      selectedChecklistItem?.id === item.id ? 'mvp-checklist__item--active' : ''
                    }`}
                    onClick={() => setSelectedChecklistId(item.id)}
                  >
                    <div>
                      <div className="table-primary">{t(item.title)}</div>
                      <div className="table-secondary">{t(item.summary)}</div>
                    </div>
                    <span
                      className={`status-pill status-pill--${
                        item.status === 'ready'
                          ? 'healthy'
                          : item.status === 'action_required'
                            ? 'critical'
                            : 'warning'
                      }`}
                    >
                      {item.status === 'ready'
                        ? t('ready')
                        : item.status === 'action_required'
                          ? t('Action')
                          : t('Progress')}
                    </span>
                  </button>
                ))}
              </div>

              {selectedChecklistItem ? (
                <article className="context-card">
                  <div className="context-card__header">
                    <div className="eyebrow">{t('Selected Step')}</div>
                    <span className="kind-pill">
                      {selectedChecklistItem.required ? t('required') : t('recommended')}
                    </span>
                  </div>
                  <div className="table-primary">{t(selectedChecklistItem.title)}</div>
                  <p className="entity-description">{t(selectedChecklistItem.why_it_matters)}</p>
                  <div className="context-list">
                    <div className="context-list__item">{t(selectedChecklistItem.summary)}</div>
                    <div className="context-list__item">
                      {t('Recommended action: {value}', {
                        value: t(selectedChecklistItem.recommended_action),
                      })}
                    </div>
                    <div className="context-list__item">
                      {t('Data freshness: {value}', {
                        value: t(mvpReadiness.freshness.summary),
                      })}
                    </div>
                  </div>
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="mini-action mini-action--primary"
                      onClick={() =>
                        onOpenReadinessAction(
                          selectedChecklistItem.workspace,
                          selectedChecklistItem.section,
                        )
                      }
                    >
                      {t('Open relevant section')}
                    </button>
                  </div>
                </article>
              ) : null}
            </div>

            {mvpReadiness.blockers.length ? (
              <div className="context-hint">
                {t('Blockers: {value}', { value: mvpReadiness.blockers.join(' | ') })}
              </div>
            ) : null}
          </>
        ) : (
          <div className="empty-state">
            {t('MVP readiness becomes available after the first authenticated refresh.')}
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Real feature coverage')}</div>
            <h2>{t('What the app really does today')}</h2>
          </div>
          {featureInventory ? (
            <div className="panel__stats">
              <span>{featureInventory.present_count} {t('present')}</span>
              <span>{featureInventory.partial_count} {t('partial')}</span>
              <span>{featureInventory.missing_count} {t('missing')}</span>
            </div>
          ) : null}
        </div>
        {featureInventory ? (
          <>
            <p className="admin-copy">{t(featureInventory.primary_scope)}</p>
            <div className="summary-strip summary-strip--stacked">
              <div className="summary-chip">
                <span>{t('Required gaps')}</span>
                <strong>{featureInventory.required_missing.length}</strong>
              </div>
              <div className="summary-chip">
                <span>{t('Status')}</span>
                <strong>{t(featureInventory.overall_status.replace('_', ' '))}</strong>
              </div>
            </div>
            <div className="mvp-checklist">
              <div className="mvp-checklist__items">
                {featureInventory.categories.map((category) => (
                  <button
                    key={category.id}
                    type="button"
                    className={`mvp-checklist__item ${
                      selectedInventoryCategory?.id === category.id ? 'mvp-checklist__item--active' : ''
                    }`}
                    onClick={() => {
                      setSelectedInventoryCategoryId(category.id)
                      setSelectedInventoryItemId(category.items[0]?.id ?? null)
                    }}
                  >
                    <div>
                      <div className="table-primary">{t(category.title)}</div>
                      <div className="table-secondary">{t(category.summary)}</div>
                    </div>
                    <span className="kind-pill">
                      {category.present_count}/{category.items.length}
                    </span>
                  </button>
                ))}
              </div>
              {selectedInventoryCategory ? (
                <article className="context-card">
                  <div className="context-card__header">
                    <div className="eyebrow">{t('Capability inventory')}</div>
                    <span className="kind-pill">{t(selectedInventoryCategory.title)}</span>
                  </div>
                  <p className="entity-description">{t(selectedInventoryCategory.summary)}</p>
                  <div className="context-list">
                    {selectedInventoryCategory.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`list-row list-row--static list-row--button ${
                          selectedInventoryItem?.id === item.id ? 'list-row--active' : ''
                        }`}
                        onClick={() => setSelectedInventoryItemId(item.id)}
                      >
                        <div>
                          <div className="table-primary">{t(item.title)}</div>
                          <div className="table-secondary">{t(item.summary)}</div>
                        </div>
                        <span
                          className={`status-pill status-pill--${
                            item.status === 'present'
                              ? 'healthy'
                              : item.status === 'partial'
                                ? 'warning'
                                : 'critical'
                          }`}
                        >
                          {t(item.status)}
                        </span>
                      </button>
                    ))}
                  </div>
                  {selectedInventoryItem ? (
                    <div className="context-list">
                      <div className="context-list__item">
                        {t('Gap: {value}', { value: t(selectedInventoryItem.gap) })}
                      </div>
                      <div className="context-list__item">
                        {t('Recommended action: {value}', {
                          value: t(selectedInventoryItem.recommended_action),
                        })}
                      </div>
                    </div>
                  ) : null}
                  {selectedInventoryItem ? (
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="mini-action mini-action--primary"
                        onClick={() =>
                          onOpenReadinessAction(
                            selectedInventoryItem.workspace,
                            selectedInventoryItem.section,
                          )
                        }
                      >
                        {t('Open relevant section')}
                      </button>
                    </div>
                  ) : null}
                </article>
              ) : null}
            </div>
            {featureInventory.required_missing.length ? (
              <div className="context-hint">
                {t('Required gaps: {value}', {
                  value: featureInventory.required_missing.join(' | '),
                })}
              </div>
            ) : null}
          </>
        ) : (
          <div className="empty-state">
            {t('Feature inventory becomes available after the first authenticated refresh.')}
          </div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Top Exposure')}</div>
            <h2>{t('Most exposed resources')}</h2>
          </div>
        </div>
        {hotspots.length ? (
          <div className="hotspot-list">
            {hotspots.map((hotspot) => (
              <article key={hotspot.resource.id} className="hotspot-card">
                <div className="insight-card__header">
                  <span>{hotspot.resource.name}</span>
                  <span className="risk-pill">{hotspot.exposure_score}</span>
                </div>
                <p>{t(hotspot.headline)}</p>
                <div className="target-card__meta">
                  <span>{hotspot.privileged_principal_count} {t('privileged principals')}</span>
                  <span>{hotspot.delegated_path_count} {t('delegated paths')}</span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t('No exposure hotspot is available yet.')}</div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Suggested Actions')}</div>
            <h2>{t('What deserves attention now')}</h2>
          </div>
        </div>
        {insights.length ? (
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
        ) : (
          <div className="empty-state">{t('No operator insight is available yet.')}</div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Risk Dashboard')}</div>
            <h2>{t('Top risk findings')}</h2>
          </div>
        </div>
        {riskFindings.length ? (
          <div className="insight-list">
            {riskFindings.slice(0, 4).map((finding) => (
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
          <div className="empty-state">{t('No risk finding is available yet.')}</div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Hidden Admin Rights')}</div>
            <h2>{t('Indirect privileged paths')}</h2>
          </div>
        </div>
        <div className="summary-strip summary-strip--stacked">
          <div className="summary-chip">
            <span>{t('Findings')}</span>
            <strong>{hiddenAdminRights.length}</strong>
          </div>
          <div className="summary-chip">
            <span>{t('Suggested cleanups')}</span>
            <strong>{insights.length}</strong>
          </div>
        </div>
        {hiddenAdminRights.length ? (
          <div className="context-list">
            {hiddenAdminRights.slice(0, 3).map((finding) => (
              <div key={finding.id} className="context-list__item">
                {finding.headline}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t('No hidden admin right is currently flagged.')}</div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Recently Changed Access')}</div>
            <h2>{t('Latest processing events')}</h2>
          </div>
        </div>
        {recentChanges.length ? (
          <div className="list-stack">
            {recentChanges.slice(0, 4).map((change) => (
              <article key={change.id} className="list-row list-row--static">
                <div>
                  <div className="table-primary">{renderChangeSummary(change)}</div>
                  <div className="table-secondary">{formatDateTime(change.occurred_at)}</div>
                </div>
                <span className={`status-pill status-pill--${change.status === 'healthy' || change.status === 'success' ? 'healthy' : change.status === 'failed' ? 'critical' : 'warning'}`}>
                  {t(change.status)}
                </span>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t('No recent platform change is available yet.')}</div>
        )}
      </article>

      <article className="panel panel--compact">
        <div className="panel__header">
          <div>
            <div className="eyebrow">{t('Recent Trend')}</div>
            <h2>{t('Privilege drift snapshot')}</h2>
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
    </section>
  )
}
