import { useEffect, useState } from 'react'
import { Handle, Position, type NodeProps, useUpdateNodeInternals } from '@xyflow/react'
import { Bot, CheckCircle2, Clock, Cpu, GitMerge, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getNodeEdgeColor, getRuntimeState, type HandleSpec, type WorkbenchNodeData } from '../../lib/graph'
import { AgentInterventionDialog } from '../AgentInterventionDialog'

const handleBase = {
  width: 12,
  height: 12,
  borderWidth: 2,
  borderColor: 'rgba(255,255,255,0.55)',
  background: 'rgba(15,23,42,0.96)',
} as const

const KIND_ICONS = {
  function: Cpu,
  agent: Bot,
  dag: GitMerge,
  wait: Clock,
  unknown: GitMerge,
} as const

const KIND_STYLES = {
  function: {
    shell: 'border-blue-600/70 bg-slate-950/95 text-slate-50 shadow-blue-950/30',
    header: 'bg-blue-700/90 text-blue-50',
    accent: 'text-blue-200',
  },
  agent: {
    shell: 'border-violet-600/70 bg-slate-950/95 text-slate-50 shadow-violet-950/30',
    header: 'bg-violet-700/90 text-violet-50',
    accent: 'text-violet-200',
  },
  dag: {
    shell: 'border-emerald-600/70 bg-slate-950/95 text-slate-50 shadow-emerald-950/30',
    header: 'bg-emerald-700/90 text-emerald-50',
    accent: 'text-emerald-200',
  },
  wait: {
    shell: 'border-amber-600/70 bg-slate-950/95 text-slate-50 shadow-amber-950/30',
    header: 'bg-amber-700/90 text-amber-50',
    accent: 'text-amber-200',
  },
  unknown: {
    shell: 'border-slate-600/70 bg-slate-950/95 text-slate-50 shadow-slate-950/30',
    header: 'bg-slate-700/90 text-slate-100',
    accent: 'text-slate-300',
  },
} as const

function StatusBadge({ status }: { status?: string }) {
  const runtime = getRuntimeState(status)
  if (!runtime) return null

  const tone =
    runtime === 'running'
      ? 'bg-blue-500 shadow-[0_0_0_4px_rgba(37,99,235,0.18)] animate-pulse'
      : runtime === 'succeeded'
        ? 'bg-emerald-500 shadow-[0_0_0_4px_rgba(22,163,74,0.16)]'
        : runtime === 'failed'
          ? 'bg-red-500 shadow-[0_0_0_4px_rgba(220,38,38,0.16)]'
          : 'bg-slate-400 shadow-[0_0_0_4px_rgba(148,163,184,0.16)]'

  return <span className={cn('absolute left-3 top-3 h-3 w-3 rounded-full', tone)} />
}

function RetryBadge({ active }: { active?: boolean }) {
  if (!active) return null
  return <span className="absolute right-3 top-3 h-3 w-3 animate-pulse rounded-full bg-amber-400 shadow-[0_0_0_4px_rgba(251,191,36,0.2)]" />
}

function SelectionBadge({ active }: { active?: boolean }) {
  if (!active) return null
  return (
    <span className="absolute -right-3 -top-3 z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 border-slate-950 bg-cyan-300 text-slate-950 shadow-[0_0_0_4px_rgba(103,232,249,0.35)]">
      <CheckCircle2 size={16} strokeWidth={2.8} />
    </span>
  )
}

function HandleRail({
  handles,
  position,
  color,
  connectionState,
}: {
  handles: HandleSpec[]
  position: Position.Left | Position.Right
  color: string
  connectionState?: 'valid' | 'invalid'
}) {
  if (handles.length === 0) return null
  const feedbackColor =
    position === Position.Left && connectionState
      ? connectionState === 'valid'
        ? '#16a34a'
        : '#dc2626'
      : color

  return (
    <>
      {handles.map((handle, index) => {
        const top = `${((index + 1) / (handles.length + 1)) * 100}%`
        return (
          <Handle
            key={handle.id}
            id={handle.id}
            type={position === Position.Left ? 'target' : 'source'}
            position={position}
            title={handle.label}
            style={{
              ...handleBase,
              top,
              opacity: handle.connected ? 1 : 0.5,
              [position === Position.Left ? 'left' : 'right']: -7,
              background: feedbackColor,
              boxShadow: `0 0 0 2px ${feedbackColor}`,
            }}
            className="group-hover:!opacity-100 transition-opacity"
          />
        )
      })}
    </>
  )
}

export function CustomNode({ id, data, selected }: NodeProps) {
  const [interventionOpen, setInterventionOpen] = useState(false)
  const updateNodeInternals = useUpdateNodeInternals()
  const node = data as unknown as WorkbenchNodeData
  const kindStyle = KIND_STYLES[node.visualKind]
  const Icon = KIND_ICONS[node.visualKind]
  const edgeColor = getNodeEdgeColor(node.visualKind)
  const title = node.alias || node.type_name
  const canIntervene = node.type === 'agent'

  useEffect(() => {
    updateNodeInternals(id)
  }, [id, node.inputHandles.length, node.outputHandles.length, updateNodeInternals])

  return (
    <div
      className={cn(
        'group relative overflow-visible rounded-2xl border shadow-xl transition-shadow',
        kindStyle.shell,
        selected && 'outline outline-[3px] outline-offset-[5px] outline-cyan-300',
        node.retrying && 'ring-2 ring-amber-300/70',
      )}
    >
      <StatusBadge status={node.status} />
      <RetryBadge active={node.retrying} />
      <SelectionBadge active={selected} />
      <HandleRail
        handles={node.inputHandles}
        position={Position.Left}
        color={edgeColor}
        connectionState={node.connectionState}
      />
      <HandleRail handles={node.outputHandles} position={Position.Right} color={edgeColor} />

      <div className={cn('px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em]', kindStyle.header)}>
        <div className="flex items-center gap-2">
          <Icon size={14} strokeWidth={2.2} />
          <span data-node-type-context className="min-w-0 flex-1 truncate">
            {node.type_name}
          </span>
        </div>
      </div>
      <div className="space-y-3 px-4 py-3">
        <div className="flex items-start gap-2">
          <div data-node-title className="min-w-0 flex-1 pr-2 text-sm font-semibold">
            {title}
          </div>
          {canIntervene ? (
            <button
              type="button"
              title="Agent 交互"
              aria-label="Agent 交互"
              onClick={(event) => {
                event.stopPropagation()
                setInterventionOpen(true)
              }}
              className="nodrag flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              <MessageSquare size={14} strokeWidth={2.2} />
            </button>
          ) : null}
        </div>
        <div className={cn('text-[11px] uppercase tracking-[0.14em]', kindStyle.accent)}>
          {node.input_type || 'none'} {'->'} {node.output_type || 'none'}
        </div>
        {node.entities?.length ? (
          <div className="flex flex-wrap gap-1">
            {node.entities.slice(0, 3).map((entity) => (
              <span
                key={entity}
                className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-200"
              >
                {entity}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {canIntervene ? (
        <AgentInterventionDialog
          open={interventionOpen}
          nodeId={id}
          nodeLabel={title}
          initialStatus={node.status}
          onClose={() => setInterventionOpen(false)}
        />
      ) : null}
    </div>
  )
}
