import type { AccessPath, EntityKind, GraphPayload } from '../types'
import { useI18n } from '../i18n'

interface AccessGraphProps {
  graph?: GraphPayload
  paths?: AccessPath[]
}

type StageNode = {
  id: string
  label: string
  kind: EntityKind
  source: string
}

function buildStageNodes(path: AccessPath): StageNode[] {
  if (path.steps.length === 0) {
    return []
  }

  const nodes: StageNode[] = [
    {
      id: path.steps[0].source.id,
      label: path.steps[0].source.name,
      kind: path.steps[0].source.kind,
      source: path.steps[0].source.source,
    },
  ]

  for (const step of path.steps) {
    nodes.push({
      id: step.target.id,
      label: step.target.name,
      kind: step.target.kind,
      source: step.target.source,
    })
  }

  return nodes
}

function kindLabel(kind: EntityKind) {
  return kind.replace('_', ' ')
}

export function AccessGraph({ graph, paths }: AccessGraphProps) {
  const { t } = useI18n()
  const visiblePaths = (paths ?? []).slice(0, 3)

  if (visiblePaths.length === 0) {
    return <div className="empty-state">{t('No graph to render for this access path.')}</div>
  }

  const nodeCount =
    graph?.nodes.length ??
    new Set(visiblePaths.flatMap((path) => buildStageNodes(path).map((node) => node.id))).size
  const edgeCount =
    graph?.edges.length ??
    visiblePaths.reduce((total, path) => total + path.steps.length, 0)

  return (
    <section className="access-map">
      <header className="access-map__header">
        <div>
          <div className="eyebrow">{t('Access Map')}</div>
          <div className="access-map__title">
            {t('Clean path view for the selected entitlement')}
          </div>
          <p className="access-map__copy">
            {t(
              'Each lane shows the effective route from identity to resource, with one transition per step.',
            )}
          </p>
        </div>
        <div className="access-map__stats">
          <div className="access-map__stat">
            <span>{t('Nodes')}</span>
            <strong>{nodeCount}</strong>
          </div>
          <div className="access-map__stat">
            <span>{t('Links')}</span>
            <strong>{edgeCount}</strong>
          </div>
        </div>
      </header>

      <div className="access-map__lanes">
        {visiblePaths.map((path, pathIndex) => {
          const nodes = buildStageNodes(path)

          return (
            <article key={`${path.access_mode}-${pathIndex}`} className="access-map__lane">
              <div className="access-map__lane-header">
                <div className="table-primary">{t('Path {index}', { index: pathIndex + 1 })}</div>
                <div className="access-map__lane-tags">
                  <span className="kind-pill">{path.access_mode}</span>
                  <span className="risk-pill">{t('risk {value}', { value: path.risk_score })}</span>
                  {path.permissions.map((permission) => (
                    <span key={permission} className="permission-chip">
                      {permission}
                    </span>
                  ))}
                </div>
              </div>

              <div className="access-map__scroll">
                <div className="access-map__track">
                  {nodes.map((node, nodeIndex) => (
                    <div key={`${pathIndex}-${node.id}-${nodeIndex}`} className="access-map__segment">
                      <div className={`access-map__node access-map__node--${node.kind}`}>
                        <div className="access-map__node-kind">{t(kindLabel(node.kind))}</div>
                        <div className="access-map__node-label">{node.label}</div>
                        <div className="access-map__node-source">{node.source}</div>
                      </div>

                      {nodeIndex < path.steps.length ? (
                        <div className="access-map__transition">
                          <div className="access-map__transition-arrow" />
                          <div className="access-map__transition-kind">
                            {t(path.steps[nodeIndex].edge_kind.replaceAll('_', ' '))}
                          </div>
                          <div className="access-map__transition-label">
                            {path.steps[nodeIndex].label}
                          </div>
                          <div className="access-map__transition-meta">
                            {path.steps[nodeIndex].rationale}
                          </div>
                          <div className="access-map__transition-permissions">
                            {(path.steps[nodeIndex].permissions.length > 0
                              ? path.steps[nodeIndex].permissions
                              : [path.steps[nodeIndex].edge_kind.replaceAll('_', ' ')]).map(
                              (item) => (
                                <span key={item} className="permission-chip permission-chip--muted">
                                  {t(item)}
                                </span>
                              ),
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {paths && paths.length > visiblePaths.length ? (
        <div className="access-map__footer">
          {t('Showing the top {visible} paths out of {total} to keep the view readable.', {
            visible: visiblePaths.length,
            total: paths.length,
          })}
        </div>
      ) : null}
    </section>
  )
}
