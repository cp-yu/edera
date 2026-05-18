import { useEffect, useMemo, useState } from 'react'
import { useDag } from '@/api/queries'
import { useSaveDag } from '@/api/mutations'
import type { InspectorSchema, NodeInstance } from '@/api/types'
import { useAppStore } from '@/store/useAppStore'
import { SchemaForm } from './SchemaForm'

const TOP_LEVEL_FIELDS = new Set(['model', 'skills', 'source_names', 'timeout_seconds'])

export function Inspector() {
  const { selectedDagName, selectedEdgeId, selectedNodeId } = useAppStore()
  const { data: dag } = useDag(selectedDagName)
  const saveDag = useSaveDag(selectedDagName)
  const node = dag?.nodes.find((item) => item.id === selectedNodeId)
  const edge = dag?.edges.find((item, index) => `e-${item.from}-${item.to}-${index}` === selectedEdgeId)
  const [alias, setAlias] = useState('')
  const [formValues, setFormValues] = useState<Record<string, unknown>>({})

  useEffect(() => {
    if (!node) return
    setAlias(node.alias ?? '')
    setFormValues(flattenConfig(node.config))
  }, [node])

  const typeDefaults = useMemo(() => (node ? defaultValues(node) : {}), [node])
  const displayDefaults = useMemo(() => {
    if (!node) return {}
    return mergeSchemaDefaults(typeDefaults, node.inspector_schema)
  }, [node, typeDefaults])

  if (edge && dag) {
    const saveEdge = (patch: { fan_in?: boolean; fan_out?: boolean }) => {
      const edges = dag.edges.map((item, index) =>
        `e-${item.from}-${item.to}-${index}` === selectedEdgeId ? { ...item, ...patch } : item,
      )
      const nodes = dag.nodes.map((item) => ({
        id: item.id,
        type: item.type_name,
        alias: item.alias,
        config: item.config ?? {},
      }))
      saveDag.mutate({ nodes, edges, ui: dag.ui })
    }
    return (
      <aside className="w-[300px] space-y-4 overflow-y-auto border-l bg-card p-4">
        <div>
          <h2 className="text-sm font-medium">连线配置</h2>
          <p className="text-xs text-muted-foreground">{edge.from} → {edge.to}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(edge.fan_in)}
            onChange={(event) => saveEdge({ fan_in: event.target.checked })}
          />
          fan_in
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(edge.fan_out)}
            onChange={(event) => saveEdge({ fan_out: event.target.checked })}
          />
          fan_out
        </label>
      </aside>
    )
  }

  if (!node || !dag) {
    return (
      <aside className="w-[300px] border-l bg-card p-4">
        <p className="text-sm text-muted-foreground">选择节点查看配置</p>
      </aside>
    )
  }

  const save = () => {
    const nodes = dag.nodes.map((item) => {
      if (item.id !== node.id) {
        return { id: item.id, type: item.type_name, alias: item.alias, config: item.config ?? {} }
      }
      const config = buildConfig(item, formValues, typeDefaults)
      return { id: item.id, type: item.type_name, alias: alias || item.type_name, config }
    })
    saveDag.mutate({ nodes, edges: dag.edges, ui: dag.ui })
  }

  return (
    <aside className="w-[300px] space-y-4 overflow-y-auto border-l bg-card p-4">
      <div>
        <h2 className="text-sm font-medium">{node.alias || node.name}</h2>
        <p className="text-xs text-muted-foreground">{node.type_name} · {node.role}</p>
      </div>
      <Field label="Alias" value={alias} onChange={setAlias} />
      <Readonly label="类型" value={node.type_name} />
      <Readonly label="角色" value={node.role} />
      <Readonly label="输入" value={node.input_type} />
      <Readonly label="输出" value={node.output_type} />
      <SchemaForm
        key={node.id}
        schema={node.inspector_schema}
        values={formValues}
        defaults={displayDefaults}
        onChange={(name, value) => {
          setFormValues((current) => {
            const next = { ...current }
            if (value === undefined) delete next[name]
            else next[name] = value
            return next
          })
        }}
      />
      <button
        onClick={save}
        disabled={saveDag.isPending}
        className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {saveDag.isPending ? '保存中...' : '保存实例'}
      </button>
    </aside>
  )
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-muted-foreground">{label}</label>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
      />
    </div>
  )
}

function Readonly({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="text-xs text-muted-foreground">{label}</label>
      <p className="text-sm">{value}</p>
    </div>
  )
}

function flattenConfig(config: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!config) return {}
  const values: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(config)) {
    if (key === 'parameters' && isRecord(value)) {
      for (const [paramKey, paramValue] of Object.entries(value)) {
        values[`param.${paramKey}`] = paramValue
      }
      continue
    }
    if (TOP_LEVEL_FIELDS.has(key)) values[key] = value
  }
  return values
}

function defaultValues(node: NodeInstance): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  if (node.model !== undefined) values.model = node.model
  if (node.skills) values.skills = node.skills
  if (node.source_names) values.source_names = node.source_names
  if (node.timeout_seconds !== undefined) values.timeout_seconds = node.timeout_seconds
  if (node.parameters) {
    for (const [key, value] of Object.entries(node.parameters)) {
      values[`param.${key}`] = value
    }
  }
  return values
}

function mergeSchemaDefaults(
  current: Record<string, unknown>,
  schema: InspectorSchema,
): Record<string, unknown> {
  const values = { ...current }
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    if (values[key] === undefined && property.default !== undefined) values[key] = property.default
  }
  return values
}

function buildConfig(
  node: NodeInstance,
  formValues: Record<string, unknown>,
  typeDefaults: Record<string, unknown>,
): Record<string, unknown> {
  const config = { ...(node.config ?? {}) }
  for (const key of TOP_LEVEL_FIELDS) delete config[key]
  const parameters = isRecord(config.parameters) ? { ...config.parameters } : {}
  for (const key of Object.keys(node.inspector_schema.properties ?? {})) {
    if (key.startsWith('param.')) delete parameters[key.slice(6)]
  }
  for (const [key, value] of Object.entries(formValues)) {
    if (isEqual(value, typeDefaults[key])) continue
    if (key.startsWith('param.')) {
      parameters[key.slice(6)] = value
      continue
    }
    config[key] = value
  }
  if (Object.keys(parameters).length > 0) config.parameters = parameters
  else delete config.parameters
  return config
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isEqual(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}
