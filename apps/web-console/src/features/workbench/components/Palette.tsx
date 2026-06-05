import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useDagList, useNodePrototypes } from '@/api/queries'
import type { DagState, NodeType } from '@/api/types'
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

function filterDagCandidates(dags: string[], excludedDagNames: string[]): string[] {
  const excluded = new Set(excludedDagNames)
  return dags.filter((name) => !excluded.has(name)).sort((left, right) => left.localeCompare(right))
}

interface Props {
  dag: DagState | null
  excludedDagNames: string[]
}

function matchesNode(node: NodeType, aliases: string[], query: string): boolean {
  const keyword = query.trim().toLowerCase()
  if (!keyword) return true
  return node.name.toLowerCase().includes(keyword) || aliases.some((alias) => alias.toLowerCase().includes(keyword))
}

export function Palette({ dag, excludedDagNames }: Props) {
  const { data } = useNodePrototypes()
  const dagList = useDagList()
  const prototypes = data?.prototypes ?? []
  const dagCandidates = filterDagCandidates(dagList.data?.dags ?? [], excludedDagNames)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [collapsedRoles, setCollapsedRoles] = useState<Set<string>>(() => new Set())
  const [collapsedPrefixes, setCollapsedPrefixes] = useState<Set<string>>(() => new Set())
  const searchActive = query.trim().length > 0
  const aliasesByType = useMemo(() => {
    const aliases = new Map<string, string[]>()
    for (const node of dag?.nodes ?? []) {
      const typeName = node.type_name ?? node.type
      const alias = node.alias?.trim()
      if (!alias) continue
      const list = aliases.get(typeName) ?? []
      list.push(alias)
      aliases.set(typeName, list)
    }
    return aliases
  }, [dag])
  const grouped = groupPrototypes(prototypes.filter((node) => matchesNode(node, aliasesByType.get(node.name) ?? [], query)))
  const toggle = (current: Set<string>, key: string) => {
    const next = new Set(current)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
  }

  return (
    <aside className="w-[250px] border-r overflow-y-auto p-3 space-y-4 bg-card">
      <h2 className="text-sm font-medium text-muted-foreground">节点面板</h2>
      <label className="relative block">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          aria-label="搜索节点"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-8 w-full rounded-md border bg-background pl-7 pr-2 text-xs outline-none focus:border-primary"
          placeholder="搜索节点"
        />
      </label>
      {grouped.map((group) => (
        <div key={group.role}>
          <button
            type="button"
            aria-expanded={searchActive || !collapsedRoles.has(group.role)}
            onClick={() => setCollapsedRoles((current) => toggle(current, group.role))}
            className="mb-2 flex w-full items-center gap-1 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {searchActive || !collapsedRoles.has(group.role) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {group.label}
          </button>
          {(searchActive || !collapsedRoles.has(group.role)) && <div className="space-y-3">
            {group.prefixes.map((prefixGroup) => (
              <div key={prefixGroup.prefix} className="space-y-1">
                <button
                  type="button"
                  data-palette-prefix
                  aria-expanded={searchActive || !collapsedPrefixes.has(`${group.role}:${prefixGroup.prefix}`)}
                  onClick={() => setCollapsedPrefixes((current) => toggle(current, `${group.role}:${prefixGroup.prefix}`))}
                  className="flex w-full items-center gap-1 text-left text-[11px] font-medium text-muted-foreground hover:text-foreground"
                >
                  {searchActive || !collapsedPrefixes.has(`${group.role}:${prefixGroup.prefix}`)
                    ? <ChevronDown className="h-3 w-3" />
                    : <ChevronRight className="h-3 w-3" />}
                  {prefixGroup.prefix}
                </button>
                {(searchActive || !collapsedPrefixes.has(`${group.role}:${prefixGroup.prefix}`)) && prefixGroup.nodes.map((node) => (
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
          </div>}
        </div>
      ))}
      {dagCandidates.length > 0 ? (
        <div>
          <div className="mb-2 text-xs font-medium text-muted-foreground">DAG 节点</div>
          <div className="space-y-1">
            {dagCandidates
              .filter((name) => name.toLowerCase().includes(query.trim().toLowerCase()))
              .map((name) => (
                <div
                  key={name}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('application/edera-dag', name)
                    e.dataTransfer.effectAllowed = 'move'
                  }}
                  className="rounded-md border px-3 py-2 text-sm cursor-grab hover:bg-accent/50 transition-colors"
                >
                  {name}
                </div>
              ))}
          </div>
        </div>
      ) : null}
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
