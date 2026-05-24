import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import type { SearchItem } from '../lib/graph'

interface Props {
  open: boolean
  query: string
  onQueryChange: (value: string) => void
  items: SearchItem[]
  onClose: () => void
  onSelect: (name: string) => void
}

export function QuickAddPanel({ open, query, onQueryChange, items, onClose, onSelect }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [cursor, setCursor] = useState(0)

  useEffect(() => {
    if (!open) return
    setCursor(0)
    inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (cursor >= items.length) {
      setCursor(items.length > 0 ? items.length - 1 : 0)
    }
  }, [cursor, items.length])

  if (!open) return null

  const active = items[cursor]
  const groups = [
    { role: 'source', label: 'Sources' },
    { role: 'processor', label: 'Processors' },
    { role: 'sink', label: 'Sinks' },
  ].map((group) => ({ ...group, items: items.filter((item) => item.role === group.role) }))
  let itemIndex = 0

  return (
    <>
      <div className="absolute inset-0 z-40 bg-black/20 backdrop-blur-[1px]" onClick={onClose} />
      <div className="absolute left-1/2 top-8 z-50 w-[min(32rem,calc(100%-2rem))] -translate-x-1/2 overflow-hidden rounded-2xl border bg-card shadow-2xl">
        <div className="border-b px-4 py-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault()
                setCursor((value) => Math.min(value + 1, Math.max(items.length - 1, 0)))
              } else if (event.key === 'ArrowUp') {
                event.preventDefault()
                setCursor((value) => Math.max(value - 1, 0))
              } else if (event.key === 'Enter' && active) {
                event.preventDefault()
                onSelect(active.name)
              } else if (event.key === 'Escape') {
                event.preventDefault()
                onClose()
              }
            }}
            className="w-full bg-transparent text-sm outline-none"
            placeholder="搜索节点并添加到画布中心"
          />
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {items.length === 0 ? (
            <div className="rounded-xl px-3 py-6 text-center text-sm text-muted-foreground">没有匹配节点</div>
          ) : (
            groups.map((group) => group.items.length > 0 && (
              <div key={group.role} className="mb-2">
                <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.label}
                </div>
                {group.items.map((item) => {
                  const index = itemIndex++
                  return (
                    <button
                      key={item.name}
                      onMouseEnter={() => setCursor(index)}
                      onClick={() => onSelect(item.name)}
                      className={cn(
                        'flex w-full items-center justify-between rounded-xl px-3 py-2 text-left transition-colors',
                        index === cursor ? 'bg-accent/60' : 'hover:bg-accent/40',
                      )}
                    >
                      <span className="text-sm font-medium">{item.name}</span>
                      <span className="text-xs text-muted-foreground">{item.kind}</span>
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}
