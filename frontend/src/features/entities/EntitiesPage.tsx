import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiFetch } from '@/api/client'

type Tab = 'types' | 'instances' | 'relations'

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

type SchemaNode = {
  type?: string
  properties?: Record<string, SchemaNode>
  required?: string[]
  default?: JsonValue
}

type EntityType = {
  display_name: string
  business_id_field: string
  display_template: string
  schema?: SchemaNode
  field_permissions?: Record<string, string>
}

type Entity = {
  id: string
  type: string
  ref: string
  display: string
  attributes: Record<string, JsonValue>
}

type Relation = {
  id: string
  entities: string[]
  type: string
  metadata: Record<string, JsonValue>
}

type TypeDialog = {
  mode: 'create' | 'edit'
  name: string
  content: string
}

type EntityDialog = {
  mode: 'create' | 'edit'
  id?: string
  type: string
  attributes: Record<string, JsonValue>
}

type RelationDialog = {
  first: string
  second: string
  type: string
}

const tabs: { key: Tab; label: string }[] = [
  { key: 'types', label: '类型' },
  { key: 'instances', label: '实例' },
  { key: 'relations', label: '关系' },
]

const typeTemplate = `display_name: 新实体
business_id_field: name
display_template: "{name}"
schema:
  type: object
  required:
    - name
  properties:
    name:
      type: string
field_permissions: {}
validate: true
`

export function EntitiesPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('types')
  const [typeDialog, setTypeDialog] = useState<TypeDialog | null>(null)
  const [entityDialog, setEntityDialog] = useState<EntityDialog | null>(null)
  const [relationDialog, setRelationDialog] = useState<RelationDialog | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const types = useQuery({
    queryKey: ['entity-types'],
    queryFn: () => apiFetch<{ types: Record<string, EntityType> }>('/api/config/entity-types'),
  })
  const entities = useQuery({
    queryKey: ['entities'],
    queryFn: () => apiFetch<{ entities: Entity[] }>('/api/entities'),
  })
  const relations = useQuery({
    queryKey: ['entity-relations'],
    queryFn: () => apiFetch<{ relations: Relation[] }>('/api/entity-relations'),
  })
  const relationTypes = useQuery({
    queryKey: ['entity-relation-types'],
    queryFn: () => apiFetch<{ types: string[] }>('/api/entity-relations/types'),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['entity-types'] })
    qc.invalidateQueries({ queryKey: ['entities'] })
    qc.invalidateQueries({ queryKey: ['entity-relations'] })
    qc.invalidateQueries({ queryKey: ['entity-relation-types'] })
  }

  const saveType = useMutation({
    mutationFn: (dialog: TypeDialog) =>
      dialog.mode === 'create'
        ? apiFetch('/api/config/entity-types', { method: 'POST', body: JSON.stringify(dialog) })
        : apiFetch(`/api/config/entity-types/${dialog.name}`, { method: 'PUT', body: JSON.stringify({ content: dialog.content }) }),
    onSuccess: () => {
      invalidate()
      setTypeDialog(null)
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const deleteType = useMutation({
    mutationFn: ({ name, cascade }: { name: string; cascade: boolean }) =>
      apiFetch(`/api/config/entity-types/${name}${cascade ? '?cascade=true' : ''}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })

  const saveEntity = useMutation({
    mutationFn: (dialog: EntityDialog) =>
      dialog.mode === 'create'
        ? apiFetch('/api/entities', { method: 'POST', body: JSON.stringify({ type: dialog.type, attributes: dialog.attributes }) })
        : apiFetch(`/api/entities/${dialog.id}`, { method: 'PUT', body: JSON.stringify({ attributes: dialog.attributes }) }),
    onSuccess: () => {
      invalidate()
      setEntityDialog(null)
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const deleteEntity = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/entities/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })

  const createRelation = useMutation({
    mutationFn: (dialog: RelationDialog) =>
      apiFetch('/api/entity-relations', {
        method: 'POST',
        body: JSON.stringify({ entities: [dialog.first, dialog.second], type: dialog.type }),
      }),
    onSuccess: () => {
      invalidate()
      setRelationDialog(null)
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const deleteRelation = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/entity-relations/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })

  const typeMap = types.data?.types ?? {}
  const entityList = entities.data?.entities ?? []
  const relationList = relations.data?.relations ?? []
  const entityByRef = entityList.reduce<Record<string, Entity>>((acc, entity) => {
    acc[entity.id] = entity
    acc[entity.ref] = entity
    return acc
  }, {})

  const openEditType = async (name: string) => {
    setFormError(null)
    const response = await apiFetch<{ name: string; content: string }>(`/api/config/entity-types/${name}`)
    setTypeDialog({ mode: 'edit', name: response.name, content: response.content })
  }

  const confirmDeleteType = (name: string) => {
    const instanceCount = entityList.filter((entity) => entity.type === name).length
    const message = instanceCount
      ? `该类型下有 ${instanceCount} 个实例，是否同时删除？`
      : `确认删除类型 ${name}？`
    if (window.confirm(message)) {
      deleteType.mutate({ name, cascade: instanceCount > 0 })
    }
  }

  const openCreateEntity = () => {
    const firstType = Object.keys(typeMap)[0] ?? ''
    setFormError(null)
    setEntityDialog({ mode: 'create', type: firstType, attributes: defaultsFor(typeMap[firstType]?.schema) })
  }

  const confirmDeleteEntity = (entity: Entity) => {
    const count = relationList.filter((relation) => relation.entities.includes(entity.id) || relation.entities.includes(entity.ref)).length
    const message = count ? `将同时移除 ${count} 条关联关系，确认删除？` : `确认删除 ${entity.display}？`
    if (window.confirm(message)) {
      deleteEntity.mutate(entity.id)
    }
  }

  const submitEntity = () => {
    if (!entityDialog) return
    const missing = requiredMissing(typeMap[entityDialog.type]?.schema, entityDialog.attributes)
    if (missing.length) {
      setFormError(`缺少必填字段: ${missing.join(', ')}`)
      return
    }
    saveEntity.mutate(entityDialog)
  }

  const submitRelation = () => {
    if (!relationDialog) return
    if (!relationDialog.first || !relationDialog.second || !relationDialog.type.trim()) {
      setFormError('请选择两个实体并填写关系类型')
      return
    }
    createRelation.mutate(relationDialog)
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-semibold">实体管理</h1>
        <p className="text-sm text-muted-foreground">管理实体类型、实例和实体关系。</p>
      </div>

      <div className="flex gap-1 border-b">
        {tabs.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === item.key ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'types' && (
        <section className="space-y-4">
          <button
            onClick={() => {
              setFormError(null)
              setTypeDialog({ mode: 'create', name: '', content: typeTemplate })
            }}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
          >
            新建类型
          </button>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(typeMap).map(([name, type]) => (
              <article key={name} className="rounded-lg border bg-card p-4 space-y-3">
                <div>
                  <h2 className="font-medium">{type.display_name}</h2>
                  <p className="text-xs text-muted-foreground">{name}</p>
                </div>
                <p className="text-xs text-muted-foreground">业务 ID: {type.business_id_field}</p>
                <div className="flex gap-2">
                  <button onClick={() => openEditType(name)} className="rounded-md border px-3 py-1.5 text-xs hover:bg-accent">编辑</button>
                  <button onClick={() => confirmDeleteType(name)} className="rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-accent">删除</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === 'instances' && (
        <section className="space-y-4">
          <button onClick={openCreateEntity} className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90">
            新建实例
          </button>
          {Object.entries(groupByType(entityList)).map(([typeName, items]) => (
            <div key={typeName} className="space-y-2">
              <h2 className="text-sm font-medium">{typeMap[typeName]?.display_name ?? typeName}</h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {items.map((entity) => (
                  <article key={entity.id} className="rounded-lg border bg-card p-4 space-y-3">
                    <div>
                      <h3 className="font-medium">{entity.display}</h3>
                      <p className="text-xs text-muted-foreground">{entity.ref}</p>
                    </div>
                    <p className="line-clamp-3 text-xs text-muted-foreground">{JSON.stringify(entity.attributes)}</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setFormError(null)
                          setEntityDialog({ mode: 'edit', id: entity.id, type: entity.type, attributes: entity.attributes })
                        }}
                        className="rounded-md border px-3 py-1.5 text-xs hover:bg-accent"
                      >
                        编辑
                      </button>
                      <button onClick={() => confirmDeleteEntity(entity)} className="rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-accent">删除</button>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {tab === 'relations' && (
        <section className="space-y-4">
          <button
            onClick={() => {
              setFormError(null)
              setRelationDialog({ first: entityList[0]?.ref ?? '', second: entityList[1]?.ref ?? '', type: relationTypes.data?.types[0] ?? '' })
            }}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
          >
            新建关系
          </button>
          <div className="space-y-2">
            {relationList.map((relation) => (
              <article key={relation.id} className="flex flex-col gap-3 rounded-lg border bg-card p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-medium">{relation.entities.map((ref) => entityByRef[ref]?.display ?? ref).join(' -> ')}</p>
                  <p className="text-xs text-muted-foreground">{relation.type}</p>
                </div>
                <button
                  onClick={() => window.confirm('确认删除该关系？') && deleteRelation.mutate(relation.id)}
                  className="w-fit rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-accent"
                >
                  删除
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      {typeDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-3xl rounded-lg border bg-background p-5 shadow-xl space-y-4">
            <h2 className="font-semibold">{typeDialog.mode === 'create' ? '新建类型' : `编辑 ${typeDialog.name}`}</h2>
            {typeDialog.mode === 'create' && (
              <input
                value={typeDialog.name}
                onChange={(event) => setTypeDialog({ ...typeDialog, name: event.target.value })}
                placeholder="name"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
            )}
            <textarea
              value={typeDialog.content}
              onChange={(event) => setTypeDialog({ ...typeDialog, content: event.target.value })}
              className="h-[420px] w-full resize-y rounded-md border bg-background px-3 py-2 font-mono text-sm"
              spellCheck={false}
            />
            <DialogActions error={formError} onCancel={() => setTypeDialog(null)} onSave={() => saveType.mutate(typeDialog)} pending={saveType.isPending} />
          </div>
        </div>
      )}

      {entityDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-2xl rounded-lg border bg-background p-5 shadow-xl space-y-4">
            <h2 className="font-semibold">{entityDialog.mode === 'create' ? '新建实例' : '编辑实例'}</h2>
            {entityDialog.mode === 'create' && (
              <select
                value={entityDialog.type}
                onChange={(event) => setEntityDialog({ mode: 'create', type: event.target.value, attributes: defaultsFor(typeMap[event.target.value]?.schema) })}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                {Object.keys(typeMap).map((name) => <option key={name} value={name}>{typeMap[name].display_name}</option>)}
              </select>
            )}
            <div className="max-h-[55vh] overflow-auto pr-1">
              <SchemaFields
                schema={typeMap[entityDialog.type]?.schema}
                permissions={typeMap[entityDialog.type]?.field_permissions ?? {}}
                values={entityDialog.attributes}
                editing={entityDialog.mode === 'edit'}
                onChange={(attributes) => setEntityDialog({ ...entityDialog, attributes })}
              />
            </div>
            <DialogActions error={formError} onCancel={() => setEntityDialog(null)} onSave={submitEntity} pending={saveEntity.isPending} />
          </div>
        </div>
      )}

      {relationDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border bg-background p-5 shadow-xl space-y-4">
            <h2 className="font-semibold">新建关系</h2>
            <EntitySelect label="实体 A" value={relationDialog.first} entities={entityList} onChange={(first) => setRelationDialog({ ...relationDialog, first })} />
            <EntitySelect label="实体 B" value={relationDialog.second} entities={entityList} onChange={(second) => setRelationDialog({ ...relationDialog, second })} />
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">关系类型</span>
              <input
                value={relationDialog.type}
                onChange={(event) => setRelationDialog({ ...relationDialog, type: event.target.value })}
                list="relation-types"
                className="w-full rounded-md border bg-background px-3 py-2"
              />
              <datalist id="relation-types">
                {(relationTypes.data?.types ?? []).map((item) => <option key={item} value={item} />)}
              </datalist>
            </label>
            <DialogActions error={formError} onCancel={() => setRelationDialog(null)} onSave={submitRelation} pending={createRelation.isPending} />
          </div>
        </div>
      )}

      {(types.error || entities.error || relations.error) && (
        <p className="text-sm text-destructive">{errorMessage(types.error || entities.error || relations.error)}</p>
      )}
    </div>
  )
}

function DialogActions({ error, onCancel, onSave, pending }: { error: string | null; onCancel: () => void; onSave: () => void; pending: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm text-destructive">{error}</p>
      <div className="flex gap-2">
        <button onClick={onCancel} className="rounded-md border px-4 py-2 text-sm hover:bg-accent">取消</button>
        <button onClick={onSave} disabled={pending} className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {pending ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  )
}

function EntitySelect({ label, value, entities, onChange }: { label: string; value: string; entities: Entity[]; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-md border bg-background px-3 py-2">
        {entities.map((entity) => <option key={entity.id} value={entity.ref}>{entity.display}</option>)}
      </select>
    </label>
  )
}

function SchemaFields({ schema, permissions, values, editing, onChange }: { schema?: SchemaNode; permissions: Record<string, string>; values: Record<string, JsonValue>; editing: boolean; onChange: (values: Record<string, JsonValue>) => void }) {
  const properties = schema?.properties ?? {}
  return (
    <div className="space-y-3">
      {Object.entries(properties).map(([name, field]) => (
        <FieldInput
          key={name}
          name={name}
          field={field}
          value={values[name]}
          disabled={editing && permissions[name] === 'read-only'}
          onChange={(value) => onChange({ ...values, [name]: value })}
        />
      ))}
    </div>
  )
}

function FieldInput({ name, field, value, disabled, onChange }: { name: string; field: SchemaNode; value: JsonValue | undefined; disabled: boolean; onChange: (value: JsonValue) => void }) {
  if (field.type === 'object' && field.properties) {
    const current = isRecord(value) ? value : {}
    return (
      <fieldset className="rounded-md border p-3 space-y-3">
        <legend className="px-1 text-sm text-muted-foreground">{name}</legend>
        {Object.entries(field.properties).map(([childName, childField]) => (
          <FieldInput
            key={childName}
            name={childName}
            field={childField}
            value={current[childName]}
            disabled={disabled}
            onChange={(childValue) => onChange({ ...current, [childName]: childValue })}
          />
        ))}
      </fieldset>
    )
  }
  if (field.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
        {name}
      </label>
    )
  }
  if (field.type === 'number' || field.type === 'integer') {
    return (
      <LabeledInput
        name={name}
        type="number"
        value={typeof value === 'number' ? String(value) : ''}
        disabled={disabled}
        onChange={(next) => onChange(field.type === 'integer' ? Number.parseInt(next || '0', 10) : Number(next || 0))}
      />
    )
  }
  if (field.type === 'object' && !field.properties) {
    return (
      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">{name}</span>
        <textarea
          value={JSON.stringify(value ?? {}, null, 2)}
          disabled={disabled}
          onChange={(event) => onChange(parseJson(event.target.value))}
          className="h-28 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm disabled:opacity-60"
        />
      </label>
    )
  }
  return (
    <LabeledInput
      name={name}
      value={typeof value === 'string' ? value : ''}
      disabled={disabled}
      onChange={onChange}
    />
  )
}

function LabeledInput({ name, value, disabled, onChange, type = 'text' }: { name: string; value: string; disabled: boolean; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-muted-foreground">{name}</span>
      <input value={value} type={type} disabled={disabled} onChange={(event) => onChange(event.target.value)} className="w-full rounded-md border bg-background px-3 py-2 disabled:opacity-60" />
    </label>
  )
}

function groupByType(entities: Entity[]): Record<string, Entity[]> {
  return entities.reduce<Record<string, Entity[]>>((acc, entity) => {
    acc[entity.type] = [...(acc[entity.type] ?? []), entity]
    return acc
  }, {})
}

function defaultsFor(schema?: SchemaNode): Record<string, JsonValue> {
  const result: Record<string, JsonValue> = {}
  for (const [name, field] of Object.entries(schema?.properties ?? {})) {
    if (field.default !== undefined) result[name] = field.default
    else if (field.type === 'boolean') result[name] = false
    else if (field.type === 'number' || field.type === 'integer') result[name] = 0
    else if (field.type === 'object') result[name] = {}
    else if (field.type === 'array') result[name] = []
    else result[name] = ''
  }
  return result
}

function requiredMissing(schema: SchemaNode | undefined, values: Record<string, JsonValue>): string[] {
  return (schema?.required ?? []).filter((field) => values[field] === undefined || values[field] === '')
}

function parseJson(value: string): JsonValue {
  try {
    return JSON.parse(value) as JsonValue
  } catch {
    return value
  }
}

function isRecord(value: JsonValue | undefined): value is Record<string, JsonValue> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '请求失败'
}
