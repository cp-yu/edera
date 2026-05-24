import { useAppStore } from '@/store/useAppStore'
import { useRunDag, useStopDag } from '@/api/mutations'
import { EntityFilter } from './EntityFilter'
import type { DagStatus } from '@/api/types'

interface Props {
  dagStatus: DagStatus | null
  isRunning: boolean
}

export function BottomToolbar({ dagStatus, isRunning }: Props) {
  const { selectedDagName, setSelectedDag } = useAppStore()
  const runDag = useRunDag()
  const stopDag = useStopDag()

  return (
    <div className="flex h-10 items-center gap-3 border-t px-4 bg-card text-sm">
      <select
        value={selectedDagName}
        onChange={(e) => setSelectedDag(e.target.value)}
        className="rounded border bg-background px-2 py-1 text-sm"
      >
        <option value="default">default</option>
      </select>

      {isRunning ? (
        <button
          onClick={() => stopDag.mutate(selectedDagName)}
          className="rounded bg-destructive px-3 py-1 text-destructive-foreground text-xs"
        >
          停止
        </button>
      ) : (
        <button
          onClick={() => runDag.mutate(selectedDagName)}
          className="rounded bg-primary px-3 py-1 text-primary-foreground text-xs"
        >
          运行
        </button>
      )}

      {dagStatus && (
        <span className="text-muted-foreground text-xs">
          {isRunning ? `运行中: ${dagStatus.current_cycle_id}` : '空闲'}
        </span>
      )}

      <div className="ml-auto">
        <EntityFilter />
      </div>
    </div>
  )
}
