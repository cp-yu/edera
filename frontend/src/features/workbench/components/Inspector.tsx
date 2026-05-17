import { useAppStore } from '@/store/useAppStore'
import { useNodePrototypes } from '@/api/queries'
import { useSaveNode } from '@/api/mutations'
import { useState, useEffect } from 'react'
import { NewSourceDialog } from './NewSourceDialog'

export function Inspector() {
  const { selectedNodeId } = useAppStore()
  const { data } = useNodePrototypes()
  const saveNode = useSaveNode()
  const node = data?.prototypes.find((n) => n.name === selectedNodeId)

  const [model, setModel] = useState('')
  const [timeout, setTimeout] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false)

  useEffect(() => {
    if (node) {
      setModel(node.model ?? '')
      setTimeout(String(node.timeout_seconds ?? ''))
    }
  }, [node])

  if (!node) {
    return (
      <aside className="w-[300px] border-l p-4 bg-card">
        <p className="text-sm text-muted-foreground">选择节点查看配置</p>
      </aside>
    )
  }

  const doSave = () => {
    saveNode.mutate({
      name: node.name,
      body: {
        ...node,
        model: model || undefined,
        timeout_seconds: timeout ? Number(timeout) : undefined,
      },
    })
    setConfirmOpen(false)
  }

  return (
    <aside className="w-[300px] border-l p-4 bg-card overflow-y-auto space-y-4">
      <h2 className="text-sm font-medium">{node.name}</h2>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-muted-foreground">类型</label>
          <p className="text-sm">{node.type}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">输入</label>
          <p className="text-sm">{node.input_type}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">输出</label>
          <p className="text-sm">{node.output_type}</p>
        </div>
        {node.skills && node.skills.length > 0 && (
          <div>
            <label className="text-xs text-muted-foreground">Skills</label>
            <p className="text-sm">{node.skills.join(', ')}</p>
          </div>
        )}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">模型</label>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
            placeholder="默认"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">超时 (秒)</label>
          <input
            value={timeout}
            onChange={(e) => setTimeout(e.target.value)}
            type="number"
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
          />
        </div>
        {node.source_names && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-muted-foreground">信息源</label>
              <button
                onClick={() => setSourceDialogOpen(true)}
                className="text-xs text-blue-500 hover:underline"
              >
                + New Input Source
              </button>
            </div>
            <p className="text-sm">{node.source_names.join(', ') || '无'}</p>
          </div>
        )}
        <button
          onClick={() => setConfirmOpen(true)}
          disabled={saveNode.isPending}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saveNode.isPending ? '保存中...' : '保存节点'}
        </button>
      </div>

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setConfirmOpen(false)}>
          <div className="w-[360px] rounded-lg bg-card border shadow-lg p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-medium">确认保存</h3>
            <p className="text-sm text-muted-foreground">
              此节点为全局实例，修改将影响所有引用它的 DAG。确定保存？
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmOpen(false)} className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/50">取消</button>
              <button onClick={doSave} className="rounded-md bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90">确认保存</button>
            </div>
          </div>
        </div>
      )}

      <NewSourceDialog open={sourceDialogOpen} onClose={() => setSourceDialogOpen(false)} fetcherName={node.name} />
    </aside>
  )
}
