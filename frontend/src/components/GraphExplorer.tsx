import CytoscapeComponent from 'react-cytoscapejs'

import type { GraphPayload } from '../types'
import { useI18n } from '../i18n'

interface GraphExplorerProps {
  graph?: GraphPayload | null
  focusId?: string | null
  truncated?: boolean
  nodeLimit?: number
  edgeLimit?: number
}

export function GraphExplorer({
  graph,
  focusId,
  truncated = false,
  nodeLimit = 0,
  edgeLimit = 0,
}: GraphExplorerProps) {
  const { t } = useI18n()

  if (!graph || graph.nodes.length === 0) {
    return <div className="empty-state">{t('No investigation graph is available for this focus yet.')}</div>
  }

  const elements = [
    ...graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        kind: node.kind,
        source: node.source,
        focus: node.id === focusId ? 'true' : 'false',
      },
      classes: `${node.kind} ${node.id === focusId ? 'focus' : ''}`,
    })),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
      },
      classes: edge.highlighted ? 'highlighted' : '',
    })),
  ]

  return (
    <section className="graph-explorer">
      <header className="graph-explorer__header">
        <div>
          <div className="eyebrow">{t('Investigation graph')}</div>
          <div className="access-map__title">
            {t('Dense neighborhood view for the focused entity')}
          </div>
          <p className="access-map__copy">
            {t(
              'Use the dense graph to inspect nearby grants, memberships and inherited routes without collapsing everything into a single path.',
            )}
          </p>
        </div>
        <div className="access-map__stats">
          <div className="access-map__stat">
            <span>{t('Nodes')}</span>
            <strong>{graph.nodes.length}</strong>
          </div>
          <div className="access-map__stat">
            <span>{t('Links')}</span>
            <strong>{graph.edges.length}</strong>
          </div>
        </div>
      </header>
      {truncated ? (
        <div className="context-hint">
          {t('This investigation graph is currently capped to {nodes} nodes and {edges} links so the view stays responsive.', {
            nodes: nodeLimit,
            edges: edgeLimit,
          })}
        </div>
      ) : null}
      <div className="graph-canvas graph-canvas--dense">
        <CytoscapeComponent
          elements={elements}
          style={{ width: '100%', height: '100%' }}
          layout={{
            name: 'breadthfirst',
            fit: true,
            padding: 28,
            spacingFactor: 1.15,
            animate: false,
            directed: true,
          }}
          stylesheet={[
            {
              selector: 'node',
              style: {
                'background-color': '#d9e7ff',
                color: '#10201f',
                label: 'data(label)',
                'font-family': 'IBM Plex Sans',
                'font-size': 11,
                'font-weight': 700,
                'text-wrap': 'wrap',
                'text-max-width': 130,
                'text-valign': 'center',
                'text-halign': 'center',
                padding: '14px',
                shape: 'round-rectangle',
                'border-width': 1,
                'border-color': '#4d6fb3',
                width: 150,
                height: 68,
              },
            },
            {
              selector: 'node.resource',
              style: {
                'background-color': '#f8dbc9',
                'border-color': '#cc845f',
              },
            },
            {
              selector: 'node.group',
              style: {
                'background-color': '#e9efe5',
                'border-color': '#6b8d67',
              },
            },
            {
              selector: 'node.role',
              style: {
                'background-color': '#f2e7bf',
                'border-color': '#a3841f',
              },
            },
            {
              selector: 'node.focus',
              style: {
                'border-width': 3,
                'border-color': '#0b615a',
                'background-color': '#d8f0ea',
              },
            },
            {
              selector: 'edge',
              style: {
                width: 2,
                'line-color': '#7d918e',
                'target-arrow-color': '#7d918e',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                label: 'data(label)',
                'font-family': 'IBM Plex Sans',
                'font-size': 9,
                'text-rotation': 'autorotate',
                'text-margin-y': -8,
                'text-background-color': '#fffaf4',
                'text-background-opacity': 0.92,
                'text-background-padding': 2,
                color: '#506462',
              },
            },
            {
              selector: 'edge.highlighted',
              style: {
                width: 3,
                'line-color': '#c85c35',
                'target-arrow-color': '#c85c35',
              },
            },
          ]}
          cy={(cy: { minZoom: (value: number) => void; maxZoom: (value: number) => void }) => {
            cy.minZoom(0.35)
            cy.maxZoom(2.4)
          }}
        />
      </div>
    </section>
  )
}
