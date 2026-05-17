import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { blendTargetColors } from '@/lib/colors'

const handleBase = { opacity: 0, width: 8, height: 8, transition: 'opacity 0.15s' } as const
const hTop = { ...handleBase, left: '40%' }
const hTopSrc = { ...handleBase, left: '60%' }
const hRight = { ...handleBase, top: '40%' }
const hRightSrc = { ...handleBase, top: '60%' }
const hBottom = { ...handleBase, left: '40%' }
const hBottomSrc = { ...handleBase, left: '60%' }
const hLeft = { ...handleBase, top: '40%' }
const hLeftSrc = { ...handleBase, top: '60%' }

export function CustomNode({ data }: NodeProps) {
  const { name, type, status, source_names } = data as {
    name: string; type: string; status?: string; error?: string; source_names?: string[]
  }

  const statusClass =
    status === 'succeeded' ? 'border-green-500' :
    status === 'failed' ? 'border-red-500' :
    status === 'running' ? 'border-blue-500 animate-pulse' :
    ''

  const targetBorderColor = source_names?.length ? blendTargetColors(source_names) : undefined

  return (
    <div
      className={cn('group rounded-lg border-2 bg-card px-4 py-2 shadow-sm min-w-[120px]', statusClass)}
      style={!statusClass && targetBorderColor ? { borderLeftColor: targetBorderColor, borderLeftWidth: 4 } : undefined}
    >
      <Handle id="top-target" type="target" position={Position.Top} style={hTop} className="group-hover:!opacity-100" />
      <Handle id="top-source" type="source" position={Position.Top} style={hTopSrc} className="group-hover:!opacity-100" />
      <Handle id="right-target" type="target" position={Position.Right} style={hRight} className="group-hover:!opacity-100" />
      <Handle id="right-source" type="source" position={Position.Right} style={hRightSrc} className="group-hover:!opacity-100" />
      <Handle id="bottom-target" type="target" position={Position.Bottom} style={hBottom} className="group-hover:!opacity-100" />
      <Handle id="bottom-source" type="source" position={Position.Bottom} style={hBottomSrc} className="group-hover:!opacity-100" />
      <Handle id="left-target" type="target" position={Position.Left} style={hLeft} className="group-hover:!opacity-100" />
      <Handle id="left-source" type="source" position={Position.Left} style={hLeftSrc} className="group-hover:!opacity-100" />

      <div className="text-sm font-medium">{name}</div>
      <div className="text-xs text-muted-foreground">{type}</div>
    </div>
  )
}

