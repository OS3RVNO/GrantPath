import {
  BackgroundVariant,
  Background,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
} from '@xyflow/react'

import type { FlowPayload } from '../types'
import { useI18n } from '../i18n'

interface WhatIfFlowProps {
  flow?: FlowPayload
}

export function WhatIfFlow({ flow }: WhatIfFlowProps) {
  const { t } = useI18n()
  if (!flow || flow.nodes.length === 0) {
    return <div className="empty-state">{t('Run a scenario to render blast radius.')}</div>
  }

  const nodes = flow.nodes.map((node) => ({
    id: node.id,
    position: { x: node.x, y: node.y },
    data: { label: t(node.label) },
    draggable: false,
    selectable: false,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    style:
      node.kind === 'change'
        ? {
            background: '#11201f',
            color: '#fffaf4',
            border: '1px solid #11201f',
            borderRadius: 20,
            padding: 14,
            width: 200,
          }
        : node.kind === 'principal'
          ? {
              background: '#dde8fb',
              color: '#18345f',
              border: '1px solid #315fab',
              borderRadius: 16,
              padding: 12,
              width: 200,
            }
          : {
              background: '#f5dcc6',
              color: '#5f2d1b',
              border: '1px solid #c85c35',
              borderRadius: 16,
              padding: 12,
              width: 220,
            },
  }))

  const edges = flow.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: t(edge.label),
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#5f726f',
    },
    style: {
      stroke: '#5f726f',
      strokeWidth: 1.8,
    },
    labelStyle: {
      fill: '#1f3431',
      fontWeight: 700,
    },
    labelBgStyle: {
      fill: '#fffaf4',
      fillOpacity: 0.95,
    },
  }))

  return (
    <div className="flow-canvas">
      <ReactFlow
        fitView
        fitViewOptions={{ padding: 0.18, minZoom: 0.45 }}
        nodes={nodes}
        edges={edges}
        nodesConnectable={false}
        nodesDraggable={false}
        zoomOnScroll={false}
        panOnScroll
        minZoom={0.4}
        maxZoom={1.4}
        proOptions={{ hideAttribution: true }}
      >
        <Controls showInteractive={false} />
        <Background color="#d6d8d1" gap={18} variant={BackgroundVariant.Dots} />
      </ReactFlow>
    </div>
  )
}
