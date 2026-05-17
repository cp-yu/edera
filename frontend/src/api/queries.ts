import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { DagState, DagStatus, ResultsSummary, RuntimeStatus, SourceHealth, SourceLog, Advice, Briefing } from './types'

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
    queryFn: () => apiFetch<{ prototypes: DagState['nodes'] }>('/api/graph/nodes'),
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

export function useAdviceDetail(id: number) {
  return useQuery({
    queryKey: ['advice', id],
    queryFn: () => apiFetch<{ advice: Advice; analyses: unknown[]; raw_items: unknown[] }>(`/api/advices/${id}`),
    enabled: id > 0,
  })
}

export function useBriefings() {
  return useQuery({
    queryKey: ['briefings'],
    queryFn: () => apiFetch<{ briefings: Briefing[] }>('/api/briefings'),
  })
}

export function useBriefingDetail(id: number) {
  return useQuery({
    queryKey: ['briefing', id],
    queryFn: () => apiFetch<{ briefing: Briefing }>(`/api/briefings/${id}`),
    enabled: id > 0,
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
