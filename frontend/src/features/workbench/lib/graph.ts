import type { Edge, Node, XYPosition } from '@xyflow/react'
import type { DagEdge, DagState, NodePrototype, RuntimeStatus } from '@/api/types'

export type NodeKind = 'fetcher' | 'llm' | 'aggregator' | 'unknown'
export type RuntimeNodeState = 'pending' | 'running' | 'succeeded' | 'failed'

export interface HandleSpec {
  id: string
  label: string
  connected: boolean
}

export interface WorkbenchNodeData extends NodePrototype {
  status?: string
  error?: string | null
  visualKind: NodeKind
  inputHandles: HandleSpec[]
  outputHandles: HandleSpec[]
}

export type WorkbenchNode = Node<WorkbenchNodeData>
export type WorkbenchEdgeData = {
  visualState?: RuntimeNodeState
}
export type WorkbenchEdge = Edge<WorkbenchEdgeData>

export interface GuideLine {
  axis: 'x' | 'y'
  start: number
  end: number
  value: number
}

export interface ContextMenuState {
  kind: 'node' | 'edge'
  id: string
  x: number
  y: number
}

export interface SearchItem {
  name: string
  type: string
  kind: NodeKind
}

export interface GraphSnapshot {
  nodes: WorkbenchNode[]
  edges: WorkbenchEdge[]
}

export interface DagDraft {
  nodes: DagState['nodes']
  edges: DagState['edges']
  ui: DagState['ui']
}

type EdgeLike =
  | Pick<DagEdge, 'from' | 'to'>
  | Pick<WorkbenchEdge, 'source' | 'target'>

const NODE_SIZE: Record<NodeKind, { width: number; height: number }> = {
  fetcher: { width: 220, height: 104 },
  llm: { width: 240, height: 112 },
  aggregator: { width: 230, height: 108 },
  unknown: { width: 220, height: 104 },
}

const NODE_COLORS: Record<NodeKind, { edge: string }> = {
  fetcher: { edge: '#2563eb' },
  llm: { edge: '#7c3aed' },
  aggregator: { edge: '#16a34a' },
  unknown: { edge: '#64748b' },
}

export function getDraftStorageKey(dagName: string): string {
  return `workbench:draft:${dagName}`
}

export function getNodeKind(node: Pick<NodePrototype, 'type' | 'source_names'>): NodeKind {
  if (node.type === 'llm') return 'llm'
  if (node.type === 'function' && (node.source_names?.length ?? 0) > 0) return 'fetcher'
  if (node.type === 'function') return 'aggregator'
  return 'unknown'
}

export function getNodeSize(kind: NodeKind): { width: number; height: number } {
  return NODE_SIZE[kind]
}

export function getNodeEdgeColor(kind: NodeKind): string {
  return NODE_COLORS[kind].edge
}

export function getRuntimeState(status?: string | null): RuntimeNodeState | undefined {
  if (status === 'running' || status === 'succeeded' || status === 'failed') return status
  if (status === 'pending' || status === 'queued' || status === 'idle' || status === 'waiting') return 'pending'
  return undefined
}

function getEdgeEndpoints(edge: EdgeLike): { source: string; target: string } {
  if ('from' in edge) return { source: edge.from, target: edge.to }
  return { source: edge.source, target: edge.target }
}

export function getHandleSpecs(
  nodeId: string,
  node: Pick<NodePrototype, 'type' | 'input_type' | 'output_type' | 'source_names'>,
  edges: EdgeLike[],
): {
  inputHandles: HandleSpec[]
  outputHandles: HandleSpec[]
} {
  let inputCount = 0
  let outputCount = 0

  for (const edge of edges) {
    const endpoints = getEdgeEndpoints(edge)
    if (endpoints.target === nodeId) inputCount += 1
    if (endpoints.source === nodeId) outputCount += 1
  }

  const resolvedInputCount = Math.max(1, inputCount)
  const resolvedOutputCount = Math.max(1, outputCount)
  const inputLabel = node.input_type || 'input'
  const outputLabel = node.output_type || 'output'
  const inputHandles = Array.from({ length: resolvedInputCount }, (_, index) => ({
    id: `input-${index}`,
    label: inputLabel,
    connected: index < inputCount,
  }))
  const outputHandles = Array.from({ length: resolvedOutputCount }, (_, index) => ({
    id: `output-${index}`,
    label: outputLabel,
    connected: index < outputCount,
  }))

  return { inputHandles, outputHandles }
}

export function enrichNodeData(node: NodePrototype, edges: EdgeLike[], runtimeStatus?: RuntimeStatus | null): WorkbenchNodeData {
  const visualKind = getNodeKind(node)
  const runtime = runtimeStatus?.node_statuses?.[node.name]
  const handles = getHandleSpecs(node.name, node, edges)

  return {
    ...node,
    visualKind,
    status: runtime?.status,
    error: runtime?.error,
    inputHandles: handles.inputHandles,
    outputHandles: handles.outputHandles,
  }
}

export function createWorkbenchNode(
  node: NodePrototype,
  position: XYPosition,
  edges: EdgeLike[],
  runtimeStatus?: RuntimeStatus | null,
): WorkbenchNode {
  const data = enrichNodeData(node, edges, runtimeStatus)
  const size = getNodeSize(data.visualKind)

  return {
    id: node.name,
    type: 'custom',
    position,
    data,
    style: size,
  }
}

function resolveNormalizedHandles<T>(
  edges: T[],
  getEndpoints: (edge: T) => { source: string; target: string },
): Array<{ sourceHandle: string; targetHandle: string }> {
  const sourceCounts = new Map<string, number>()
  const targetCounts = new Map<string, number>()

  return edges.map((edge) => {
    const { source, target } = getEndpoints(edge)
    const sourceIndex = sourceCounts.get(source) ?? 0
    const targetIndex = targetCounts.get(target) ?? 0
    sourceCounts.set(source, sourceIndex + 1)
    targetCounts.set(target, targetIndex + 1)

    return {
      sourceHandle: `output-${sourceIndex}`,
      targetHandle: `input-${targetIndex}`,
    }
  })
}

export function normalizeDagEdges(edges: DagEdge[]): DagEdge[] {
  const handles = resolveNormalizedHandles(edges, (edge) => ({ source: edge.from, target: edge.to }))
  return edges.map((edge, index) => ({ ...edge, ...handles[index] }))
}

export function normalizeWorkbenchEdges(edges: WorkbenchEdge[]): WorkbenchEdge[] {
  const handles = resolveNormalizedHandles(edges, (edge) => ({ source: edge.source, target: edge.target }))
  return edges.map((edge, index) => ({ ...edge, ...handles[index] }))
}

export function createWorkbenchEdge(
  edge: DagEdge,
  index: number,
  nodesById: Map<string, WorkbenchNodeData>,
  runtimeStatus?: RuntimeStatus | null,
): WorkbenchEdge {
  const id = getEdgeId(edge, index)
  const sourceKind = nodesById.get(edge.from)?.visualKind ?? 'unknown'
  const targetState = getRuntimeState(runtimeStatus?.node_statuses?.[edge.to]?.status)
  const color = getEdgeColor(sourceKind, targetState)

  return {
    id,
    source: edge.from,
    target: edge.to,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: 'default',
    markerEnd: { type: 'arrowclosed', color },
    style: {
      stroke: color,
      strokeWidth: targetState ? 3 : 2,
    },
    data: {
      visualState: targetState,
    },
  }
}

export function getEdgeId(edge: DagEdge, index: number): string {
  return `e-${edge.from}-${edge.to}-${index}`
}

export function getEdgeColor(kind: NodeKind, state?: RuntimeNodeState): string {
  if (state === 'running') return '#2563eb'
  if (state === 'succeeded') return '#16a34a'
  if (state === 'failed') return '#dc2626'
  return getNodeEdgeColor(kind)
}

export function toDagDraft(nodes: WorkbenchNode[], edges: WorkbenchEdge[]): DagDraft {
  const uiNodes: NonNullable<DagState['ui']['nodes']> = {}
  const uiEdges: NonNullable<DagState['ui']['edges']> = {}

  for (const node of nodes) {
    uiNodes[node.id] = { x: node.position.x, y: node.position.y }
  }

  const dagNodes = nodes.map((node) => {
    const { visualKind, inputHandles, outputHandles, status, error, ...rest } = node.data
    void visualKind
    void inputHandles
    void outputHandles
    void status
    void error
    return rest
  })

  const dagEdges = edges.map((edge) => {
    uiEdges[edge.id] = {
      sourceHandle: edge.sourceHandle ?? undefined,
      targetHandle: edge.targetHandle ?? undefined,
    }

    return {
      from: edge.source,
      to: edge.target,
      sourceHandle: edge.sourceHandle ?? undefined,
      targetHandle: edge.targetHandle ?? undefined,
    }
  })

  return {
    nodes: dagNodes,
    edges: dagEdges,
    ui: {
      nodes: uiNodes,
      edges: uiEdges,
    },
  }
}

export function readDraft(dagName: string): DagDraft | null {
  try {
    const raw = localStorage.getItem(getDraftStorageKey(dagName))
    if (!raw) return null
    return JSON.parse(raw) as DagDraft
  } catch {
    return null
  }
}

export function writeDraft(dagName: string, draft: DagDraft): void {
  localStorage.setItem(getDraftStorageKey(dagName), JSON.stringify(draft))
}

export function clearDraftIfMatch(dagName: string, serializedDraft: string): void {
  if (localStorage.getItem(getDraftStorageKey(dagName)) === serializedDraft) {
    localStorage.removeItem(getDraftStorageKey(dagName))
  }
}

export function buildSearchItems(nodes: NodePrototype[]): SearchItem[] {
  return nodes.map((node) => ({
    name: node.name,
    type: node.type,
    kind: getNodeKind(node),
  }))
}

export function filterSearchItems(items: SearchItem[], query: string): SearchItem[] {
  const keyword = query.trim().toLowerCase()
  if (!keyword) return items.slice(0, 12)

  const score = (value: string): number => {
    const haystack = value.toLowerCase()
    let cursor = 0
    let streak = 0
    let total = 0

    for (const char of keyword) {
      const found = haystack.indexOf(char, cursor)
      if (found === -1) return -1
      const contiguous = found === cursor
      streak = contiguous ? streak + 1 : 1
      total += contiguous ? 8 + streak * 2 : 3
      if (found === 0) total += 12
      if (found > 0 && /[\s_-]/.test(haystack[found - 1] ?? '')) total += 6
      cursor = found + 1
    }

    total -= haystack.length - keyword.length
    return total
  }

  return items
    .map((item) => ({
      item,
      score: score(`${item.name} ${item.type} ${item.kind}`),
    }))
    .filter((entry) => entry.score >= 0)
    .sort((a, b) => {
      if (a.score !== b.score) return b.score - a.score
      return a.name.localeCompare(b.name)
    })
    .map((entry) => entry.item)
    .slice(0, 12)
}

export function calculateGuideLines(nodes: WorkbenchNode[], activeNode: WorkbenchNode): GuideLine[] {
  const threshold = 5
  const guides: GuideLine[] = []
  const activeSize = getNodeSize(activeNode.data.visualKind)
  const activeCenterX = activeNode.position.x + activeSize.width / 2
  const activeCenterY = activeNode.position.y + activeSize.height / 2

  for (const node of nodes) {
    if (node.id === activeNode.id) continue
    const size = getNodeSize(node.data.visualKind)
    const centerX = node.position.x + size.width / 2
    const centerY = node.position.y + size.height / 2

    if (Math.abs(centerX - activeCenterX) < threshold) {
      guides.push({
        axis: 'x',
        value: centerX,
        start: Math.min(node.position.y, activeNode.position.y) - 24,
        end: Math.max(node.position.y + size.height, activeNode.position.y + activeSize.height) + 24,
      })
    }

    if (Math.abs(centerY - activeCenterY) < threshold) {
      guides.push({
        axis: 'y',
        value: centerY,
        start: Math.min(node.position.x, activeNode.position.x) - 24,
        end: Math.max(node.position.x + size.width, activeNode.position.x + activeSize.width) + 24,
      })
    }
  }

  return guides.slice(0, 2)
}

export function getRuntimeEdgeStates(edges: WorkbenchEdge[], runtimeStatus?: RuntimeStatus | null): Map<string, RuntimeNodeState> {
  const states = new Map<string, RuntimeNodeState>()
  if (!runtimeStatus) return states

  const incoming = new Map<string, WorkbenchEdge[]>()
  for (const edge of edges) {
    const group = incoming.get(edge.target) ?? []
    group.push(edge)
    incoming.set(edge.target, group)
  }

  const collectAncestry = (nodeId: string, visited = new Set<string>()): string[] => {
    const directEdges = incoming.get(nodeId) ?? []
    const result: string[] = []

    for (const edge of directEdges) {
      if (visited.has(edge.id)) continue
      visited.add(edge.id)
      result.push(edge.id)
      result.push(...collectAncestry(edge.source, visited))
    }

    return result
  }

  for (const [nodeId, status] of Object.entries(runtimeStatus.node_statuses ?? {})) {
    if (status.status === 'succeeded') {
      for (const edgeId of collectAncestry(nodeId)) {
        if (!states.has(edgeId)) states.set(edgeId, 'succeeded')
      }
    }
  }

  for (const [nodeId, status] of Object.entries(runtimeStatus.node_statuses ?? {})) {
    if (status.status === 'running') {
      for (const edgeId of collectAncestry(nodeId)) {
        states.set(edgeId, 'running')
      }
    }
  }

  for (const [nodeId, status] of Object.entries(runtimeStatus.node_statuses ?? {})) {
    if (status.status !== 'failed') continue
    for (const edge of incoming.get(nodeId) ?? []) {
      states.set(edge.id, 'failed')
    }
  }

  return states
}
