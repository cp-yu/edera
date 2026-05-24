import { useState } from 'react'
import { useCreateSource } from '@/api/mutations'

interface Props {
  open: boolean
  onClose: () => void
  fetcherName: string
}

export function NewSourceDialog({ open, onClose, fetcherName }: Props) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const createSource = useCreateSource()

  if (!open) return null

  const handleCreate = () => {
    if (!name.trim() || !url.trim()) return
    createSource.mutate(
      { name: name.trim(), url: url.trim(), fetcherName },
      { onSuccess: () => { setName(''); setUrl(''); onClose() } },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-[400px] rounded-lg bg-card border shadow-lg p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-medium">新建信息源</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              placeholder="source_name"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              placeholder="https://..."
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent/50">取消</button>
            <button
              onClick={handleCreate}
              disabled={!name.trim() || !url.trim() || createSource.isPending}
              className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createSource.isPending ? '创建中...' : '创建'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
