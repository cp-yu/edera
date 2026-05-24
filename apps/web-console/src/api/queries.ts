import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { Advice, Briefing, DagState, DagStatus, NodeHistoryItem, NodeOutputEntity, NodeType, ResultsSummary, RuntimeStatus, SkillDefinition, SourceHealth, SourceLog } from './types'

export function useDag(name: string) {
  return useQuery({
    queryKey: ['dag', name],
    queryFn: () => apiFetch<DagState>(`/api/graph/dag/${name}`),
    enabled: !!name,
  })
}

export function useNodePrototypes() {
  return useQuery({
    queryKey: ['nodePrototypes'],
    queryFn: () => apiFetch<{ prototypes: NodeType[] }>('/api/graph/nodes'),
  })
}

export function useNodeTypes() {
  return useQuery({
    queryKey: ['nodeTypes'],
    queryFn: () => apiFetch<{ types: NodeType[] }>('/api/graph/node-types'),
  })
}

export function useHandler(name: string | null) {
  return useQuery({
    queryKey: ['handler', name],
    queryFn: () => apiFetch<{ name: string; code: string }>(`/api/graph/handlers/${name}`),
    enabled: !!name,
  })
}

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: () => apiFetch<{ skills: SkillDefinition[] }>('/api/graph/skills'),
  })
}

export function useRuntimeStatus(polling = false) {
  return useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiFetch<RuntimeStatus>('/api/graph/runtime-status'),
    refetchInterval: polling ? 2000 : false,
  })
}

export function useDagStatus(dagName: string, polling = false) {
  return useQuery({
    queryKey: ['dagStatus', dagName],
    queryFn: () => apiFetch<DagStatus>(`/api/pipeline/dag/${dagName}/status`),
    enabled: !!dagName,
    refetchInterval: polling ? 2000 : false,
  })
}

export function useResults(params?: { stock_code?: string; direction?: string }) {
  const search = new URLSearchParams()
  if (params?.stock_code) search.set('stock_code', params.stock_code)
  if (params?.direction) search.set('direction', params.direction)
  const qs = search.toString()
  return useQuery({
    queryKey: ['results', params],
    queryFn: () => apiFetch<ResultsSummary>(`/api/results${qs ? `?${qs}` : ''}`),
  })
}

export function useAdviceDetail(id?: string) {
  return useQuery({
    queryKey: ['advice', id],
    queryFn: () => apiFetch<{ advice: Advice; analyses: unknown[]; raw_items: unknown[] }>(`/api/advices/${id}`),
    enabled: !!id,
  })
}

export function useBriefings() {
  return useQuery({
    queryKey: ['briefings'],
    queryFn: () => apiFetch<{ briefings: Briefing[] }>('/api/briefings'),
  })
}

export function useBriefingDetail(id?: string) {
  return useQuery({
    queryKey: ['briefing', id],
    queryFn: () => apiFetch<{ briefing: Briefing }>(`/api/briefings/${id}`),
    enabled: !!id,
  })
}

export function useSourcesHealth() {
  return useQuery({
    queryKey: ['sourcesHealth'],
    queryFn: () => apiFetch<{ sources: SourceHealth[] }>('/api/sources/health'),
  })
}

export function useSourceLogs(sourceName?: string) {
  const qs = sourceName ? `?source_name=${sourceName}` : ''
  return useQuery({
    queryKey: ['sourceLogs', sourceName],
    queryFn: () => apiFetch<{ logs: SourceLog[] }>(`/api/sources/logs${qs}`),
  })
}

export function useNodeOutputs(nodeId: string | null, cycleId?: string | null) {
  const search = new URLSearchParams()
  if (nodeId) search.set('node_id', nodeId)
  if (cycleId) search.set('cycle_id', cycleId)
  const qs = search.toString()
  return useQuery({
    queryKey: ['nodeOutputs', nodeId, cycleId],
    queryFn: () => apiFetch<{ outputs: NodeOutputEntity[] }>(`/api/node-outputs${qs ? `?${qs}` : ''}`),
    enabled: !!nodeId,
  })
}

export function useNodeHistory(dagName: string, nodeId: string) {
  return useQuery({
    queryKey: ['nodeHistory', dagName, nodeId],
    queryFn: () => apiFetch<{ history: NodeHistoryItem[] }>(`/api/history/dag/${dagName}/nodes/${nodeId}`),
    enabled: !!dagName && !!nodeId,
  })
}
