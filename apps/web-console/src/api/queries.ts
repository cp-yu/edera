import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { Advice, Briefing, DagState, DagStatus, EntityItem, NodeControlStatus, NodeExecutionLog, NodeHistoryItem, NodeOutputEntity, NodeResumeResponse, NodeType, ResultsSummary, RuntimeStatus, SkillDefinition, SourceHealth, SourceLog } from './types'

export function useDag(name: string) {
  return useQuery({
    queryKey: ['dag', name],
    queryFn: () => apiFetch<DagState>(`/api/graph/dag/${name}`),
    enabled: !!name,
  })
}

export function useDagList() {
  return useQuery({
    queryKey: ['dags'],
    queryFn: () => apiFetch<{ dags: string[] }>('/api/graph/dags'),
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

export function useHandlers() {
  return useQuery({
    queryKey: ['handlers'],
    queryFn: () => apiFetch<{ handlers: { name: string }[] }>('/api/graph/handlers'),
  })
}

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: () => apiFetch<{ skills: SkillDefinition[] }>('/api/graph/skills'),
  })
}

export function useEntities(type?: string) {
  const qs = type ? `?${new URLSearchParams({ type }).toString()}` : ''
  return useQuery({
    queryKey: ['entities', type ?? 'all'],
    queryFn: () => apiFetch<{ entities: EntityItem[] }>(`/api/entities${qs}`),
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
    queryFn: () => apiFetch<DagStatus>(`/api/dags/${dagName}/status`),
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
    refetchInterval: 10000,
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
    refetchInterval: 10000,
  })
}

export function useSourceLogs(sourceName?: string) {
  const qs = sourceName ? `?${new URLSearchParams({ source_name: sourceName }).toString()}` : ''
  return useQuery({
    queryKey: ['sourceLogs', sourceName],
    queryFn: () => apiFetch<{ logs: SourceLog[] }>(`/api/sources/logs${qs}`),
    refetchInterval: 10000,
  })
}

export function useNodeOutputs(nodeId: string | null, runId?: string | null) {
  const search = new URLSearchParams()
  if (nodeId) search.set('node_id', nodeId)
  if (runId) search.set('run_id', runId)
  const qs = search.toString()
  return useQuery({
    queryKey: ['nodeOutputs', nodeId, runId],
    queryFn: () => apiFetch<{ outputs: NodeOutputEntity[] }>(`/api/node-outputs${qs ? `?${qs}` : ''}`),
    enabled: !!nodeId,
  })
}

export function useNodeLogs(nodeId: string | null, runId?: string | null) {
  const search = new URLSearchParams()
  if (nodeId) search.set('node_id', nodeId)
  if (runId) search.set('run_id', runId)
  const qs = search.toString()
  return useQuery({
    queryKey: ['nodeLogs', nodeId, runId],
    queryFn: () => apiFetch<{ logs: NodeExecutionLog[] }>(`/api/node-logs${qs ? `?${qs}` : ''}`),
    enabled: !!nodeId && !!runId,
  })
}

export function useNodeStatus(nodeId: string | null, polling = false) {
  return useQuery({
    queryKey: ['nodeStatus', nodeId],
    queryFn: () => apiFetch<NodeControlStatus>(`/api/node/${nodeId}/status`),
    enabled: !!nodeId,
    refetchInterval: polling ? 2000 : false,
  })
}

export function useNodeStop(nodeId: string) {
  return useMutation({
    mutationFn: () => apiFetch<NodeControlStatus>(`/api/node/${nodeId}/stop`, { method: 'POST' }),
  })
}

export function useNodeResume(nodeId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ runId, prompt }: { runId: string; prompt: string }) =>
      apiFetch<NodeResumeResponse>(`/api/node/${nodeId}/resume`, {
        method: 'POST',
        body: JSON.stringify({ run_id: runId, prompt }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodeOutputs', nodeId] })
      qc.invalidateQueries({ queryKey: ['nodeLogs', nodeId] })
      qc.invalidateQueries({ queryKey: ['nodeStatus', nodeId] })
      qc.invalidateQueries({ queryKey: ['runtimeStatus'] })
    },
  })
}

export function useNodeHistory(dagName: string, nodeId: string) {
  return useQuery({
    queryKey: ['nodeHistory', dagName, nodeId],
    queryFn: () => apiFetch<{ history: NodeHistoryItem[] }>(`/api/history/dag/${dagName}/nodes/${nodeId}`),
    enabled: !!dagName && !!nodeId,
  })
}
