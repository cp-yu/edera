import { useState } from 'react'
import { useCreateNode } from '@/api/mutations'
import { useAppStore } from '@/store/useAppStore'

interface Props {
  open: boolean
  onClose: () => void
}

const SKELETONS = [
  { label: 'RSS Fetcher', type: 'rss_fetcher', input_type: 'rss_feed', output_type: 'raw_item' },
  { label: 'Web Fetcher', type: 'web_fetcher', input_type: 'url', output_type: 'raw_item' },
] as const

export function NewFetcherSheet({ open, onClose }: Props) {
  const [name, setName] = useState('')
  const [skeleton, setSkeleton] = useState<(typeof SKELETONS)[number]>(SKELETONS[0])
  const createNode = useCreateNode()
  const { selectedDagName } = useAppStore()

  if (!open) return null

  const handleCreate = () => {
    if (!name.trim()) return
    createNode.mutate(
      { dagName: selectedDagName, body: { name: name.trim(), type: skeleton.type, input_type: skeleton.input_type, output_type: skeleton.output_type, skills: [], source_names: [] } },
      { onSuccess: () => { setName(''); onClose() } },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="w-[320px] h-full bg-card border-l shadow-lg p-4 space-y-4 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">新建 Fetcher</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg">&times;</button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              placeholder="my_fetcher"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">类型</label>
            <div className="space-y-1">
              {SKELETONS.map((s) => (
                <label key={s.type} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    checked={skeleton.type === s.type}
                    onChange={() => setSkeleton(s)}
                    className="accent-primary"
                  />
                  {s.label}
                </label>
              ))}
            </div>
          </div>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || createNode.isPending}
            className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {createNode.isPending ? '创建中...' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
