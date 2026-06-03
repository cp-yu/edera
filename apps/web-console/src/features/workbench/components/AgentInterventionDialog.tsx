import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNodeResume, useNodeStatus, useNodeStop, useRuntimeStatus } from '@/api/queries'

interface Props {
  open: boolean
  nodeId: string
  nodeLabel: string
  initialStatus?: string
  onClose: () => void
}

export function AgentInterventionDialog({ open, nodeId, nodeLabel, initialStatus, onClose }: Props) {
  const [prompt, setPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const status = useNodeStatus(open ? nodeId : null)
  const runtime = useRuntimeStatus(open)
  const refetchStatus = status.refetch
  const refetchRuntime = runtime.refetch
  const stopNode = useNodeStop(nodeId)
  const resumeNode = useNodeResume(nodeId)
  const runtimeStatus = runtime.data?.node_statuses?.[nodeId]
  const currentStatus = status.data?.status ?? runtimeStatus?.status ?? initialStatus ?? '-'
  const runId = runtimeStatus?.run_id
  const pending = submitting || stopNode.isPending || resumeNode.isPending
  const canSubmit = !!prompt.trim() && !!runId && !pending

  useEffect(() => {
    if (!open) return
    const source = new EventSource(`/api/events/node/${nodeId}`)
    const refetch = () => {
      void refetchStatus()
      void refetchRuntime()
    }
    source.addEventListener('node.stdout', refetch)
    source.addEventListener('dag.status', refetch)
    source.addEventListener('node.status', refetch)
    return () => source.close()
  }, [nodeId, open, refetchRuntime, refetchStatus])

  if (!open) return null

  const handleSubmit = async () => {
    const text = prompt.trim()
    if (!text || !runId || pending) return

    setSubmitting(true)
    setError(null)
    try {
      if (currentStatus === 'running') {
        await stopNode.mutateAsync()
      }
      await resumeNode.mutateAsync({ runId, prompt: text })
      setPrompt('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="w-full max-w-[440px] rounded-lg border bg-card p-5 shadow-lg" onClick={(event) => event.stopPropagation()}>
        <div className="space-y-4">
          <div>
            <h2 className="text-sm font-medium">Agent 交互</h2>
            <p className="mt-1 text-xs text-muted-foreground">{nodeLabel}</p>
          </div>
          <div className="grid grid-cols-[64px_1fr] gap-2 rounded-md border bg-muted/20 p-3 text-xs">
            <span className="text-muted-foreground">状态</span>
            <span>{currentStatus}</span>
            <span className="text-muted-foreground">run</span>
            <span className="break-all">{runId ?? '-'}</span>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Prompt</label>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              className="min-h-28 w-full resize-y rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="输入干预内容"
              disabled={pending}
            />
          </div>
          {error ? <p className="text-xs text-red-500">{error}</p> : null}
          {!runId ? <p className="text-xs text-muted-foreground">缺少可续跑的 run_id</p> : null}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/50" disabled={pending}>
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {pending ? '提交中...' : currentStatus === 'running' ? '中断并发送' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
