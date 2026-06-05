import { ReactFlowProvider } from '@xyflow/react'
import { useAppStore } from '@/store/useAppStore'
import { useChildRun, useDag, useRuntimeStatus, useDagStatus } from '@/api/queries'
import { Canvas } from './components/Canvas'
import { Palette } from './components/Palette'
import { Inspector } from './components/Inspector'
import { BottomToolbar } from './components/BottomToolbar'

export function WorkbenchPage() {
  const { selectedDagName, subDagView } = useAppStore()
  const activeDagName = subDagView?.childDagName ?? selectedDagName
  const rootDag = useDag(selectedDagName)
  const activeDag = useDag(activeDagName)
  const dagStatus = useDagStatus(selectedDagName, !!rootDag.data)
  const isRunning = !!dagStatus.data?.current_run_id
  const childRun = useChildRun(subDagView?.parentRunId, subDagView?.parentNodeId)
  const childRunId = childRun.data?.child_run_id
  const runtime = useRuntimeStatus(subDagView ? Boolean(childRunId) : isRunning, childRunId, !subDagView || Boolean(childRunId))
  const subDagRuntimeEmpty = Boolean(subDagView && (!subDagView.parentRunId || (childRun.data && !childRunId)))

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        <Palette dag={activeDag.data ?? null} rootDagName={selectedDagName} />
        <ReactFlowProvider>
          <div className="flex-1 relative">
            <Canvas
              dagName={activeDagName}
              dag={activeDag.data ?? null}
              dagStatus={dagStatus.data ?? null}
              runtimeStatus={runtime.data ?? null}
              isRunning={isRunning}
            />
          </div>
        </ReactFlowProvider>
        <Inspector
          dagName={activeDagName}
          dag={activeDag.data ?? null}
          runtimeStatus={runtime.data ?? null}
          subDagRuntimeEmpty={subDagRuntimeEmpty}
        />
      </div>
      <BottomToolbar dag={rootDag.data ?? null} dagStatus={dagStatus.data ?? null} isRunning={isRunning} />
    </div>
  )
}
