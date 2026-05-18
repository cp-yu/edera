import { useEffect, useState } from 'react'
import { useDag } from '@/api/queries'
import { useSaveDag } from '@/api/mutations'
import { useAppStore } from '@/store/useAppStore'

export function Inspector() {
  const { selectedDagName, selectedEdgeId, selectedNodeId } = useAppStore()
  const { data: dag } = useDag(selectedDagName)
  const saveDag = useSaveDag(selectedDagName)
  const node = dag?.nodes.find((item) => item.id === selectedNodeId)
  const edge = dag?.edges.find((item, index) => `e-${item.from}-${item.to}-${index}` === selectedEdgeId)
  const [alias, setAlias] = useState('')
  const [model, setModel] = useState('')
  const [skills, setSkills] = useState('')
  const [sourceNames, setSourceNames] = useState('')
  const [parameters, setParameters] = useState('{}')

  useEffect(() => {
    if (!node) return
    setAlias(node.alias ?? '')
    setModel(node.model ?? '')
    setSkills((node.skills ?? []).join(', '))
    setSourceNames((node.source_names ?? []).join(', '))
    setParameters(JSON.stringify(node.parameters ?? {}, null, 2))
  }, [node])

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
    let parsedParameters: Record<string, unknown>
    try {
      parsedParameters = JSON.parse(parameters) as Record<string, unknown>
    } catch {
      window.alert('parameters 必须是 JSON 对象')
      return
    }
    const nodes = dag.nodes.map((item) => {
      if (item.id !== node.id) {
        return { id: item.id, type: item.type_name, alias: item.alias, config: item.config ?? {} }
      }
      const config = {
        ...(item.config ?? {}),
        ...(item.type === 'llm' ? { skills: splitList(skills), model: model || undefined } : {}),
        ...(item.type === 'function' ? { source_names: splitList(sourceNames) } : {}),
        parameters: parsedParameters,
      }
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
      <Readonly label="输入" value={node.input_type} />
      <Readonly label="输出" value={node.output_type} />
      {node.type === 'llm' && <Field label="Model" value={model} onChange={setModel} />}
      {node.type === 'llm' && <Field label="Skills" value={skills} onChange={setSkills} />}
      {node.type === 'function' && <Field label="Source Names" value={sourceNames} onChange={setSourceNames} />}
      <div>
        <label className="mb-1 block text-xs text-muted-foreground">Parameters</label>
        <textarea
          value={parameters}
          onChange={(event) => setParameters(event.target.value)}
          className="min-h-32 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
        />
      </div>
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

function splitList(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}
