import { useEffect, useMemo, useState } from 'react'
import { useDag, useNodeOutputs, useRuntimeStatus } from '@/api/queries'
import { useSaveDag } from '@/api/mutations'
import type { EntityItem, EntityRelation, EntityTypeDefinition, InspectorSchema, NodeInstance, NodeOutputEntity, NodeStatus } from '@/api/types'
import { useAppStore } from '@/store/useAppStore'
import { SchemaForm } from './SchemaForm'

const TOP_LEVEL_FIELDS = new Set(['model', 'skills', 'entities', 'entity_permissions', 'timeout_seconds'])
const FIELD_PERMISSIONS = ['none', 'read-only', 'write-only', 'read-write'] as const
type FieldPermission = typeof FIELD_PERMISSIONS[number]
type PendingPermissionOverride = { type: string; field: string; permission: string }

const ALLOWED_PERMISSION_OVERRIDES: Record<FieldPermission, FieldPermission[]> = {
  none: ['none', 'read-only', 'write-only', 'read-write'],
  'read-only': ['read-only', 'read-write'],
  'write-only': ['write-only', 'read-write'],
  'read-write': ['read-write'],
}

export function Inspector() {
  const { inspectorTab, selectedDagName, selectedEdgeId, selectedNodeId, setInspectorTab } = useAppStore()
  const { data: dag } = useDag(selectedDagName)
  const runtime = useRuntimeStatus(true)
  const saveDag = useSaveDag(selectedDagName)
  const node = dag?.nodes.find((item) => item.id === selectedNodeId)
  const edge = dag?.edges.find((item, index) => `e-${item.from}-${item.to}-${index}` === selectedEdgeId)
  const runtimeNodeId = edge?.from ?? node?.id ?? null
  const runtimeStatus = runtimeNodeId ? runtime.data?.node_statuses?.[runtimeNodeId] : undefined
  const outputs = useNodeOutputs(runtimeNodeId, runtimeStatus?.cycle_id)
  const stdout = useNodeStdout(runtimeNodeId)
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
  const formSchema = useMemo(() => omitSchemaFields(node?.inspector_schema, ['entities', 'entity_permissions']), [node])
  const selectedEntityTypes = useMemo(() => selectedTypes(formValues.entities), [formValues.entities])
  const permissionEntityTypes = useMemo(
    () => filterEntityTypes(dag?.entity_types ?? {}, selectedEntityTypes),
    [dag?.entity_types, selectedEntityTypes],
  )

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
          <h2 className="text-sm font-medium">数据流</h2>
          <p className="text-xs text-muted-foreground">{edge.from} → {edge.to}</p>
        </div>
        <RuntimeStatusView status={runtimeStatus} outputs={outputs.data?.outputs ?? []} stdout={stdout} />
        <a
          href={`/history/dag/${selectedDagName}/nodes/${edge.from}`}
          className="block rounded-md border px-3 py-2 text-center text-xs hover:bg-accent"
        >
          查看历史
        </a>
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
        <p className="text-sm text-muted-foreground">选择节点或连线查看详情</p>
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
      <div className="grid grid-cols-2 rounded-md border p-1 text-xs">
        <button
          type="button"
          onClick={() => setInspectorTab('config')}
          className={`rounded px-2 py-1 ${inspectorTab === 'config' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
        >
          Config
        </button>
        <button
          type="button"
          onClick={() => setInspectorTab('runtime')}
          className={`rounded px-2 py-1 ${inspectorTab === 'runtime' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
        >
          Runtime
        </button>
      </div>
      {inspectorTab === 'runtime' ? (
        <RuntimeStatusView status={runtimeStatus} outputs={outputs.data?.outputs ?? []} stdout={stdout} />
      ) : (
        <>
      <Field label="Alias" value={alias} onChange={setAlias} />
      <Readonly label="类型" value={node.type_name} />
      <Readonly label="角色" value={node.role} />
      <Readonly label="输入" value={node.input_type} />
      <Readonly label="输出" value={node.output_type} />
      <SchemaForm
        key={node.id}
        schema={formSchema}
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
      <EntitySelector
        entities={dag.entities ?? []}
        relations={dag.entity_relations ?? []}
        value={formValues.entities}
        node={node}
        onChange={(value) => setFormValues((current) => ({
          ...current,
          entities: value,
          entity_permissions: prunePermissions(current.entity_permissions, selectedTypes(value)),
        }))}
      />
      <PermissionConfigurator
        entityTypes={permissionEntityTypes}
        value={formValues.entity_permissions}
        onChange={(value) => setFormValues((current) => ({ ...current, entity_permissions: value }))}
      />
      <button
        onClick={save}
        disabled={saveDag.isPending}
        className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {saveDag.isPending ? '保存中...' : '保存实例'}
      </button>
        </>
      )}
    </aside>
  )
}

function RuntimeStatusView({ status, outputs, stdout }: { status?: NodeStatus; outputs: NodeOutputEntity[]; stdout: string[] }) {
  return (
    <div className="space-y-3">
      <div className="space-y-2 rounded-md border p-3 text-xs">
        <RuntimeRow label="status" value={status?.status ?? 'unknown'} />
        <RuntimeRow label="cycle" value={status?.cycle_id ?? '-'} />
        <RuntimeRow label="started" value={status?.started_at ?? '-'} />
        <RuntimeRow label="ended" value={status?.ended_at ?? '-'} />
        {status?.error && <RuntimeRow label="error" value={status.error} />}
      </div>
      <div className="space-y-2">
        <div className="text-xs font-medium">Output entities</div>
        {outputs.length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无输出</p>
        ) : (
          <div className="space-y-2">
            {outputs.map((output) => (
              <div key={output.id} className="rounded-md border p-2 text-xs">
                <div className="font-medium">{output.type}</div>
                <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words text-[11px] text-muted-foreground">
                  {JSON.stringify(output.attributes.payload ?? output.attributes, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-2">
        <div className="text-xs font-medium">stdout</div>
        <pre className="max-h-36 overflow-auto rounded-md border bg-muted/30 p-2 text-[11px] whitespace-pre-wrap">
          {stdout.length > 0 ? stdout.join('\n') : '暂无输出'}
        </pre>
      </div>
    </div>
  )
}

function useNodeStdout(nodeId: string | null) {
  const [lines, setLines] = useState<string[]>([])

  useEffect(() => {
    setLines([])
    if (!nodeId) return
    const source = new EventSource(`/api/events/node/${nodeId}`)
    source.addEventListener('node.stdout', (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { line?: unknown }
      if (typeof data.line !== 'string') return
      setLines((current) => [...current.slice(-199), data.line])
    })
    return () => source.close()
  }, [nodeId])

  return lines
}

function RuntimeRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[64px_1fr] gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all">{value}</span>
    </div>
  )
}

function EntitySelector({
  entities,
  relations,
  value,
  node,
  onChange,
}: {
  entities: EntityItem[]
  relations: EntityRelation[]
  value: unknown
  node: NodeInstance
  onChange: (value: string[]) => void
}) {
  const [query, setQuery] = useState('')
  const selected = Array.isArray(value) ? value.map(String) : []
  const related = relatedEntityRefs(node, relations)
  const filtered = entities
    .filter((entity) => {
      const text = `${entity.ref} ${entity.display}`.toLowerCase()
      return text.includes(query.trim().toLowerCase())
    })
    .sort((left, right) => Number(related.has(right.ref)) - Number(related.has(left.ref)) || left.type.localeCompare(right.type))
  const groups = groupEntities(filtered)

  return (
    <div className="space-y-2">
      <div>
        <label className="block text-xs text-muted-foreground">Entities</label>
        <p className="text-[11px] text-muted-foreground">按类型选择当前节点可访问的实体</p>
      </div>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="搜索实体"
        className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
      />
      <div className="max-h-48 space-y-3 overflow-y-auto rounded-md border p-2">
        {groups.map((group) => (
          <div key={group.type} className="space-y-1">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{group.type}</div>
            {group.entities.map((entity) => {
              const active = selected.includes(entity.ref)
              return (
                <button
                  key={entity.ref}
                  type="button"
                  onClick={() => onChange(toggleItem(selected, entity.ref))}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-xs ${active ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
                >
                  <span>{entity.display}</span>
                  {related.has(entity.ref) && <span className="text-[10px] opacity-70">关联</span>}
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

function PermissionConfigurator({
  entityTypes,
  value,
  onChange,
}: {
  entityTypes: Record<string, EntityTypeDefinition>
  value: unknown
  onChange: (value: Record<string, Record<string, string>>) => void
}) {
  const permissions = isRecord(value) ? normalizePermissions(value) : {}
  const [pending, setPending] = useState<PendingPermissionOverride | null>(null)
  const update = (type: string, field: string, permission: string) => {
    const next = { ...permissions, [type]: { ...(permissions[type] ?? {}) } }
    if (!permission) delete next[type][field]
    else next[type][field] = permission
    if (Object.keys(next[type]).length === 0) delete next[type]
    onChange(next)
  }
  const startAdd = (type: string, fields: string[]) => {
    if (fields.length > 0) setPending({ type, field: fields[0], permission: '' })
  }
  const confirmAdd = () => {
    if (!pending?.field || !pending.permission) return
    update(pending.type, pending.field, pending.permission)
    setPending(null)
  }

  return (
    <div className="space-y-2">
      <div>
        <label className="block text-xs text-muted-foreground">Entity permissions</label>
        <p className="text-[11px] text-muted-foreground">按实体类型配置字段权限覆盖</p>
      </div>
      <div className="space-y-3 rounded-md border p-2">
        {Object.keys(entityTypes).length === 0 && (
          <p className="text-[11px] text-muted-foreground">未选择实体</p>
        )}
        {Object.entries(entityTypes).map(([type, definition]) => {
          const active = permissions[type] ?? {}
          const activeFields = Object.keys(active)
          const availableFields = Object.keys(definition.field_permissions).filter((field) => active[field] === undefined)
          const pendingForType = pending?.type === type ? pending : null
          return (
            <div key={type} className="space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{definition.display_name}</div>
              {activeFields.length === 0 && !pendingForType && (
                <p className="text-[11px] text-muted-foreground">暂无权限覆盖</p>
              )}
              {activeFields.map((field) => {
                const defaultPermission = definition.field_permissions[field]
                const override = active[field]
                const options = legalPermissionOptions(defaultPermission)
                return (
                  <div key={field} className="flex items-center justify-between gap-2 text-xs">
                    <span>
                      {field}
                      <span className="ml-1 text-[10px] text-muted-foreground">默认: {defaultPermission}</span>
                    </span>
                    <div className="flex items-center gap-1">
                      <select
                        aria-label={`${field} 权限覆盖`}
                        value={override}
                        onChange={(event) => update(type, field, event.target.value)}
                        className="rounded border bg-background px-2 py-1"
                      >
                        {options.map((permission) => (
                          <option key={permission} value={permission}>{permission}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        aria-label={`移除 ${field} 权限覆盖`}
                        onClick={() => update(type, field, '')}
                        className="rounded border px-2 py-1 text-muted-foreground hover:text-foreground"
                      >
                        移除
                      </button>
                    </div>
                  </div>
                )
              })}
              {pendingForType && (
                <div className="space-y-1 rounded-md bg-muted/30 p-2 text-xs">
                  <select
                    aria-label="选择权限覆盖字段"
                    value={pendingForType.field}
                    onChange={(event) => setPending({ type, field: event.target.value, permission: '' })}
                    className="w-full rounded border bg-background px-2 py-1"
                  >
                    {availableFields.map((field) => (
                      <option key={field} value={field}>{field}</option>
                    ))}
                  </select>
                  {pendingForType.field && (
                    <p className="text-[11px] text-muted-foreground">
                      默认权限: {definition.field_permissions[pendingForType.field]}
                    </p>
                  )}
                  <select
                    aria-label="选择权限级别"
                    value={pendingForType.permission}
                    onChange={(event) => setPending({ ...pendingForType, permission: event.target.value })}
                    className="w-full rounded border bg-background px-2 py-1"
                  >
                    <option value="" disabled>选择权限级别</option>
                    {legalPermissionOptions(definition.field_permissions[pendingForType.field]).map((permission) => (
                      <option key={permission} value={permission}>{permission}</option>
                    ))}
                  </select>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      aria-label={`确认添加 ${definition.display_name} 权限覆盖`}
                      onClick={confirmAdd}
                      disabled={!pendingForType.permission}
                      className="rounded border px-2 py-1 hover:bg-accent disabled:opacity-50"
                    >
                      确认
                    </button>
                    <button
                      type="button"
                      onClick={() => setPending(null)}
                      className="rounded border px-2 py-1 text-muted-foreground hover:text-foreground"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
              {!pendingForType && availableFields.length > 0 && (
                <button
                  type="button"
                  aria-label={`添加 ${definition.display_name} 权限覆盖`}
                  onClick={() => startAdd(type, availableFields)}
                  className="rounded border px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  添加权限覆盖
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
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
  if (node.entities) values.entities = node.entities
  if (node.entity_permissions) values.entity_permissions = node.entity_permissions
  if (node.timeout_seconds !== undefined) values.timeout_seconds = node.timeout_seconds
  if (node.parameters) {
    for (const [key, value] of Object.entries(node.parameters)) {
      values[`param.${key}`] = value
    }
  }
  return values
}

function omitSchemaFields(schema: InspectorSchema | undefined, fields: string[]): InspectorSchema {
  if (!schema) return {}
  const properties = { ...(schema.properties ?? {}) }
  for (const field of fields) delete properties[field]
  return { ...schema, properties }
}

function groupEntities(entities: EntityItem[]): Array<{ type: string; entities: EntityItem[] }> {
  const groups = new Map<string, EntityItem[]>()
  for (const entity of entities) {
    const group = groups.get(entity.type)
    if (group) group.push(entity)
    else groups.set(entity.type, [entity])
  }
  return Array.from(groups.entries()).map(([type, items]) => ({ type, entities: items }))
}

function relatedEntityRefs(node: NodeInstance, relations: EntityRelation[]): Set<string> {
  const source = node.config?.source
  const refs = new Set(
    typeof source === 'string' ? [source] : Array.isArray(node.config?.entities) ? node.config.entities.map(String) : [],
  )
  const related = new Set<string>()
  for (const relation of relations) {
    if (!relation.entities.some((ref) => refs.has(ref))) continue
    for (const ref of relation.entities) related.add(ref)
  }
  return related
}

function normalizePermissions(value: Record<string, unknown>): Record<string, Record<string, string>> {
  const result: Record<string, Record<string, string>> = {}
  for (const [type, fields] of Object.entries(value)) {
    if (!isRecord(fields)) continue
    result[type] = {}
    for (const [field, permission] of Object.entries(fields)) {
      if (typeof permission === 'string') result[type][field] = permission
    }
  }
  return result
}

function selectedTypes(value: unknown): Set<string> {
  const types = new Set<string>()
  if (!Array.isArray(value)) return types
  for (const ref of value) {
    const [type] = String(ref).split(':')
    if (type) types.add(type)
  }
  return types
}

function filterEntityTypes(
  entityTypes: Record<string, EntityTypeDefinition>,
  selected: Set<string>,
): Record<string, EntityTypeDefinition> {
  return Object.fromEntries(Object.entries(entityTypes).filter(([type]) => selected.has(type)))
}

function prunePermissions(value: unknown, selected: Set<string>): Record<string, Record<string, string>> {
  const permissions = isRecord(value) ? normalizePermissions(value) : {}
  return Object.fromEntries(Object.entries(permissions).filter(([type]) => selected.has(type)))
}

function toggleItem(items: string[], value: string): string[] {
  return items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
}

function legalPermissionOptions(defaultPermission: string): FieldPermission[] {
  if (!isFieldPermission(defaultPermission)) return [...FIELD_PERMISSIONS]
  return ALLOWED_PERMISSION_OVERRIDES[defaultPermission]
}

function isFieldPermission(value: string): value is FieldPermission {
  return FIELD_PERMISSIONS.includes(value as FieldPermission)
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
    if (key !== 'entities' && key !== 'entity_permissions' && isEqual(value, typeDefaults[key])) continue
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
