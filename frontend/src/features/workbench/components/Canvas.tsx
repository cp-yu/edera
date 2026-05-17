import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useAppStore } from '@/store/useAppStore'
import { CustomNode } from './nodes/CustomNode'
import type { DagState, RuntimeStatus } from '@/api/types'

const nodeTypes = { custom: CustomNode }

interface Props {
  dag: DagState | null
  runtimeStatus: RuntimeStatus | null
  isRunning: boolean
}

export function Canvas({ dag, runtimeStatus, isRunning }: Props) {
  const { selectedNodeId, setSelectedNode, targetFilter } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!dag) return
    const uiPositions = dag.ui?.nodes ?? {}
    const newNodes: Node[] = dag.nodes.map((n, i) => {
      const pos = uiPositions[n.name] ?? { x: 100 + (i % 4) * 200, y: 80 + Math.floor(i / 4) * 120 }
      const status = runtimeStatus?.node_statuses?.[n.name]
      return {
        id: n.name,
        type: 'custom',
        position: pos,
        data: { ...n, status: status?.status, error: status?.error },
        selected: n.name === selectedNodeId,
      }
    })
    const newEdges: Edge[] = dag.edges.map((e, i) => ({
      id: `e-${i}`,
      source: e.from,
      target: e.to,
      animated: isRunning,
    }))
    setNodes(newNodes)
    setEdges(newEdges)
  }, [dag, runtimeStatus, isRunning, selectedNodeId, setNodes, setEdges])

  const styledNodes = useMemo(() => {
    if (targetFilter.length === 0) return nodes
    return nodes.map((n) => {
      const data = n.data as Record<string, unknown>
      const nodeTargets: string[] = (data.source_names as string[]) ?? []
      const matches = targetFilter.length === 0 || nodeTargets.some((t) => targetFilter.includes(t))
      return { ...n, style: { ...(n.style ?? {}), opacity: matches ? 1 : 0.2 } }
    })
  }, [nodes, targetFilter])

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id)
  }, [setSelectedNode])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [setSelectedNode])

  return (
    <ReactFlow
      nodes={styledNodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      nodeTypes={nodeTypes}
      fitView
      className="bg-background"
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  )
}
