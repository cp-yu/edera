import { useEffect, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'
import { useEntities, useNodeLogs, useNodeOutputs } from '@/api/queries'
import { useCreateEntity, useDeleteEntity, useSaveDag, useUpdateEntity } from '@/api/mutations'
import type { DagEdge, DagNodeRecord, DagState, EntityItem, EntityRelation, EntityTypeDefinition, InspectorSchema, NodeExecutionLog, NodeInstance, NodeOutputEntity, NodeStatus, RuntimeStatus, TriggerAttributes } from '@/api/types'
import { useAppStore } from '@/store/useAppStore'
import { SchemaForm } from './SchemaForm'

const TOP_LEVEL_FIELDS = new Set(['model', 'skills', 'entities', 'entity_permissions', 'timeout_seconds'])
const FIELD_PERMISSIONS = ['none', 'read-only', 'write-only', 'read-write'] as const
type FieldPermission = typeof FIELD_PERMISSIONS[number]
type PendingPermissionOverride = { type: string; field: string; permission: string }
type InspectorTab = 'config' | 'runtime' | 'triggers'
type TriggerFormValue = TriggerAttributes

const ALLOWED_PERMISSION_OVERRIDES: Record<FieldPermission, FieldPermission[]> = {
  none: ['none', 'read-only', 'write-only', 'read-write'],
  'read-only': ['read-only', 'read-write'],
  'write-only': ['write-only', 'read-write'],
  'read-write': ['read-write'],
}

export function Inspector({
  dagName,
  dag,
  runtimeStatus: runtime,
  subDagRuntimeEmpty = false,
}: {
  dagName: string
  dag: DagState | null
  runtimeStatus: RuntimeStatus | null
  subDagRuntimeEmpty?: boolean
}) {
  const { inspectorTab, selectedEdgeId, selectedNodeId, setInspectorTab } = useAppStore()
  const saveDag = useSaveDag(dagName)
  const node = dag?.nodes.find((item) => item.id === selectedNodeId)
  const edge = dag?.edges.find((item, index) => `e-${item.from}-${item.to}-${index}` === selectedEdgeId)
  const runtimeNodeId = edge?.from ?? node?.id ?? null
  const runtimeStatus = runtimeNodeId ? runtime?.node_statuses?.[runtimeNodeId] : undefined
  const outputs = useNodeOutputs(runtimeNodeId, runtimeStatus?.run_id)
  const logs = useNodeLogs(runtimeNodeId, runtimeStatus?.run_id)
  const stdout = useNodeStdout(runtimeNodeId)
  const [alias, setAlias] = useState('')
  const [instanceOptional, setInstanceOptional] = useState(false)
  const [loopMode, setLoopMode] = useState<'' | 'parallel' | 'serial'>('')
  const [loopCount, setLoopCount] = useState<number | undefined>(undefined)
  const [loopUntil, setLoopUntil] = useState('')
  const [loopResource, setLoopResource] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<Record<string, unknown>>({})

  useEffect(() => {
    if (!node) return
    setAlias(node.alias ?? '')
    setInstanceOptional(Boolean(node.optional))
    setLoopMode(node.loop?.mode ?? '')
    setLoopCount(node.loop?.count)
    setLoopUntil(node.loop?.until ?? '')
    setLoopResource(node.resource ?? null)
    setFormValues(flattenConfig(node.config))
  }, [node])

  const typeDefaults = useMemo(() => (node ? defaultValues(node) : {}), [node])
  const displayDefaults = useMemo(() => {
    if (!node) return {}
    return mergeSchemaDefaults(typeDefaults, node.inspector_schema ?? {})
  }, [node, typeDefaults])
  const formSchema = useMemo(() => omitSchemaFields(node?.inspector_schema, ['entities', 'entity_permissions']), [node])
  const selectedEntityTypes = useMemo(() => selectedTypes(formValues.entities), [formValues.entities])
  const permissionEntityTypes = useMemo(
    () => filterEntityTypes(dag?.entity_types ?? {}, selectedEntityTypes),
    [dag?.entity_types, selectedEntityTypes],
  )

  if (edge && dag) {
    const saveEdge = (patch: Partial<Pick<DagEdge, 'fan_in' | 'fan_out' | 'optional'>>) => {
      const edges = dag.edges.map((item, index) =>
        `e-${item.from}-${item.to}-${index}` === selectedEdgeId ? { ...item, ...patch } : item,
      )
      const nodes: DagNodeRecord[] = dag.nodes.map((item) => ({
        id: item.id,
        type: item.type_name,
        dag_ref: item.dag_ref,
        input_mapping: item.input_mapping,
        alias: item.alias,
        config: item.config ?? {},
        optional: Boolean(item.optional),
      }))
      saveDag.mutate({ nodes, edges, ui: dag.ui })
    }
    return (
      <aside className="w-[300px] space-y-4 overflow-y-auto border-l bg-card p-4">
        <div>
          <h2 className="text-sm font-medium">数据流</h2>
          <p className="text-xs text-muted-foreground">{edge.from} → {edge.to}</p>
        </div>
        <RuntimeStatusView
          status={runtimeStatus}
          outputs={outputs.data?.outputs ?? []}
          logs={logs.data?.logs ?? []}
          stdout={stdout}
          subDagRuntimeEmpty={subDagRuntimeEmpty}
        />
        <a
          href={`/history/dag/${dagName}/nodes/${edge.from}`}
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(edge.optional)}
            onChange={(event) => saveEdge({ optional: event.target.checked })}
          />
          optional
        </label>
      </aside>
    )
  }

  if (!dag) {
    return (
      <aside className="w-[300px] border-l bg-card p-4">
        <p className="text-sm text-muted-foreground">选择节点或连线查看详情</p>
      </aside>
    )
  }

  if (!node) {
    return (
      <aside className="w-[300px] space-y-4 overflow-y-auto border-l bg-card p-4">
        <div>
          <h2 className="text-sm font-medium">{dagName}</h2>
          <p className="text-xs text-muted-foreground">DAG</p>
        </div>
        <InspectorTabs active={inspectorTab} onChange={setInspectorTab} />
        {inspectorTab === 'triggers' ? (
          <TriggersPanel dagName={dagName} dag={dag} node={null} />
        ) : (
          <p className="text-sm text-muted-foreground">选择节点或连线查看详情</p>
        )}
      </aside>
    )
  }

  const save = () => {
    const nodes: DagNodeRecord[] = dag.nodes.map((item) => {
      if (item.id !== node.id) {
        return { id: item.id, type: item.type_name, dag_ref: item.dag_ref, input_mapping: item.input_mapping, alias: item.alias, config: item.config ?? {}, optional: Boolean(item.optional), loop: item.loop, resource: item.resource }
      }
      const config = buildConfig(item, formValues, typeDefaults)
      const loop = loopMode ? { mode: loopMode, count: loopCount, until: loopUntil || undefined } : undefined
      return { id: item.id, type: item.type_name, dag_ref: item.dag_ref, input_mapping: item.input_mapping, alias: alias || item.type_name, config, optional: instanceOptional, loop, resource: loopResource }
    })
    saveDag.mutate({ nodes, edges: dag.edges, ui: dag.ui })
  }

  return (
    <aside className="flex h-full w-[300px] flex-col border-l bg-card">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <div>
          <h2 className="text-sm font-medium">{node.alias || node.name}</h2>
          <p className="text-xs text-muted-foreground">{node.type_name} · {node.role}</p>
        </div>
        <InspectorTabs active={inspectorTab} onChange={setInspectorTab} />
        {inspectorTab === 'runtime' ? (
          <RuntimeStatusView
            status={runtimeStatus}
            outputs={outputs.data?.outputs ?? []}
            logs={logs.data?.logs ?? []}
            stdout={stdout}
            subDagRuntimeEmpty={subDagRuntimeEmpty}
          />
        ) : inspectorTab === 'triggers' ? (
          <TriggersPanel dagName={dagName} dag={dag} node={node} />
        ) : (
          <>
            <div className="space-y-4">
              <Field label="Alias" value={alias} onChange={setAlias} />
              <Readonly label="name" value={node.name} />
              <Readonly label="类型" value={node.type_name} />
              <Readonly label="角色" value={node.role} />
              <Readonly label="输入" value={node.input_type} />
              <Readonly label="输出" value={node.output_type} />
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={instanceOptional}
                  onChange={(event) => setInstanceOptional(event.target.checked)}
                />
                <span>
                  当前 DAG 当前实例 optional
                  <span className="block text-xs text-muted-foreground">仅影响此节点实例的出边</span>
                </span>
              </label>
              <LoopConfigurator
                mode={loopMode}
                count={loopCount}
                until={loopUntil}
                resource={loopResource}
                resources={dag.entities?.filter((e) => e.type === 'resource') ?? []}
                onModeChange={setLoopMode}
                onCountChange={setLoopCount}
                onUntilChange={setLoopUntil}
                onResourceChange={setLoopResource}
              />
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
            </div>
            <div data-inspector-config-footer className="sticky bottom-0 -mx-4 mt-4 border-t bg-card p-4">
              <button
                onClick={save}
                disabled={saveDag.isPending}
                className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {saveDag.isPending ? '保存中...' : '保存实例'}
              </button>
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

function InspectorTabs({ active, onChange }: { active: InspectorTab; onChange: (tab: InspectorTab) => void }) {
  return (
    <div className="grid grid-cols-3 rounded-md border p-1 text-xs">
      {(['config', 'runtime', 'triggers'] as const).map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={`rounded px-2 py-1 ${active === tab ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
        >
          {tab === 'config' ? 'Config' : tab === 'runtime' ? 'Runtime' : 'Triggers'}
        </button>
      ))}
    </div>
  )
}

function TriggersPanel({ dagName, dag, node }: { dagName: string; dag: { nodes: NodeInstance[] }; node: NodeInstance | null }) {
  const target = node ? `node:${dagName}/${node.id}` : `dag:${dagName}`
  const triggers = useEntities('trigger')
  const createEntity = useCreateEntity()
  const updateEntity = useUpdateEntity()
  const deleteEntity = useDeleteEntity()
  const expressionRef = useRef<HTMLTextAreaElement>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<TriggerFormValue>(() => emptyTrigger(target))
  const [error, setError] = useState('')

  useEffect(() => {
    setEditingId(null)
    setDraft(emptyTrigger(target))
    setError('')
  }, [target])

  const items = (triggers.data?.entities ?? [])
    .map(toTriggerEntity)
    .filter((item): item is EntityItem & { attributes: TriggerAttributes } => !!item && item.attributes.target === target)

  const startEdit = (item: EntityItem & { attributes: TriggerAttributes }) => {
    setEditingId(item.id)
    setDraft({
      name: item.attributes.name,
      wait_for: item.attributes.wait_for,
      target,
      enabled: item.attributes.enabled !== false,
    })
    setError('')
  }

  const save = () => {
    const validation = validateTriggerExpression(draft.wait_for)
    if (validation) {
      setError(validation)
      return
    }
    const attributes = {
      name: draft.name.trim(),
      wait_for: draft.wait_for.trim(),
      target,
      enabled: draft.enabled !== false,
    }
    if (!attributes.name) {
      setError('Trigger 名称不能为空')
      return
    }
    setError('')
    if (editingId) updateEntity.mutate({ id: editingId, type: 'trigger', attributes })
    else createEntity.mutate({ type: 'trigger', attributes })
    setEditingId(null)
    setDraft(emptyTrigger(target))
  }

  const insertToken = (token: string) => {
    const input = expressionRef.current
    setDraft((current) => ({
      ...current,
      wait_for: input
        ? insertExpressionToken(current.wait_for, token, input.selectionStart, input.selectionEnd)
        : appendExpressionToken(current.wait_for, token),
    }))
    setError('')
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs font-medium">Triggers</div>
        <p className="break-all text-[11px] text-muted-foreground">{target}</p>
      </div>
      <div className="space-y-2">
        {items.length === 0 && <p className="text-xs text-muted-foreground">暂无 trigger</p>}
        {items.map((item) => (
          <div key={item.id} className="space-y-2 rounded-md border p-2 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate font-medium">{item.attributes.name}</div>
                <div className="break-all text-[11px] text-muted-foreground">{item.attributes.wait_for}</div>
              </div>
              <input
                aria-label={`${item.attributes.name} enabled`}
                type="checkbox"
                checked={item.attributes.enabled !== false}
                onChange={(event) => updateEntity.mutate({
                  id: item.id,
                  type: 'trigger',
                  attributes: { enabled: event.target.checked },
                })}
              />
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => startEdit(item)} className="rounded border px-2 py-1 hover:bg-accent">编辑</button>
              <button
                type="button"
                onClick={() => deleteEntity.mutate({ id: item.id, type: 'trigger' })}
                className="rounded border px-2 py-1 text-destructive hover:bg-accent"
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="space-y-2 rounded-md border p-2">
        <div className="text-xs font-medium">{editingId ? '编辑 trigger' : '新建 trigger'}</div>
        <Field label="Name" value={draft.name} onChange={(name) => setDraft((current) => ({ ...current, name }))} />
        <ExpressionEditor
          inputRef={expressionRef}
          value={draft.wait_for}
          error={error}
          onChange={(wait_for) => {
            setDraft((current) => ({ ...current, wait_for }))
            setError('')
          }}
        />
        <CronPicker onInsert={insertToken} />
        <EventPicker dag={dag} node={node} onInsert={insertToken} />
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={draft.enabled !== false}
            onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
          />
          enabled
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={save}
            disabled={createEntity.isPending || updateEntity.isPending}
            className="flex-1 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {editingId ? '保存 trigger' : '创建 trigger'}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={() => {
                setEditingId(null)
                setDraft(emptyTrigger(target))
                setError('')
              }}
              className="rounded-md border px-3 py-2 text-sm hover:bg-accent"
            >
              取消
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ExpressionEditor({
  inputRef,
  value,
  error,
  onChange,
}: {
  inputRef: RefObject<HTMLTextAreaElement | null>
  value: string
  error: string
  onChange: (value: string) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-muted-foreground">Expression</label>
      <textarea
        ref={inputRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
      />
      {error && <p className="mt-1 text-[11px] text-destructive">{error}</p>}
    </div>
  )
}

function CronPicker({ onInsert }: { onInsert: (token: string) => void }) {
  const [time, setTime] = useState('09:00')
  const [repeat, setRepeat] = useState('daily')
  const [date, setDate] = useState('2026-05-30')
  const [weekdays, setWeekdays] = useState<string[]>(['1'])
  const [advanced, setAdvanced] = useState('')
  const cron = advanced.trim() || cronFromPicker(time, repeat, date, weekdays)

  return (
    <div className="space-y-2 rounded-md bg-muted/30 p-2">
      <div className="text-xs font-medium">插入定时</div>
      <div className="grid grid-cols-[1fr_1.2fr] gap-2">
        <input
          aria-label="触发时间"
          type="time"
          value={time}
          onChange={(event) => setTime(event.target.value)}
          className="rounded border bg-background px-2 py-1 text-xs"
        />
        <select
          aria-label="重复规则"
          value={repeat}
          onChange={(event) => setRepeat(event.target.value)}
          className="rounded border bg-background px-2 py-1 text-xs"
        >
          <option value="daily">每天</option>
          <option value="weekdays">工作日</option>
          <option value="weekends">周末</option>
          <option value="custom">自定义周几</option>
          <option value="once">一次性</option>
        </select>
      </div>
      {repeat === 'custom' && (
        <div className="grid grid-cols-4 gap-1">
          {[
            ['1', '周一'],
            ['2', '周二'],
            ['3', '周三'],
            ['4', '周四'],
            ['5', '周五'],
            ['6', '周六'],
            ['0', '周日'],
          ].map(([value, label]) => (
            <label key={value} className="flex items-center gap-1 rounded border px-2 py-1 text-[11px]">
              <input
                aria-label={label}
                type="checkbox"
                checked={weekdays.includes(value)}
                onChange={() => setWeekdays((current) => toggleItem(current, value))}
              />
              {label}
            </label>
          ))}
        </div>
      )}
      {repeat === 'once' && (
        <input
          aria-label="触发日期"
          type="date"
          value={date}
          onChange={(event) => setDate(event.target.value)}
          className="w-full rounded border bg-background px-2 py-1 text-xs"
        />
      )}
      <input
        aria-label="高级 cron"
        value={advanced}
        onChange={(event) => setAdvanced(event.target.value)}
        placeholder="高级 cron"
        className="w-full rounded border bg-background px-2 py-1 text-xs"
      />
      <button type="button" onClick={() => onInsert(`cron:"${cron}"`)} className="rounded border px-2 py-1 text-xs hover:bg-accent">
        插入 {`cron:"${cron}"`}
      </button>
    </div>
  )
}

function EventPicker({
  dag,
  node,
  onInsert,
}: {
  dag: { nodes: NodeInstance[] }
  node: NodeInstance | null
  onInsert: (token: string) => void
}) {
  const options = eventOptions(dag.nodes, node)
  const [selected, setSelected] = useState(options[0] ?? '')
  const [custom, setCustom] = useState('')
  const token = custom.trim() || selected

  useEffect(() => {
    setSelected(options[0] ?? '')
    setCustom('')
  }, [node?.id])

  return (
    <div className="space-y-2 rounded-md bg-muted/30 p-2">
      <div className="text-xs font-medium">插入事件</div>
      <select
        aria-label="事件源"
        value={selected}
        onChange={(event) => setSelected(event.target.value)}
        className="w-full rounded border bg-background px-2 py-1 text-xs"
      >
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
      <input
        aria-label="自定义事件"
        value={custom}
        onChange={(event) => setCustom(event.target.value)}
        placeholder="event:custom"
        className="w-full rounded border bg-background px-2 py-1 text-xs"
      />
      <button type="button" onClick={() => token && onInsert(token)} className="rounded border px-2 py-1 text-xs hover:bg-accent">
        插入事件
      </button>
    </div>
  )
}

function RuntimeStatusView({
  status,
  outputs,
  logs,
  stdout,
  subDagRuntimeEmpty = false,
}: {
  status?: NodeStatus
  outputs: NodeOutputEntity[]
  logs: NodeExecutionLog[]
  stdout: string[]
  subDagRuntimeEmpty?: boolean
}) {
  return (
    <div className="space-y-3">
      {subDagRuntimeEmpty && (
        <div className="rounded-md border p-3 text-xs text-muted-foreground">
          当前 Sub DAG 实例还没有 child run
        </div>
      )}
      <div className="space-y-2 rounded-md border p-3 text-xs">
        <RuntimeRow label="status" value={status?.status ?? 'unknown'} />
        <RuntimeRow label="run" value={status?.run_id ?? '-'} />
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
      <LogList logs={logs} />
      <div className="space-y-2">
        <div className="text-xs font-medium">stdout</div>
        <pre className="max-h-36 overflow-auto rounded-md border bg-muted/30 p-2 text-[11px] whitespace-pre-wrap">
          {stdout.length > 0 ? stdout.join('\n') : '暂无输出'}
        </pre>
      </div>
    </div>
  )
}

function LogList({ logs }: { logs: NodeExecutionLog[] }) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium">Logs</div>
      {logs.length === 0 ? (
        <p className="text-xs text-muted-foreground">暂无日志</p>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="rounded-md border p-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{log.kind}</span>
                <span className="text-[11px] text-muted-foreground">{log.size} bytes</span>
              </div>
              <div className="mt-1 break-all text-[11px] text-muted-foreground">{log.path}</div>
              <div className="mt-1 break-all text-[11px] text-muted-foreground">{log.digest}</div>
            </div>
          ))}
        </div>
      )}
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
      const line = data.line
      if (typeof line !== 'string') return
      setLines((current) => [...current.slice(-199), line])
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

function emptyTrigger(target: string): TriggerFormValue {
  const suffix = target.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '')
  return { name: `trigger-${suffix}`, wait_for: '', target, enabled: true }
}

function toTriggerEntity(entity: EntityItem): (EntityItem & { attributes: TriggerAttributes }) | null {
  const attrs = entity.attributes
  if (
    typeof attrs.name !== 'string'
    || typeof attrs.wait_for !== 'string'
    || typeof attrs.target !== 'string'
  ) {
    return null
  }
  return {
    ...entity,
    attributes: {
      name: attrs.name,
      wait_for: attrs.wait_for,
      target: attrs.target,
      enabled: typeof attrs.enabled === 'boolean' ? attrs.enabled : true,
    },
  }
}

function validateTriggerExpression(expression: string): string {
  const text = expression.trim()
  if (!text) return '表达式不能为空'
  if (/(^|[\s(])manual:/.test(text)) return 'manual 前缀仅用于 emit，不能写入 wait_for'
  if (/cron:\s*[^"]/.test(text)) return 'cron 表达式必须写成 cron:"分 时 日 月 周"'
  let depth = 0
  for (const char of text) {
    if (char === '(') depth += 1
    if (char === ')') depth -= 1
    if (depth < 0) return '括号不匹配'
  }
  if (depth !== 0) return '括号不匹配'
  const cronTokens = text.match(/cron:"[^"]*"/g) ?? []
  for (const token of cronTokens) {
    const fields = token.slice(6, -1).trim().split(/\s+/)
    if (fields.length !== 5) return 'cron 表达式需要 5 个字段'
  }
  return ''
}

function appendExpressionToken(expression: string, token: string): string {
  const text = expression.trim()
  return text ? `${text} AND ${token}` : token
}

function insertExpressionToken(expression: string, token: string, start: number, end: number): string {
  if (start === end && start === expression.length) return appendExpressionToken(expression, token)
  return `${expression.slice(0, start)}${token}${expression.slice(end)}`
}

function cronFromPicker(time: string, repeat: string, date: string, weekdays: string[]): string {
  const [hour = '9', minute = '0'] = time.split(':')
  const [_year, month = '*', dayOfMonth = '*'] = date.split('-')
  if (repeat === 'once') return `${Number(minute)} ${Number(hour)} ${Number(dayOfMonth)} ${Number(month)} *`
  const day = repeat === 'weekdays'
    ? '1-5'
    : repeat === 'weekends'
      ? '6,0'
      : repeat === 'custom'
        ? (weekdays.length > 0 ? weekdays.join(',') : '*')
        : '*'
  return `${Number(minute)} ${Number(hour)} * * ${day}`
}

function eventOptions(nodes: NodeInstance[], node: NodeInstance | null): string[] {
  const options = new Set<string>([
    'event:config-changed',
    'event:entity-changed:*',
  ])
  if (node) {
    for (const event of declaredEvents(node.emits)) options.add(event)
    const configEmits = Array.isArray(node.config?.emits) ? node.config.emits : []
    for (const event of declaredEvents(configEmits)) options.add(event)
  } else {
    for (const item of nodes) {
      for (const event of declaredEvents(item.emits)) options.add(event)
      const configEmits = Array.isArray(item.config?.emits) ? item.config.emits : []
      for (const event of declaredEvents(configEmits)) options.add(event)
    }
  }
  return Array.from(options)
}

function declaredEvents(emits: unknown): string[] {
  if (!Array.isArray(emits)) return []
  return emits
    .map((item): string | null => {
      if (typeof item === 'string') return item
      if (isRecord(item) && typeof item.event === 'string') return item.event
      return null
    })
    .filter((item): item is string => !!item)
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
    <div data-inspector-readonly={label}>
      <label className="text-xs text-muted-foreground">{label}</label>
      <p className="text-sm">{value}</p>
    </div>
  )
}

function LoopConfigurator({
  mode,
  count,
  until,
  resource,
  resources,
  onModeChange,
  onCountChange,
  onUntilChange,
  onResourceChange,
}: {
  mode: '' | 'parallel' | 'serial'
  count: number | undefined
  until: string
  resource: string | null
  resources: EntityItem[]
  onModeChange: (mode: '' | 'parallel' | 'serial') => void
  onCountChange: (count: number | undefined) => void
  onUntilChange: (until: string) => void
  onResourceChange: (resource: string | null) => void
}) {
  const [expanded, setExpanded] = useState(Boolean(mode))

  return (
    <details open={expanded} onToggle={(e) => setExpanded((e.target as HTMLDetailsElement).open)} className="space-y-2">
      <summary className="cursor-pointer text-sm font-medium">循环</summary>
      <div className="space-y-2 pl-4">
        <div>
          <label className="mb-1 block text-xs text-muted-foreground">Mode</label>
          <select
            value={mode}
            onChange={(e) => onModeChange(e.target.value as '' | 'parallel' | 'serial')}
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
          >
            <option value="">无</option>
            <option value="parallel">parallel</option>
            <option value="serial">serial</option>
          </select>
        </div>
        {mode && (
          <>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Count</label>
              <input
                type="number"
                value={count ?? ''}
                onChange={(e) => onCountChange(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Until</label>
              <input
                value={until}
                onChange={(e) => onUntilChange(e.target.value)}
                placeholder="optional condition"
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Resource</label>
              <select
                value={resource ?? ''}
                onChange={(e) => onResourceChange(e.target.value || null)}
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              >
                <option value="">无</option>
                {resources.map((res) => (
                  <option key={res.ref} value={res.ref}>{res.display}</option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>
    </details>
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
