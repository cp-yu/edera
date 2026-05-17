import { useAppStore } from '@/store/useAppStore'
import { useDag } from '@/api/queries'
import { targetColor } from '@/lib/colors'

export function TargetFilter() {
  const { selectedDagName, targetFilter, setTargetFilter } = useAppStore()
  const { data: dag } = useDag(selectedDagName)

  const allTargets = Array.from(
    new Set(dag?.nodes.flatMap((n) => n.source_names ?? []) ?? []),
  ).sort()

  if (allTargets.length === 0) return null

  const toggle = (t: string) => {
    setTargetFilter(
      targetFilter.includes(t) ? targetFilter.filter((x) => x !== t) : [...targetFilter, t],
    )
  }

  return (
    <div className="flex items-center gap-1">
      {allTargets.map((t) => {
        const active = targetFilter.includes(t)
        return (
          <button
            key={t}
            onClick={() => toggle(t)}
            title={t}
            className="rounded px-2 py-0.5 text-xs border transition-colors"
            style={{
              borderColor: targetColor(t),
              backgroundColor: active ? targetColor(t) : 'transparent',
              color: active ? '#fff' : undefined,
              opacity: active ? 1 : 0.6,
            }}
          >
            {t.length > 10 ? t.slice(0, 10) + '…' : t}
          </button>
        )
      })}
      {targetFilter.length > 0 && (
        <button
          onClick={() => setTargetFilter([])}
          className="text-xs text-muted-foreground hover:text-foreground ml-1"
        >
          清除
        </button>
      )}
    </div>
  )
}
