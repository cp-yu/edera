import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { blendTargetColors } from '@/lib/colors'

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
      className={cn('rounded-lg border-2 bg-card px-4 py-2 shadow-sm min-w-[120px]', statusClass)}
      style={!statusClass && targetBorderColor ? { borderLeftColor: targetBorderColor, borderLeftWidth: 4 } : undefined}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="text-sm font-medium">{name}</div>
      <div className="text-xs text-muted-foreground">{type}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  )
}
