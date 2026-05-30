import { useState } from 'react'
import { useNodePrototypes } from '@/api/queries'
import type { NodeType } from '@/api/types'
import { NewFetcherSheet } from './NewFetcherSheet'

const ROLE_LABELS = {
  source: 'Source 节点',
  processor: 'Processor 节点',
  sink: 'Sink 节点',
} as const

const ROLE_ORDER = ['source', 'processor', 'sink'] as const

function prefixOf(name: string): string {
  const parts = name.split('-').filter(Boolean)
  if (parts[0] === 'uzi' && parts.length >= 2) return `${parts[0]}-${parts[1]}`
  return parts[0] ?? name
}

function groupPrototypes(prototypes: NodeType[]) {
  const grouped = new Map<NodeType['role'], Map<string, NodeType[]>>()

  for (const node of prototypes) {
    const roleGroup = grouped.get(node.role) ?? new Map<string, NodeType[]>()
    const prefix = prefixOf(node.name)
    const nodes = roleGroup.get(prefix) ?? []
    nodes.push(node)
    roleGroup.set(prefix, nodes)
    grouped.set(node.role, roleGroup)
  }

  return ROLE_ORDER.flatMap((role) => {
    const roleGroup = grouped.get(role)
    if (!roleGroup) return []
    return [{
      role,
      label: ROLE_LABELS[role],
      prefixes: Array.from(roleGroup.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([prefix, nodes]) => ({
          prefix,
          nodes: nodes.slice().sort((left, right) => left.name.localeCompare(right.name)),
        })),
    }]
  })
}

export function Palette() {
  const { data } = useNodePrototypes()
  const prototypes = data?.prototypes ?? []
  const [sheetOpen, setSheetOpen] = useState(false)
  const grouped = groupPrototypes(prototypes)

  return (
    <aside className="w-[250px] border-r overflow-y-auto p-3 space-y-4 bg-card">
      <h2 className="text-sm font-medium text-muted-foreground">节点面板</h2>
      {grouped.map((group) => (
        <div key={group.role}>
          <h3 className="text-xs font-medium text-muted-foreground mb-2">{group.label}</h3>
          <div className="space-y-3">
            {group.prefixes.map((prefixGroup) => (
              <div key={prefixGroup.prefix} className="space-y-1">
                <div data-palette-prefix className="text-[11px] font-medium text-muted-foreground">
                  {prefixGroup.prefix}
                </div>
                {prefixGroup.nodes.map((node) => (
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
