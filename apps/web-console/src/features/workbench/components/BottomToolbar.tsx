import { useState } from 'react'
import { Settings2 } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { useDagList } from '@/api/queries'
import { useCreateDag, useRunDag, useStopDag, type TemporaryInputs } from '@/api/mutations'
import { EntityFilter } from './EntityFilter'
import { TemporaryInputDialog } from '@/components/TemporaryInputDialog'
import type { DagState, DagStatus } from '@/api/types'

interface Props {
  dag: DagState | null
  dagStatus: DagStatus | null
  isRunning: boolean
}

export function BottomToolbar({ dag, dagStatus, isRunning }: Props) {
  const { selectedDagName, setSelectedDag } = useAppStore()
  const runDag = useRunDag()
  const stopDag = useStopDag()
  const createDag = useCreateDag()
  const dagList = useDagList()
  const [creating, setCreating] = useState(false)
  const [newDagName, setNewDagName] = useState('')
  const [temporaryInputs, setTemporaryInputs] = useState<TemporaryInputs>({})
  const [temporaryDialogOpen, setTemporaryDialogOpen] = useState(false)
  const dagOptions = Array.from(new Set([...(dagList.data?.dags ?? ['default']), selectedDagName, dag?.name].filter(Boolean) as string[]))
  const submitCreate = () => {
    const name = newDagName.trim()
    if (!name) return
    createDag.mutate(name, {
      onSuccess: () => {
        setSelectedDag(name)
        setNewDagName('')
        setCreating(false)
      },
    })
  }

  return (
    <div className="flex h-10 items-center gap-3 border-t px-4 bg-card text-sm">
      <div className="flex items-center gap-2">
        <select
          value={selectedDagName}
          onChange={(e) => e.target.value === '__new__' ? setCreating(true) : setSelectedDag(e.target.value)}
          className="rounded border bg-background px-2 py-1 text-sm"
        >
          {dagOptions.map((name) => <option key={name} value={name}>{name}</option>)}
          <option value="__new__">+ 新建 DAG</option>
        </select>
        {creating && (
          <div className="flex items-center gap-1">
            <input
              value={newDagName}
              onChange={(event) => setNewDagName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') submitCreate()
                if (event.key === 'Escape') setCreating(false)
              }}
              className="w-36 rounded border bg-background px-2 py-1 text-xs"
              placeholder="weekly-report"
            />
            <button onClick={submitCreate} className="rounded border px-2 py-1 text-xs hover:bg-accent">确认</button>
            <button onClick={() => setCreating(false)} className="rounded border px-2 py-1 text-xs hover:bg-accent">取消</button>
          </div>
        )}
      </div>

      {isRunning ? (
        <button
          onClick={() => stopDag.mutate({ dagName: selectedDagName })}
          className="rounded bg-destructive px-3 py-1 text-destructive-foreground text-xs"
        >
          停止
        </button>
      ) : (
        <div className="flex items-center gap-1">
          <button
            onClick={() => runDag.mutate({ dagName: selectedDagName, temporaryInputs })}
            className="rounded bg-primary px-3 py-1 text-primary-foreground text-xs"
          >
            运行
          </button>
          <button
            type="button"
            title="临时输入"
            onClick={() => setTemporaryDialogOpen(true)}
            className="flex h-7 w-7 items-center justify-center rounded border hover:bg-accent"
          >
            <Settings2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {dagStatus && (
        <span className="text-muted-foreground text-xs">
          {isRunning ? `运行中: ${dagStatus.current_run_id}` : '空闲'}
        </span>
      )}

      <div className="ml-auto">
        <EntityFilter />
      </div>

      <TemporaryInputDialog
        open={temporaryDialogOpen}
        title="运行临时输入"
        initial={temporaryInputs}
        onClose={() => setTemporaryDialogOpen(false)}
        onSubmit={setTemporaryInputs}
      />
    </div>
  )
}
