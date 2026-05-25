import { cn } from '@/lib/utils'
import type { ContextMenuState } from '../lib/graph'

interface MenuAction {
  label: string
  tone?: 'default' | 'danger'
  disabled?: boolean
  tooltip?: string
  onSelect: () => void
}

interface Props {
  menu: ContextMenuState | null
  actions: MenuAction[]
  onClose: () => void
}

export function CanvasContextMenu({ menu, actions, onClose }: Props) {
  if (!menu) return null

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 min-w-44 overflow-hidden rounded-lg border bg-card/95 p-1 shadow-xl backdrop-blur"
        style={{ left: menu.x, top: menu.y }}
      >
        {actions.map((action) => (
          <button
            key={action.label}
            disabled={action.disabled}
            title={action.tooltip}
            onClick={() => {
              if (action.disabled) return
              action.onSelect()
              onClose()
            }}
            className={cn(
              'flex w-full items-center rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent/50',
              action.tone === 'danger' && 'text-red-600 hover:bg-red-500/10',
              action.disabled && 'cursor-not-allowed opacity-45 hover:bg-transparent',
            )}
          >
            {action.label}
          </button>
        ))}
      </div>
    </>
  )
}
