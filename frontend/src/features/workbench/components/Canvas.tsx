import { useCallback, useEffect, useMemo, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useNodesState,
  useEdgesState,
  useReactFlow,
  addEdge,
  type Node,
  type Edge,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Dagre from '@dagrejs/dagre'
import { useAppStore } from '@/store/useAppStore'
import { CustomNode } from './nodes/CustomNode'
import { useCreateNode } from '@/api/mutations'
import type { DagState, RuntimeStatus } from '@/api/types'

const nodeTypes = { custom: CustomNode }

interface Props {
  dag: DagState | null
  runtimeStatus: RuntimeStatus | null
  isRunning: boolean
}

export function Canvas({ dag, runtimeStatus, isRunning }: Props) {
  const { selectedNodeId, setSelectedNode, targetFilter, selectedDagName } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const { screenToFlowPosition } = useReactFlow()
  const createNode = useCreateNode()
  const prevDagRef = useRef<DagState | null>(null)

  // A1: Only rebuild nodes/edges when dag data changes
  useEffect(() => {
    if (!dag) return
    if (prevDagRef.current === dag) return
    prevDagRef.current = dag

    const uiPositions = dag.ui?.nodes ?? {}
    const uiEdges = dag.ui?.edges ?? {}
    const newNodes: Node[] = dag.nodes.map((n, i) => {
      const pos = uiPositions[n.name] ?? { x: 100 + (i % 4) * 200, y: 80 + Math.floor(i / 4) * 120 }
      return {
        id: n.name,
        type: 'custom',
        position: pos,
        data: { ...n },
      }
    })
    const newEdges: Edge[] = dag.edges.map((e, i) => {
      const edgeId = `e-${e.from}-${e.to}-${i}`
      const uiMeta = uiEdges[edgeId]
      return {
        id: edgeId,
        source: e.from,
        target: e.to,
        sourceHandle: e.sourceHandle ?? uiMeta?.sourceHandle,
        targetHandle: e.targetHandle ?? uiMeta?.targetHandle,
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: isRunning,
      }
    })
    setNodes(newNodes)
    setEdges(newEdges)
  }, [dag, isRunning, setNodes, setEdges])

  // Inject runtime status into node data without rebuilding positions
  useEffect(() => {
    if (!runtimeStatus) return
    setNodes((nds) =>
      nds.map((n) => {
        const st = runtimeStatus.node_statuses?.[n.id]
        if (!st) return n
        const prev = n.data as Record<string, unknown>
        if (prev.status === st.status && prev.error === st.error) return n
        return { ...n, data: { ...prev, status: st.status, error: st.error } }
      }),
    )
  }, [runtimeStatus, setNodes])

  // A3: onConnect creates new edge
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, markerEnd: { type: MarkerType.ArrowClosed } }, eds))
    },
    [setEdges],
  )

  // A4: onDragOver + onDrop for Palette drag-to-add
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const nodeName = event.dataTransfer.getData('application/reactflow')
      if (!nodeName) return
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      createNode.mutate({ dagName: selectedDagName, body: { name: nodeName } })
      // Optimistically add to canvas
      setNodes((nds) => [
        ...nds,
        {
          id: nodeName,
          type: 'custom',
          position,
          data: { name: nodeName, type: 'unknown', input_type: '', output_type: '', skills: [] },
        },
      ])
    },
    [screenToFlowPosition, createNode, selectedDagName, setNodes],
  )

  const styledNodes = useMemo(() => {
    if (targetFilter.length === 0) return nodes
    return nodes.map((n) => {
      const data = n.data as Record<string, unknown>
      const nodeTargets: string[] = (data.source_names as string[]) ?? []
      const matches = nodeTargets.some((t) => targetFilter.includes(t))
      return { ...n, style: { ...(n.style ?? {}), opacity: matches ? 1 : 0.2 } }
    })
  }, [nodes, targetFilter])

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id)
  }, [setSelectedNode])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [setSelectedNode])

  // A6: Auto-layout using dagre
  const onAutoLayout = useCallback(() => {
    const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 })
    nodes.forEach((n) => g.setNode(n.id, { width: 150, height: 50 }))
    edges.forEach((e) => g.setEdge(e.source, e.target))
    Dagre.layout(g)
    setNodes((nds) =>
      nds.map((n) => {
        const pos = g.node(n.id)
        return { ...n, position: { x: pos.x - 75, y: pos.y - 25 } }
      }),
    )
  }, [nodes, edges, setNodes])

  return (
    <ReactFlow
      nodes={styledNodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      onDragOver={onDragOver}
      onDrop={onDrop}
      deleteKeyCode="Delete"
      nodeTypes={nodeTypes}
      fitView
      className="bg-background"
    >
      <Background />
      <Controls />
      <MiniMap />
      <Panel position="top-right">
        <button
          onClick={onAutoLayout}
          className="rounded-md border bg-card px-3 py-1.5 text-xs shadow-sm hover:bg-accent/50"
        >
          自动布局
        </button>
      </Panel>
    </ReactFlow>
  )
}

