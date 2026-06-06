import { useEffect, useState, type ReactNode } from 'react'
import { useHandler, useHandlers, useNodeTypes, useSkills } from '@/api/queries'
import {
  useCreateNodeType,
  useCreateSkill,
  useDeleteNodeType,
  useDeleteSkill,
  useSaveHandler,
  useSaveNodeType,
  useSaveSkill,
} from '@/api/mutations'
import type { NodeType, SkillDefinition } from '@/api/types'

type Tab = 'function' | 'skills' | 'handlers'

const NEW_FUNCTION = {
  name: 'new-function-node',
  type: 'function',
  role: 'processor',
  handler: 'new-function-node',
  handler_code: 'def run(input_data, parameters, context):\n    return input_data\n',
  input_type: 'Any',
  output_type: 'Any',
  parameters: {},
}

const NEW_SKILL = {
  name: 'new-skill',
  description: '',
  handler: 'new-skill',
  handler_code: 'def run(arguments, context):\n    return arguments\n',
  parameters_schema: { type: 'object', properties: {} },
}

export function NodesPage() {
  const [tab, setTab] = useState<Tab>('function')
  const { data: nodeTypes } = useNodeTypes()
  const { data: skills } = useSkills()
  const { data: handlers } = useHandlers()
  const saveNodeType = useSaveNodeType()
  const createNodeType = useCreateNodeType()
  const deleteNodeType = useDeleteNodeType()
  const saveSkill = useSaveSkill()
  const createSkill = useCreateSkill()
  const deleteSkill = useDeleteSkill()
  const nodes = tab === 'function'
    ? nodeTypes?.types.filter((node) => node.type === tab) ?? []
    : []

  return (
    <main className="h-full overflow-y-auto bg-background p-6">
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">节点管理</h1>
            <p className="text-sm text-muted-foreground">管理 Function 节点和 Skills 注册表。</p>
          </div>
          {tab !== 'handlers' && (
            <button
              onClick={() => {
                if (tab === 'skills') createSkill.mutate(NEW_SKILL)
                else {
                  const payload = { ...NEW_FUNCTION, type: 'function' as const, role: 'processor' as const }
                  createNodeType.mutate(payload)
                }
              }}
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
            >
              创建
            </button>
          )}
        </div>
        <div className="flex gap-2">
          {(['function', 'skills', 'handlers'] as Tab[]).map((item) => (
            <button
              key={item}
              onClick={() => setTab(item)}
              className={`rounded-md border px-3 py-1.5 text-sm ${tab === item ? 'bg-primary text-primary-foreground' : 'bg-card'}`}
            >
              {item === 'function' ? 'Function 节点' : item === 'skills' ? 'Skills' : 'Handler'}
            </button>
          ))}
        </div>

        {tab === 'handlers' ? (
          <div className="grid gap-4 md:grid-cols-2">
            {(handlers?.handlers ?? []).map((h) => (
              <HandlerCard key={h.name} name={h.name} />
            ))}
          </div>
        ) : tab !== 'skills' ? (
          <div className="grid gap-4 md:grid-cols-2">
            {nodes.map((node) => (
              <JsonCard
                key={node.name}
                title={node.name}
                subtitle={`${node.role} · ${node.input_type} -> ${node.output_type}`}
                value={withNodeCodeFields(node)}
                onSave={(next) => saveNodeType.mutate({ name: node.name, body: next as Partial<NodeType> & Record<string, unknown> })}
                onDelete={() => deleteNodeType.mutate(node.name)}
              />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {(skills?.skills ?? []).map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                onSave={(next) => saveSkill.mutate({ name: skill.name, body: next as Partial<SkillDefinition> & Record<string, unknown> })}
                onDelete={() => deleteSkill.mutate(skill.name)}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  )
}

function SkillCard({
  skill,
  onSave,
  onDelete,
}: {
  skill: SkillDefinition
  onSave: (value: Record<string, unknown>) => void
  onDelete: () => void
}) {
  const readonly = (skill.files?.length ?? 0) > 1
  return (
    <JsonCard
      title={skill.name}
      subtitle={skill.handler || skill.description}
      value={{ ...skill, handler_code: '' }}
      onSave={onSave}
      onDelete={onDelete}
      readonly={readonly}
      notice={readonly ? '此 skill 包含多个文件，请使用 CLI 管理' : undefined}
    />
  )
}

function HandlerCard({ name }: { name: string }) {
  const [handlerCode, setHandlerCode] = useState('')
  const handler = useHandler(name)
  const saveHandler = useSaveHandler()
  const saveCode = (code: string) => saveHandler.mutate({ name, code })

  useEffect(() => {
    setHandlerCode(handler.data?.code ?? '')
  }, [handler.data?.code])

  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm">
      <div>
        <h2 className="font-medium">{name}</h2>
      </div>
      <div className="mt-3 space-y-2">
        {handler.isLoading ? (
          <div className="min-h-56 rounded-md border bg-background p-3 text-xs text-muted-foreground">加载中...</div>
        ) : (
          <textarea
            className="min-h-56 w-full rounded-md border bg-background p-3 font-mono text-xs"
            value={handlerCode}
            onChange={(event) => setHandlerCode(event.target.value)}
            onBlur={() => saveCode(handlerCode)}
          />
        )}
        <button
          type="button"
          disabled={saveHandler.isPending || !handler.data}
          onClick={() => saveCode(handlerCode)}
          className="rounded-md border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
        >
          {saveHandler.isPending ? '保存中...' : '保存 Handler'}
        </button>
      </div>
    </section>
  )
}

function NodeCardHeader({ title, subtitle, onDelete }: { title: string; subtitle: ReactNode; onDelete: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="font-medium">{title}</h2>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
      <button onClick={onDelete} className="rounded-md border px-2 py-1 text-xs text-destructive">
        删除
      </button>
    </div>
  )
}

function JsonCard({
  title,
  subtitle,
  value,
  onSave,
  onDelete,
  readonly = false,
  notice,
}: {
  title: string
  subtitle: string
  value: Record<string, unknown>
  onSave: (value: Record<string, unknown>) => void
  onDelete: () => void
  readonly?: boolean
  notice?: string
}) {
  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm">
      <NodeCardHeader title={title} subtitle={subtitle} onDelete={onDelete} />
      {notice && <p className="mt-3 rounded-md border bg-muted px-3 py-2 text-xs text-muted-foreground">{notice}</p>}
      <textarea
        className="mt-3 min-h-56 w-full rounded-md border bg-background p-3 font-mono text-xs"
        defaultValue={JSON.stringify(value, null, 2)}
        readOnly={readonly}
        onBlur={(event) => {
          if (!readonly) onSave(JSON.parse(event.target.value) as Record<string, unknown>)
        }}
      />
    </section>
  )
}

function withNodeCodeFields(node: NodeType): Record<string, unknown> {
  return withoutHandlerCode(node)
}

function withoutHandlerCode(node: NodeType): Record<string, unknown> {
  const { handler_code: _handlerCode, ...rest } = node as NodeType & { handler_code?: unknown }
  return rest
}
