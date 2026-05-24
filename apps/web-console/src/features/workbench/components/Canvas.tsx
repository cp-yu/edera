import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useReactFlow,
  useViewport,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
  type Connection,
  type NodeMouseHandler,
  ViewportPortal,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import ELK from 'elkjs'
import { useAppStore } from '@/store/useAppStore'
import { CustomNode } from './nodes/CustomNode'
import { useRetryDagNode, useSaveDag } from '@/api/mutations'
import { useNodePrototypes } from '@/api/queries'
import { entityColor } from '@/lib/colors'
import type { DagNodeRecord, DagState, NodeInstance, NodeType, RuntimeStatus } from '@/api/types'
import { CanvasContextMenu } from './CanvasContextMenu'
import { QuickAddPanel } from './QuickAddPanel'
import {
  buildSearchItems,
  calculateGuideLines,
  clearDraftIfMatch,
  createWorkbenchEdge,
  createWorkbenchNode,
  enrichNodeData,
  filterSearchItems,
  getEdgeColor,
  getHandleSpecs,
  getNodeEdgeColor,
  getNodeSize,
  getRuntimeEdgeStates,
  isValidConnection,
  isWarningConnection,
  normalizeDagEdges,
  normalizeWorkbenchEdges,
  readDraft,
  type DagDraft,
  writeDraft,
  toDagDraft,
  type ContextMenuState,
  type GraphSnapshot,
  type GuideLine,
  type WorkbenchEdge,
  type WorkbenchNode,
} from '../lib/graph'

const nodeTypes = { custom: CustomNode }
const elk = new ELK()
const GRID_SIZE = 4
const SNAP_GRID: [number, number] = [GRID_SIZE, GRID_SIZE]
const HISTORY_LIMIT = 50
const MIN_ZOOM = 0.01
const FIT_VIEW_PADDING = 0.24
const FIT_VIEW_FRAME_DELAY = 2

function createInstance(prototype: NodeType): NodeInstance {
  return {
    ...prototype,
    id: crypto.randomUUID(),
    type_name: prototype.name,
    alias: prototype.name,
    config: {},
  }
}

function hydrateInstance(
  instance: NodeInstance | DagNodeRecord,
  prototypes: Map<string, NodeType>,
): NodeInstance | null {
  const typeName = 'type_name' in instance ? instance.type_name : instance.type
  const prototype = prototypes.get(typeName)
  if (!prototype) return null
  const config = instance.config ?? {}
  return {
    ...prototype,
    ...instance,
    name: prototype.name,
    type: prototype.type,
    type_name: typeName,
    role: prototype.role,
    input_type: prototype.input_type,
    output_type: prototype.output_type,
    handler: prototype.handler,
    system_prompt_file: prototype.system_prompt_file,
    config,
    skills: Array.isArray(config.skills) ? config.skills.map(String) : prototype.skills,
    model: typeof config.model === 'string' ? config.model : prototype.model,
    timeout_seconds: typeof config.timeout_seconds === 'number' ? config.timeout_seconds : prototype.timeout_seconds,
    entities: Array.isArray(config.entities) ? config.entities.map(String) : prototype.entities,
    parameters: typeof config.parameters === 'object' && config.parameters
      ? config.parameters as Record<string, unknown>
      : prototype.parameters,
  }
}

interface Props {
  dag: DagState | null
  runtimeStatus: RuntimeStatus | null
  isRunning: boolean
}

export function Canvas({ dag, runtimeStatus, isRunning: _isRunning }: Props) {
  const { setInspectorTab, setSelectedEdge, setSelectedNode, entityFilter, selectedDagName } = useAppStore()
  const { data: prototypesData } = useNodePrototypes()
  const saveDag = useSaveDag(selectedDagName)
  const retryNode = useRetryDagNode()
  const { screenToFlowPosition, fitView } = useReactFlow<WorkbenchNode, WorkbenchEdge>()
  const viewport = useViewport()
  const canvasRef = useRef<HTMLDivElement>(null)
  const saveTimerRef = useRef<number | null>(null)
  const nodesRef = useRef<WorkbenchNode[]>([])
  const edgesRef = useRef<WorkbenchEdge[]>([])
  const historyRef = useRef<GraphSnapshot[]>([])
  const historyIndexRef = useRef(-1)
  const applyingHistoryRef = useRef(false)
  const [nodes, setNodes] = useState<WorkbenchNode[]>([])
  const [edges, setEdges] = useState<WorkbenchEdge[]>([])
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [guideLines, setGuideLines] = useState<GuideLine[]>([])
  const [connectionSourceId, setConnectionSourceId] = useState<string | null>(null)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const pendingDraftRef = useRef<string | null>(null)

  const prototypes = prototypesData?.prototypes ?? []
  const prototypeMap = useMemo(() => new Map(prototypes.map((node) => [node.name, node])), [prototypes])

  useEffect(() => {
    nodesRef.current = nodes
  }, [nodes])

  useEffect(() => {
    edgesRef.current = edges
  }, [edges])

  const fitCanvasToGraph = useCallback((duration = 0) => {
    let frame = 0

    const schedule = () => {
      if (frame >= FIT_VIEW_FRAME_DELAY) {
        void fitView({
          padding: FIT_VIEW_PADDING,
          minZoom: MIN_ZOOM,
          duration,
          includeHiddenNodes: true,
        })
        return
      }

      frame += 1
      window.requestAnimationFrame(schedule)
    }

    window.requestAnimationFrame(schedule)
  }, [fitView])

  const persistGraph = useCallback((nextNodes: WorkbenchNode[], nextEdges: WorkbenchEdge[]) => {
    if (!dag) return
    const draft = toDagDraft(nextNodes, nextEdges)
    const serializedDraft = JSON.stringify(draft)
    pendingDraftRef.current = serializedDraft
    writeDraft(selectedDagName, draft)
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => {
      saveDag.mutate({
        nodes: draft.nodes,
        edges: draft.edges,
        ui: draft.ui,
      })
    }, 500)
  }, [dag, saveDag, selectedDagName])

  useEffect(() => {
    if (saveDag.isSuccess && pendingDraftRef.current) {
      clearDraftIfMatch(selectedDagName, pendingDraftRef.current)
      pendingDraftRef.current = null
    }
  }, [saveDag.isSuccess, selectedDagName])

  const recordHistory = useCallback((nextNodes: WorkbenchNode[], nextEdges: WorkbenchEdge[]) => {
    if (applyingHistoryRef.current) return
    const snapshot: GraphSnapshot = {
      nodes: nextNodes.map((node) => ({ ...node, position: { ...node.position }, data: { ...node.data } })),
      edges: nextEdges.map((edge) => ({
        ...edge,
        data: edge.data ? { ...edge.data } : edge.data,
        style: edge.style ? { ...edge.style } : edge.style,
        markerEnd: edge.markerEnd,
      })),
    }
    const base = historyRef.current.slice(0, historyIndexRef.current + 1)
    base.push(snapshot)
    if (base.length > HISTORY_LIMIT) base.shift()
    historyRef.current = base
    historyIndexRef.current = base.length - 1
  }, [])

  const commitGraph = useCallback((
    nextNodes: WorkbenchNode[],
    nextEdges: WorkbenchEdge[],
    options?: { persist?: boolean; recordHistory?: boolean },
  ) => {
    setNodes(nextNodes)
    setEdges(nextEdges)
    if (options?.recordHistory !== false) recordHistory(nextNodes, nextEdges)
    if (options?.persist !== false) persistGraph(nextNodes, nextEdges)
  }, [persistGraph, recordHistory])

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (!dag) {
      setNodes([])
      setEdges([])
      historyRef.current = []
      historyIndexRef.current = -1
      return
    }

    const draft = readDraft(selectedDagName)
    const source: DagDraft | DagState = draft ?? dag
    const uiPositions = source.ui?.nodes ?? {}
    const sourceEdges = normalizeDagEdges(source.edges.map((edge, index) => ({
      ...edge,
      sourceHandle: edge.sourceHandle ?? source.ui?.edges?.[`e-${edge.from}-${edge.to}-${index}`]?.sourceHandle,
      targetHandle: edge.targetHandle ?? source.ui?.edges?.[`e-${edge.from}-${edge.to}-${index}`]?.targetHandle,
    })))

    const nodeData = source.nodes.flatMap((node, index) => {
      const hydrated = hydrateInstance(node, prototypeMap)
      if (!hydrated) return []
      const position = uiPositions[hydrated.id] ?? { x: 120 + (index % 4) * 260, y: 80 + Math.floor(index / 4) * 170 }
      return [createWorkbenchNode(hydrated, position, sourceEdges, runtimeStatus)]
    })
    const nodeMap = new Map(nodeData.map((node) => [node.id, node.data]))
    const edgeData = sourceEdges.map((edge, index) => createWorkbenchEdge(edge, index, nodeMap, runtimeStatus))

    setNodes(nodeData)
    setEdges(edgeData)
    historyRef.current = [{ nodes: nodeData, edges: edgeData }]
    historyIndexRef.current = 0
    fitCanvasToGraph()
  }, [dag, fitCanvasToGraph, runtimeStatus, selectedDagName])

  useEffect(() => {
    if (!runtimeStatus) return
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        const nextData = enrichNodeData(node.data, edgesRef.current, runtimeStatus)
        if (nextData.status === node.data.status && nextData.error === node.data.error) return node
        return { ...node, data: nextData }
      }),
    )
    setEdges((currentEdges) => {
      const nodeMap = new Map(nodesRef.current.map((node) => [node.id, node.data]))
      const edgeStates = getRuntimeEdgeStates(currentEdges, runtimeStatus)
      return currentEdges.map((edge) => {
        const sourceKind = nodeMap.get(edge.source)?.visualKind ?? 'unknown'
        const targetState = edgeStates.get(edge.id)
        const color = getEdgeColor(sourceKind, targetState)
        return {
          ...edge,
          data: { visualState: targetState },
          markerEnd: { type: MarkerType.ArrowClosed, color },
          style: {
            ...(edge.style ?? {}),
            stroke: color,
            strokeWidth: targetState ? 3 : 2,
          },
        }
      })
    })
  }, [runtimeStatus])

  useEffect(() => {
    if (runtimeStatus) return
    setEdges((currentEdges) => {
      const nodeMap = new Map(nodesRef.current.map((node) => [node.id, node.data]))
      return currentEdges.map((edge) => {
        const sourceKind = nodeMap.get(edge.source)?.visualKind ?? 'unknown'
        const color = getNodeEdgeColor(sourceKind)
        return {
          ...edge,
          data: { visualState: undefined },
          markerEnd: { type: MarkerType.ArrowClosed, color },
          style: {
            ...(edge.style ?? {}),
            stroke: color,
            strokeWidth: 2,
          },
        }
      })
    })
  }, [runtimeStatus])

  const onConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodesRef.current.find((node) => node.id === connection.source)
      const targetNode = nodesRef.current.find((node) => node.id === connection.target)
      if (!isValidConnection(sourceNode?.data, targetNode?.data)) return
      if (connection.source && connection.target && createsCycle(connection.source, connection.target, edgesRef.current)) {
        setToastMessage('连线会形成环，已拒绝')
        return
      }
      const warning = isWarningConnection(sourceNode?.data, targetNode?.data)
      const color = warning ? '#ca8a04' : getNodeEdgeColor(sourceNode?.data.visualKind ?? 'unknown')
      const nextEdges = normalizeWorkbenchEdges(addEdge(
        {
          ...connection,
          type: 'default',
          markerEnd: { type: MarkerType.ArrowClosed, color },
          style: { stroke: color, strokeWidth: 2, strokeDasharray: warning ? '6 4' : undefined },
          data: { warning },
        },
        edgesRef.current,
      ) as WorkbenchEdge[])
      const nextNodes = nodesRef.current.map((node) => ({
        ...node,
        data: enrichNodeData(node.data, nextEdges, runtimeStatus),
      }))
      commitGraph(nextNodes, nextEdges)
    },
    [commitGraph, runtimeStatus],
  )

  useEffect(() => {
    if (!toastMessage) return
    const timer = window.setTimeout(() => setToastMessage(null), 2400)
    return () => window.clearTimeout(timer)
  }, [toastMessage])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const addExistingNode = useCallback((prototypeName: string, position: { x: number; y: number }) => {
    const prototype = prototypeMap.get(prototypeName)
    if (!prototype) return

    const instance = createInstance(prototype)
    const nextNode = createWorkbenchNode(instance, position, edgesRef.current, runtimeStatus)
    const nextNodes = [...nodesRef.current, nextNode]
    commitGraph(nextNodes, edgesRef.current)
    setSelectedNode(nextNode.id)
  }, [commitGraph, prototypeMap, runtimeStatus, setSelectedNode])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const nodeName = event.dataTransfer.getData('application/reactflow')
      if (!nodeName) return
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      addExistingNode(nodeName, position)
    },
    [addExistingNode, screenToFlowPosition],
  )

  const styledNodes = useMemo(() => {
    const source = nodes.find((node) => node.id === connectionSourceId)
    const visibleNodes = entityFilter.length === 0 ? nodes : nodes.map((n) => {
      const nodeEntities = n.data.entities ?? []
      const matches = nodeEntities.some((entity) => entityFilter.includes(entity))
      return { ...n, style: { ...(n.style ?? {}), opacity: matches ? 1 : 0.2 } }
    })
    if (!source) return visibleNodes
    return visibleNodes.map((node) => {
      if (node.id === source.id) return { ...node, data: { ...node.data, connectionState: undefined } }
      return {
        ...node,
        data: {
          ...node.data,
          connectionState: isValidConnection(source.data, node.data) ? 'valid' as const : 'invalid' as const,
        },
      }
    })
  }, [connectionSourceId, nodes, entityFilter])

  const searchItems = useMemo(
    () => filterSearchItems(buildSearchItems(prototypes, nodes.map((node) => node.data)), searchQuery),
    [nodes, prototypes, searchQuery],
  )

  const groupedEntities = useMemo(() => {
    const groups = new Map<string, WorkbenchNode[]>()

    for (const node of nodes) {
      for (const entity of node.data.entities ?? []) {
        const list = groups.get(entity) ?? []
        list.push(node)
        groups.set(entity, list)
      }
    }

    return Array.from(groups.entries()).map(([entity, groupedNodes]) => {
      const padding = 30
      const positions = groupedNodes.map((node) => {
        const size = getNodeSize(node.data.visualKind)
        return {
          left: node.position.x,
          top: node.position.y,
          right: node.position.x + size.width,
          bottom: node.position.y + size.height,
        }
      })

      const minLeft = Math.min(...positions.map((item) => item.left)) - padding
      const minTop = Math.min(...positions.map((item) => item.top)) - padding
      const maxRight = Math.max(...positions.map((item) => item.right)) + padding
      const maxBottom = Math.max(...positions.map((item) => item.bottom)) + padding

      return {
        entity,
        x: minLeft,
        y: minTop,
        width: maxRight - minLeft,
        height: maxBottom - minTop,
        color: entityColor(entity),
      }
    })
  }, [nodes])

  const onNodeClick = useCallback((_: React.MouseEvent, node: WorkbenchNode) => {
    setSelectedNode(node.id)
  }, [setSelectedNode])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
    setSelectedEdge(null)
    setContextMenu(null)
  }, [setSelectedEdge, setSelectedNode])

  const onNodesChange = useCallback((changes: NodeChange<WorkbenchNode>[]) => {
    setNodes((currentNodes) => applyNodeChanges(changes, currentNodes))
  }, [])

  const onEdgesChange = useCallback((changes: EdgeChange<WorkbenchEdge>[]) => {
    setEdges((currentEdges) => applyEdgeChanges(changes, currentEdges))
  }, [])

  const onNodeDrag: NodeMouseHandler<WorkbenchNode> = useCallback((_, activeNode) => {
    setGuideLines(calculateGuideLines(nodesRef.current, activeNode))
  }, [])

  const onNodeDragStop: NodeMouseHandler<WorkbenchNode> = useCallback(() => {
    setGuideLines([])
    persistGraph(nodesRef.current, edgesRef.current)
    recordHistory(nodesRef.current, edgesRef.current)
  }, [persistGraph, recordHistory])

  const onAutoLayout = useCallback(async () => {
    const currentNodes = nodesRef.current
    const currentEdges = edgesRef.current
    const elkNodes = currentNodes.map((node) => {
      const size = getNodeSize(node.data.visualKind)
      const handles = getHandleSpecs(node.id, node.data, currentEdges)
      return {
        id: node.id,
        width: size.width,
        height: size.height,
        layoutOptions: {
          'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
        },
        ports: [
          ...handles.inputHandles.map((handle, index) => ({
            id: `${node.id}:${handle.id}`,
            layoutOptions: {
              'org.eclipse.elk.port.side': 'WEST',
              'org.eclipse.elk.port.index': String(index),
            },
          })),
          ...handles.outputHandles.map((handle, index) => ({
            id: `${node.id}:${handle.id}`,
            layoutOptions: {
              'org.eclipse.elk.port.side': 'EAST',
              'org.eclipse.elk.port.index': String(index),
            },
          })),
        ],
      }
    })

    const layout = await elk.layout({
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.layered.spacing.nodeNodeBetweenLayers': '110',
        'elk.spacing.nodeNode': '70',
        'org.eclipse.elk.layered.portSortingStrategy': 'INPUT_ORDER',
      },
      children: elkNodes,
      edges: currentEdges.map((edge) => ({
        id: edge.id,
        sources: [`${edge.source}:${edge.sourceHandle ?? 'output-0'}`],
        targets: [`${edge.target}:${edge.targetHandle ?? 'input-0'}`],
      })),
    })

    const nextNodes = currentNodes.map((node) => {
      const layoutNode = layout.children?.find((child) => child.id === node.id)
      if (!layoutNode) return node
      return {
        ...node,
        position: {
          x: layoutNode.x ?? node.position.x,
          y: layoutNode.y ?? node.position.y,
        },
      }
    })

    commitGraph(nextNodes, currentEdges)
    fitCanvasToGraph(180)
  }, [commitGraph, fitCanvasToGraph])

  const closeContextMenu = useCallback(() => setContextMenu(null), [])

  const deleteEdgeById = useCallback((edgeId: string) => {
    const nextEdges = edgesRef.current.filter((edge) => edge.id !== edgeId)
    const nextNodes = nodesRef.current.map((node) => ({
      ...node,
      data: enrichNodeData(node.data, nextEdges, runtimeStatus),
    }))
    commitGraph(nextNodes, nextEdges)
  }, [commitGraph, runtimeStatus])

  const reverseEdgeById = useCallback((edgeId: string) => {
    const reversed = edgesRef.current.map((edge) =>
      edge.id === edgeId
        ? {
            ...edge,
            source: edge.target,
            target: edge.source,
          }
        : edge,
    )
    const nextEdges = normalizeWorkbenchEdges(reversed).map((edge) => {
      const sourceNode = nodesRef.current.find((node) => node.id === edge.source)
      const color = getNodeEdgeColor(sourceNode?.data.visualKind ?? 'unknown')
      return {
        ...edge,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { ...(edge.style ?? {}), stroke: color },
      }
    })
    const nextNodes = nodesRef.current.map((node) => ({
      ...node,
      data: enrichNodeData(node.data, nextEdges, runtimeStatus),
    }))
    commitGraph(nextNodes, nextEdges)
  }, [commitGraph, runtimeStatus])

  const deleteNodeById = useCallback((nodeId: string) => {
    if (!nodesRef.current.some((node) => node.id === nodeId)) return
    const nextNodes = nodesRef.current.filter((node) => node.id !== nodeId)
    const nextEdges = normalizeWorkbenchEdges(edgesRef.current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId))
    const hydratedNodes = nextNodes.map((node) => ({
      ...node,
      data: enrichNodeData(node.data, nextEdges, runtimeStatus),
    }))
    commitGraph(hydratedNodes, nextEdges)
    setSelectedNode(null)
  }, [commitGraph, runtimeStatus, setSelectedNode])

  const disconnectNodeById = useCallback((nodeId: string) => {
    const nextEdges = normalizeWorkbenchEdges(edgesRef.current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId))
    const nextNodes = nodesRef.current.map((node) => ({
      ...node,
      data: enrichNodeData(node.data, nextEdges, runtimeStatus),
    }))
    commitGraph(nextNodes, nextEdges)
  }, [commitGraph, runtimeStatus])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const editing =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.isContentEditable

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        setSearchQuery('')
        return
      }

      if (editing) return

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        const move = event.shiftKey ? 1 : -1
        const nextIndex = historyIndexRef.current + move
        if (nextIndex < 0 || nextIndex >= historyRef.current.length) return
        applyingHistoryRef.current = true
        const snapshot = historyRef.current[nextIndex]
        const normalizedEdges = normalizeWorkbenchEdges(snapshot.edges)
        const normalizedNodes = snapshot.nodes.map((node) => ({
          ...node,
          data: enrichNodeData(node.data, normalizedEdges, runtimeStatus),
        }))
        setNodes(normalizedNodes)
        setEdges(normalizedEdges)
        historyIndexRef.current = nextIndex
        persistGraph(normalizedNodes, normalizedEdges)
        queueMicrotask(() => {
          applyingHistoryRef.current = false
        })
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [persistGraph, runtimeStatus])

  const contextActions = useMemo(() => {
    if (!contextMenu) return []
    if (contextMenu.kind === 'edge') {
      const edge = edgesRef.current.find((item) => item.id === contextMenu.id)
      return [
        {
          label: '查看上游节点历史',
          onSelect: () => {
            if (edge) window.location.assign(`/history/dag/${selectedDagName}/nodes/${edge.source}`)
          },
        },
        { label: '反转方向', onSelect: () => reverseEdgeById(contextMenu.id) },
        { label: '删除连线', tone: 'danger' as const, onSelect: () => deleteEdgeById(contextMenu.id) },
      ]
    }
    const status = runtimeStatus?.node_statuses?.[contextMenu.id]

    return [
      {
        label: '查看当前运行状态',
        onSelect: () => {
          setSelectedNode(contextMenu.id)
          setInspectorTab('runtime')
        },
      },
      {
        label: '查看历史',
        onSelect: () => window.location.assign(`/history/dag/${selectedDagName}/nodes/${contextMenu.id}`),
      },
      {
        label: '重试节点',
        onSelect: () => {
          if (status?.cycle_id) retryNode.mutate({ dagName: selectedDagName, cycleId: status.cycle_id, nodeId: contextMenu.id, mode: 'single' })
        },
      },
      {
        label: '重试节点及下游',
        onSelect: () => {
          if (status?.cycle_id) retryNode.mutate({ dagName: selectedDagName, cycleId: status.cycle_id, nodeId: contextMenu.id, mode: 'cascade' })
        },
      },
      { label: '删除节点', tone: 'danger' as const, onSelect: () => void deleteNodeById(contextMenu.id) },
      { label: '断开所有连线', onSelect: () => disconnectNodeById(contextMenu.id) },
    ]
  }, [contextMenu, deleteEdgeById, reverseEdgeById, deleteNodeById, disconnectNodeById, retryNode, runtimeStatus, selectedDagName, setInspectorTab, setSelectedNode])

  return (
    <div ref={canvasRef} className="h-full w-full">
      <QuickAddPanel
        open={searchOpen}
        query={searchQuery}
        onQueryChange={setSearchQuery}
        items={searchItems}
        onClose={() => setSearchOpen(false)}
        onSelect={(name) => {
          const rect = canvasRef.current?.getBoundingClientRect()
          if (!rect) return
          const center = screenToFlowPosition({
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          })
          addExistingNode(name, center)
          setSearchOpen(false)
        }}
      />
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onConnectStart={(_, params) => setConnectionSourceId(params.nodeId)}
        onConnectEnd={() => setConnectionSourceId(null)}
        isValidConnection={(connection) => {
          const sourceNode = nodesRef.current.find((node) => node.id === connection.source)
          const targetNode = nodesRef.current.find((node) => node.id === connection.target)
          return isValidConnection(sourceNode?.data, targetNode?.data)
        }}
        onNodeClick={onNodeClick}
        onEdgeClick={(_, edge) => setSelectedEdge(edge.id)}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeContextMenu={(event, node) => {
          event.preventDefault()
          setContextMenu({ kind: 'node', id: node.id, x: event.clientX, y: event.clientY })
        }}
        onEdgeContextMenu={(event, edge) => {
          event.preventDefault()
          setContextMenu({ kind: 'edge', id: edge.id, x: event.clientX, y: event.clientY })
        }}
        onNodesDelete={(deletedNodes) => {
          const deletedIds = new Set(deletedNodes.map((node) => node.id))
          const nextNodes = nodesRef.current.filter((node) => !deletedIds.has(node.id))
          const nextEdges = normalizeWorkbenchEdges(edgesRef.current.filter((edge) => !deletedIds.has(edge.source) && !deletedIds.has(edge.target)))
          const hydratedNodes = nextNodes.map((node) => ({
            ...node,
            data: enrichNodeData(node.data, nextEdges, runtimeStatus),
          }))
          commitGraph(hydratedNodes, nextEdges)
        }}
        onEdgesDelete={(deletedEdges) => {
          const deletedIds = new Set(deletedEdges.map((edge) => edge.id))
          const nextEdges = normalizeWorkbenchEdges(edgesRef.current.filter((edge) => !deletedIds.has(edge.id)))
          const nextNodes = nodesRef.current.map((node) => ({
            ...node,
            data: enrichNodeData(node.data, nextEdges, runtimeStatus),
          }))
          commitGraph(nextNodes, nextEdges)
        }}
        onPaneClick={onPaneClick}
        onPaneContextMenu={(event) => {
          event.preventDefault()
          closeContextMenu()
        }}
        onDragOver={onDragOver}
        onDrop={onDrop}
        deleteKeyCode="Delete"
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{
          padding: FIT_VIEW_PADDING,
          minZoom: MIN_ZOOM,
          includeHiddenNodes: true,
        }}
        minZoom={MIN_ZOOM}
        nodesConnectable
        connectionRadius={28}
        snapToGrid
        snapGrid={SNAP_GRID}
        defaultEdgeOptions={{
          type: 'default',
          markerEnd: { type: MarkerType.ArrowClosed },
        }}
        className="bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.55),_transparent_55%),linear-gradient(180deg,_rgba(248,250,252,0.9),_rgba(241,245,249,0.94))]"
      >
        <Background gap={GRID_SIZE} color="rgba(100,116,139,0.18)" />
        <Controls />
        <MiniMap
          pannable
          zoomable
          nodeStrokeWidth={3}
          nodeColor={(node) => getNodeEdgeColor((node.data as WorkbenchNode['data']).visualKind)}
        />
        <ViewportPortal>
          {groupedEntities.map((group) => (
            <div
              key={group.entity}
              className="pointer-events-none absolute rounded-[28px] border border-dashed"
              style={{
                transform: `translate(${group.x}px, ${group.y}px)`,
                width: group.width,
                height: group.height,
                backgroundColor: group.color.replace('rgb', 'rgba').replace(')', ', 0.08)'),
                borderColor: group.color.replace('rgb', 'rgba').replace(')', ', 0.32)'),
              }}
            >
              <span
                className="absolute left-4 top-3 rounded-full px-2 py-0.5 text-[10px] font-medium"
                style={{
                  backgroundColor: group.color.replace('rgb', 'rgba').replace(')', ', 0.14)'),
                  color: group.color,
                }}
              >
                {group.entity}
              </span>
            </div>
          ))}
          {guideLines.map((guide, index) => (
            <div
              key={`${guide.axis}-${index}-${guide.value}`}
              className="pointer-events-none absolute bg-red-500/80"
              style={
                guide.axis === 'x'
                  ? {
                      transform: `translate(${guide.value}px, ${guide.start}px)`,
                      width: 1,
                      height: guide.end - guide.start,
                    }
                  : {
                      transform: `translate(${guide.start}px, ${guide.value}px)`,
                      width: guide.end - guide.start,
                      height: 1,
                    }
              }
            />
          ))}
        </ViewportPortal>
        <Panel position="top-right">
          <div className="flex gap-2">
            <button
              onClick={() => setSearchOpen(true)}
              className="rounded-md border bg-card px-3 py-1.5 text-xs shadow-sm hover:bg-accent/50"
            >
              Cmd/Ctrl+K
            </button>
            <button
              onClick={() => void onAutoLayout()}
              className="rounded-md border bg-card px-3 py-1.5 text-xs shadow-sm hover:bg-accent/50"
            >
              自动布局
            </button>
          </div>
        </Panel>
      </ReactFlow>
      <CanvasContextMenu menu={contextMenu} actions={contextActions} onClose={closeContextMenu} />
      {toastMessage && (
        <div className="pointer-events-none absolute left-1/2 top-4 z-50 -translate-x-1/2 rounded-md border bg-card px-3 py-2 text-xs shadow-lg">
          {toastMessage}
        </div>
      )}
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-full border bg-card/85 px-3 py-1 text-[11px] text-muted-foreground shadow-sm">
        grid {GRID_SIZE}px · x {viewport.x.toFixed(0)} · y {viewport.y.toFixed(0)} · z {viewport.zoom.toFixed(2)}
      </div>
    </div>
  )
}

function createsCycle(source: string, target: string, edges: WorkbenchEdge[]): boolean {
  const adjacency = new Map<string, string[]>()
  for (const edge of edges) {
    const list = adjacency.get(edge.source) ?? []
    list.push(edge.target)
    adjacency.set(edge.source, list)
  }
  const stack = [target]
  const visited = new Set<string>()
  while (stack.length > 0) {
    const node = stack.pop()
    if (!node || visited.has(node)) continue
    if (node === source) return true
    visited.add(node)
    stack.push(...(adjacency.get(node) ?? []))
  }
  return false
}
