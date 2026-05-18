import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { DagNodeRecord, NodeInstance, NodeType, SkillDefinition } from './types'

function alertMutationError(error: Error) {
  window.alert(error.message)
}

export function useSaveDag(dagName: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { nodes: DagNodeRecord[]; edges: Array<{ from: string; to: string; fan_out?: boolean; fan_in?: boolean }>; ui?: { nodes?: Record<string, { x: number; y: number }>; edges?: Record<string, { sourceHandle?: string; targetHandle?: string }> } }) =>
      apiFetch(`/api/graph/dag/${dagName}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dag', dagName] }) },
    onError: alertMutationError,
  })
}

export function useSaveNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: Partial<NodeType> }) =>
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
    onError: alertMutationError,
  })
}

export function useStopDag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (dagName: string) =>
      apiFetch(`/api/pipeline/dag/${dagName}/stop`, { method: 'POST' }),
    onSuccess: (_data, dagName) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
    onError: alertMutationError,
  })
}

export function useCreateNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dagName, body }: { dagName: string; body: Partial<NodeInstance> }) =>
      apiFetch(`/api/graph/dag/${dagName}/nodes`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (_data, { dagName }) => {
      qc.invalidateQueries({ queryKey: ['dag', dagName] })
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
    },
    onError: alertMutationError,
  })
}

export function useSaveNodeType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: Partial<NodeType> & Record<string, unknown> }) =>
      apiFetch(`/api/graph/node-types/${name}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodeTypes'] })
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
    },
    onError: alertMutationError,
  })
}

export function useCreateNodeType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<NodeType> & Record<string, unknown>) =>
      apiFetch('/api/graph/node-types', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodeTypes'] })
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
    },
    onError: alertMutationError,
  })
}

export function useDeleteNodeType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch(`/api/graph/node-types/${name}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodeTypes'] })
      qc.invalidateQueries({ queryKey: ['nodePrototypes'] })
    },
    onError: alertMutationError,
  })
}

export function useSaveSkill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: Partial<SkillDefinition> & Record<string, unknown> }) =>
      apiFetch(`/api/graph/skills/${name}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['skills'] }) },
    onError: alertMutationError,
  })
}

export function useCreateSkill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<SkillDefinition> & Record<string, unknown>) =>
      apiFetch('/api/graph/skills', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['skills'] }) },
    onError: alertMutationError,
  })
}

export function useDeleteSkill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch(`/api/graph/skills/${name}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['skills'] }) },
    onError: alertMutationError,
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
