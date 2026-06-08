import { useState } from 'react'
import { createPortal } from 'react-dom'
import type { TemporaryInputs } from '@/api/mutations'

interface Props {
  open: boolean
  title: string
  initial?: TemporaryInputs
  onClose: () => void
  onSubmit: (inputs: TemporaryInputs) => void
}

export function TemporaryInputDialog({ open, title, initial, onClose, onSubmit }: Props) {
  const [sourceSharedInputs, setSourceSharedInputs] = useState(jsonText(initial?.sourceSharedInputs ?? {}))
  const [nodeInputs, setNodeInputs] = useState(jsonText(initial?.nodeInputs ?? {}))
  const [appendNodes, setAppendNodes] = useState((initial?.appendNodes ?? []).join(', '))
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const submit = () => {
    try {
      const source = parseObject(sourceSharedInputs, 'sourceSharedInputs')
      const nodes = parseObject(nodeInputs, 'nodeInputs')
      onSubmit({
        sourceSharedInputs: source,
        nodeInputs: nodes,
        appendNodes: appendNodes.split(',').map((item) => item.trim()).filter(Boolean),
      })
      setError(null)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '输入无效')
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-lg border bg-card p-5 shadow-lg" onClick={(event) => event.stopPropagation()}>
        <div className="space-y-4">
          <h2 className="text-sm font-medium">{title}</h2>
          <JsonField label="sourceSharedInputs" value={sourceSharedInputs} onChange={setSourceSharedInputs} />
          <JsonField label="nodeInputs" value={nodeInputs} onChange={setNodeInputs} />
          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">appendNodes</span>
            <input
              value={appendNodes}
              onChange={(event) => setAppendNodes(event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </label>
          {error ? <p className="text-xs text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/50">取消</button>
            <button onClick={submit} className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90">确认</button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function JsonField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-28 w-full resize-y rounded-md border bg-background px-3 py-2 font-mono text-sm"
        spellCheck={false}
      />
    </label>
  )
}

function jsonText(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(value || '{}') as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON object`)
  }
  return parsed as Record<string, unknown>
}
