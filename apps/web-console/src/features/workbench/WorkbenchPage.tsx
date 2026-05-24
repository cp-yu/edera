import { ReactFlowProvider } from '@xyflow/react'
import { useAppStore } from '@/store/useAppStore'
import { useDag, useRuntimeStatus, useDagStatus } from '@/api/queries'
import { Canvas } from './components/Canvas'
import { Palette } from './components/Palette'
import { Inspector } from './components/Inspector'
import { BottomToolbar } from './components/BottomToolbar'

export function WorkbenchPage() {
  const { selectedDagName } = useAppStore()
  const dag = useDag(selectedDagName)
  const dagStatus = useDagStatus(selectedDagName, !!dag.data)
  const isRunning = !!dagStatus.data?.current_cycle_id
  const runtime = useRuntimeStatus(isRunning)

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        <Palette />
        <ReactFlowProvider>
          <div className="flex-1 relative">
            <Canvas
              dag={dag.data ?? null}
              runtimeStatus={runtime.data ?? null}
              isRunning={isRunning}
            />
          </div>
        </ReactFlowProvider>
        <Inspector />
      </div>
      <BottomToolbar dag={dag.data ?? null} dagStatus={dagStatus.data ?? null} isRunning={isRunning} />
    </div>
  )
}
