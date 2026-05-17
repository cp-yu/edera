import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { DagState, NodePrototype } from './types'

export function useSaveDag(dagName: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { nodes: DagState['nodes'] | string[]; edges: DagState['edges']; ui?: DagState['ui'] }) =>
      apiFetch(`/api/graph/dag/${dagName}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dag', dagName] }) },
  })
}

export function useSaveNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: Partial<NodePrototype> }) =>
      apiFetch(`/api/graph/node/${name}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['nodePrototypes'] }) },
  })
}

export function useRunDag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (dagName: string) =>
      apiFetch<{ cycle_id: string }>(`/api/pipeline/dag/${dagName}/run`, { method: 'POST' }),
    onSuccess: (_data, dagName) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
  })
}

export function useStopDag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (dagName: string) =>
      apiFetch(`/api/pipeline/dag/${dagName}/stop`, { method: 'POST' }),
    onSuccess: (_data, dagName) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
  })
}

export function useCreateNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dagName, body }: { dagName: string; body: Partial<NodePrototype> }) =>
      apiFetch(`/api/graph/dag/${dagName}/nodes`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (_data, { dagName }) => {
      qc.invalidateQueries({ queryKey: ['dag', dagName] })
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
    },
  })
}

export function useCreateSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, url, fetcherName }: { name: string; url: string; fetcherName: string }) =>
      apiFetch('/api/sources', { method: 'POST', body: JSON.stringify({ name, url, fetcher_name: fetcherName }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
      qc.invalidateQueries({ queryKey: ['sourcesHealth'] })
    },
  })
}
