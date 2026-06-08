import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { DagEdge, DagNodeRecord, NodeInstance, NodeType, RetryDagResponse, SkillDefinition } from './types'

export interface TemporaryInputs {
  sourceSharedInputs?: Record<string, unknown>
  nodeInputs?: Record<string, unknown>
  appendNodes?: string[]
}

function alertMutationError(error: Error) {
  window.alert(error.message)
}

export function useSaveDag(dagName: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { nodes: DagNodeRecord[]; edges: DagEdge[]; ui?: { nodes?: Record<string, { x: number; y: number }>; edges?: Record<string, { sourceHandle?: string; targetHandle?: string }> } }) =>
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
    mutationFn: ({ dagName, temporaryInputs }: { dagName: string; temporaryInputs?: TemporaryInputs }) =>
      apiFetch<{ run_id: string }>(`/api/dags/${dagName}/run`, {
        method: 'POST',
        body: JSON.stringify(temporaryInputs ?? {}),
      }),
    onSuccess: (_data, { dagName }) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
    onError: alertMutationError,
  })
}

export function useStopDag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dagName, force = false }: { dagName: string; force?: boolean }) =>
      apiFetch(`/api/dags/${dagName}/stop`, { method: 'POST', body: JSON.stringify({ force }) }),
    onSuccess: (_data, { dagName }) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
    onError: alertMutationError,
  })
}

export function useRetryDagNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dagName, runId, nodeIds, mode, temporaryInputs }: { dagName: string; runId?: string; nodeIds: string[]; mode: 'single' | 'cascade'; temporaryInputs?: TemporaryInputs }) =>
      apiFetch<RetryDagResponse>(`/api/dags/${dagName}/retry`, {
        method: 'POST',
        body: JSON.stringify({ run_id: runId, node_ids: nodeIds, mode, ...(temporaryInputs ?? {}) }),
      }),
    onSuccess: (_data, { dagName }) => { qc.invalidateQueries({ queryKey: ['dagStatus', dagName] }) },
    onError: alertMutationError,
  })
}

export function useCreateDag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<{ dag: { name: string } }>('/api/graph/dag', { method: 'POST', body: JSON.stringify({ name }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dagList'] }) },
    onError: alertMutationError,
  })
}

export function useCreateEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ type, attributes }: { type: string; attributes: Record<string, unknown> }) =>
      apiFetch('/api/entities', { method: 'POST', body: JSON.stringify({ type, attributes }) }),
    onSuccess: (_data, { type }) => {
      qc.invalidateQueries({ queryKey: ['entities', type] })
      qc.invalidateQueries({ queryKey: ['entities', 'all'] })
    },
    onError: alertMutationError,
  })
}

export function useUpdateEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, attributes }: { id: string; type: string; attributes: Record<string, unknown> }) =>
      apiFetch(`/api/entities/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify({ attributes }) }),
    onSuccess: (_data, { type }) => {
      qc.invalidateQueries({ queryKey: ['entities', type] })
      qc.invalidateQueries({ queryKey: ['entities', 'all'] })
    },
    onError: alertMutationError,
  })
}

export function useDeleteEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string; type: string }) =>
      apiFetch(`/api/entities/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    onSuccess: (_data, { type }) => {
      qc.invalidateQueries({ queryKey: ['entities', type] })
      qc.invalidateQueries({ queryKey: ['entities', 'all'] })
    },
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

export function useSaveHandler() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, code }: { name: string; code: string }) =>
      apiFetch(`/api/graph/handlers/${name}`, { method: 'PUT', body: JSON.stringify({ code }) }),
    onSuccess: (_data, { name }) => { qc.invalidateQueries({ queryKey: ['handler', name] }) },
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

export function useInstallExtension() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch(`/api/extensions/${encodeURIComponent(name)}/install`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['extensions', 'available'] })
      qc.invalidateQueries({ queryKey: ['extensions', 'installed'] })
    },
    onError: alertMutationError,
  })
}

export function useUninstallExtension() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, strategy }: { name: string; strategy: 'purge' | 'keep-modified' | 'deactivate' }) =>
      apiFetch(`/api/extensions/${encodeURIComponent(name)}/uninstall`, {
        method: 'POST',
        body: JSON.stringify({ strategy }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['extensions', 'available'] })
      qc.invalidateQueries({ queryKey: ['extensions', 'installed'] })
    },
    onError: alertMutationError,
  })
}
