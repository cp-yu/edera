import { useState } from 'react'
import { useNodePrototypes } from '@/api/queries'
import { NewFetcherSheet } from './NewFetcherSheet'

export function Palette() {
  const { data } = useNodePrototypes()
  const prototypes = data?.prototypes ?? []
  const [sheetOpen, setSheetOpen] = useState(false)

  const grouped = prototypes.reduce<Record<string, typeof prototypes>>((acc, node) => {
    const group = node.role === 'source' ? 'Source 节点' : node.role === 'sink' ? 'Sink 节点' : 'Processor 节点'
    ;(acc[group] ??= []).push(node)
    return acc
  }, {})

  return (
    <aside className="w-[250px] border-r overflow-y-auto p-3 space-y-4 bg-card">
      <h2 className="text-sm font-medium text-muted-foreground">节点面板</h2>
      {Object.entries(grouped).map(([group, nodes]) => (
        <div key={group}>
          <h3 className="text-xs font-medium text-muted-foreground mb-2">{group}</h3>
          <div className="space-y-1">
            {nodes.map((node) => (
              <div
                key={node.name}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/reactflow', node.name)
                  e.dataTransfer.effectAllowed = 'move'
                }}
                className="rounded-md border px-3 py-2 text-sm cursor-grab hover:bg-accent/50 transition-colors"
              >
                {node.name}
              </div>
            ))}
          </div>
        </div>
      ))}
      <button
        onClick={() => setSheetOpen(true)}
        className="w-full rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground hover:bg-accent/50 transition-colors"
      >
        + New Fetcher
      </button>
      <NewFetcherSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />
    </aside>
  )
}
