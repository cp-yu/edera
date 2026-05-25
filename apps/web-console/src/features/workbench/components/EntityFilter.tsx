import { useMemo, useState } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useDag } from '@/api/queries'
import { entityColor } from '@/lib/colors'
import type { EntityItem } from '@/api/types'

export function EntityFilter() {
  const { selectedDagName, entityFilter, setEntityFilter } = useAppStore()
  const { data: dag } = useDag(selectedDagName)
  const [open, setOpen] = useState(false)
  const entities = dag?.entities ?? []
  const grouped = useMemo(() => groupEntities(entities), [entities])
  const selectedEntities = entities.filter((entity) => entityFilter.includes(entity.ref))
  const summary = selectedEntities.length === 0
    ? '全部实体'
    : selectedEntities.length === 1
      ? selectedEntities[0].display
      : `已选 ${selectedEntities.length} 项`

  if (entities.length === 0) return null

  const toggle = (ref: string) => {
    setEntityFilter(
      entityFilter.includes(ref) ? entityFilter.filter((item) => item !== ref) : [...entityFilter, ref],
    )
  }

  return (
    <div className="relative flex items-center gap-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="workbench-entity-filter-panel"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex min-w-32 max-w-56 items-center gap-1 rounded border bg-background px-2 py-1 text-left text-xs hover:bg-accent"
      >
        <span className="text-muted-foreground">实体过滤: </span>
        <span className="truncate">{summary}</span>
      </button>
      {entityFilter.length > 0 && (
        <button
          onClick={() => setEntityFilter([])}
          className="text-xs text-muted-foreground hover:text-foreground ml-1"
        >
          清除
        </button>
      )}
      {open && (
        <div
          id="workbench-entity-filter-panel"
          className="absolute bottom-9 right-0 z-20 w-72 max-h-80 overflow-y-auto rounded-md border bg-popover p-3 shadow-lg"
        >
          <div className="space-y-3">
            {grouped.map((group) => (
              <div key={group.type} className="space-y-1">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.type}
                </div>
                <div className="flex flex-wrap gap-1">
                  {group.entities.map((entity) => {
                    const active = entityFilter.includes(entity.ref)
                    return (
                      <button
                        key={entity.ref}
                        type="button"
                        onClick={() => toggle(entity.ref)}
                        title={entity.display}
                        className="max-w-full rounded px-2 py-0.5 text-xs border transition-colors"
                        style={{
                          borderColor: entityColor(entity.ref),
                          backgroundColor: active ? entityColor(entity.ref) : 'transparent',
                          color: active ? '#fff' : undefined,
                          opacity: active ? 1 : 0.72,
                        }}
                      >
                        <span className="block max-w-32 truncate">{entity.display}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function groupEntities(entities: EntityItem[]): Array<{ type: string; entities: EntityItem[] }> {
  const groups = entities.reduce<Record<string, EntityItem[]>>((acc, entity) => {
    ;(acc[entity.type] ??= []).push(entity)
    return acc
  }, {})

  return Object.entries(groups)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([type, items]) => ({
      type,
      entities: [...items].sort((left, right) => left.display.localeCompare(right.display)),
    }))
}
