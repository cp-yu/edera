import { useAppStore } from '@/store/useAppStore'
import { useDag } from '@/api/queries'
import { entityColor } from '@/lib/colors'

export function EntityFilter() {
  const { selectedDagName, entityFilter, setEntityFilter } = useAppStore()
  const { data: dag } = useDag(selectedDagName)
  const entities = dag?.entities ?? []

  if (entities.length === 0) return null

  const toggle = (ref: string) => {
    setEntityFilter(
      entityFilter.includes(ref) ? entityFilter.filter((item) => item !== ref) : [...entityFilter, ref],
    )
  }

  return (
    <div className="flex items-center gap-1">
      {entities.map((entity) => {
        const active = entityFilter.includes(entity.ref)
        return (
          <button
            key={entity.ref}
            onClick={() => toggle(entity.ref)}
            title={entity.display}
            className="rounded px-2 py-0.5 text-xs border transition-colors"
            style={{
              borderColor: entityColor(entity.ref),
              backgroundColor: active ? entityColor(entity.ref) : 'transparent',
              color: active ? '#fff' : undefined,
              opacity: active ? 1 : 0.6,
            }}
          >
            {entity.display.length > 10 ? entity.display.slice(0, 10) + '...' : entity.display}
          </button>
        )
      })}
      {entityFilter.length > 0 && (
        <button
          onClick={() => setEntityFilter([])}
          className="text-xs text-muted-foreground hover:text-foreground ml-1"
        >
          清除
        </button>
      )}
    </div>
  )
}
