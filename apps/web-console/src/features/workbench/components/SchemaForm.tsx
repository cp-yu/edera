import { useEffect, useState } from 'react'
import type { InspectorSchema, InspectorSchemaProperty } from '@/api/types'

interface Props {
  schema: InspectorSchema
  values: Record<string, unknown>
  defaults: Record<string, unknown>
  onChange: (name: string, value: unknown | undefined) => void
}

export function SchemaForm({ schema, values, defaults, onChange }: Props) {
  const properties = schema.properties ?? {}

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([name, property]) => (
        <FieldRow
          key={name}
          name={name}
          property={property}
          value={values[name]}
          defaultValue={defaults[name]}
          onChange={onChange}
        />
      ))}
    </div>
  )
}

function FieldRow({
  name,
  property,
  value,
  defaultValue,
  onChange,
}: {
  name: string
  property: InspectorSchemaProperty
  value: unknown
  defaultValue: unknown
  onChange: (name: string, value: unknown | undefined) => void
}) {
  const label = formatLabel(name)
  const hasOverride = value !== undefined
  const hint = formatDefault(defaultValue)

  if (property.type === 'string' && Array.isArray(property.enum)) {
    return (
      <div className="space-y-1">
        <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(name, event.target.value || undefined)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">{hint ? `使用默认值: ${hint}` : '未设置'}</option>
          {property.enum.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
    )
  }

  if (property.type === 'string') {
    return (
      <div className="space-y-1">
        <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
        <input
          value={typeof value === 'string' ? value : ''}
          placeholder={hint ?? ''}
          onChange={(event) => onChange(name, event.target.value || undefined)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>
    )
  }

  if (property.type === 'integer' || property.type === 'number') {
    return (
      <div className="space-y-1">
        <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
        <input
          type="number"
          step={property.type === 'integer' ? '1' : 'any'}
          value={typeof value === 'number' ? String(value) : ''}
          placeholder={hint ?? ''}
          onChange={(event) => {
            const next = event.target.value.trim()
            if (!next) {
              onChange(name, undefined)
              return
            }
            const parsed = property.type === 'integer' ? Number.parseInt(next, 10) : Number(next)
            if (!Number.isNaN(parsed)) onChange(name, parsed)
          }}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>
    )
  }

  if (property.type === 'boolean') {
    const checked = typeof value === 'boolean' ? value : Boolean(defaultValue)
    return (
      <div className="space-y-1">
        <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => onChange(name, event.target.checked)}
          />
          {checked ? '开启' : '关闭'}
        </label>
      </div>
    )
  }

  if (property.type === 'array' && Array.isArray(property.items?.enum)) {
    const selected = Array.isArray(value)
      ? value.map(String)
      : Array.isArray(defaultValue)
        ? defaultValue.map(String)
        : []
    return (
      <div className="space-y-2">
        <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
        <div className="flex flex-wrap gap-2">
          {property.items.enum.map((item) => {
            const active = selected.includes(item)
            return (
              <button
                key={item}
                type="button"
                onClick={() => onChange(name, toggleItem(selected, item))}
                className={`rounded-full border px-3 py-1 text-xs ${active ? 'border-primary bg-primary text-primary-foreground' : 'bg-card'}`}
              >
                {item}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <JsonField
      name={name}
      label={label}
      value={value}
      defaultValue={defaultValue}
      hasOverride={hasOverride}
      onChange={onChange}
    />
  )
}

function JsonField({
  name,
  label,
  value,
  defaultValue,
  hasOverride,
  onChange,
}: {
  name: string
  label: string
  value: unknown
  defaultValue: unknown
  hasOverride: boolean
  onChange: (name: string, value: unknown | undefined) => void
}) {
  const [text, setText] = useState<string>('')
  const [error, setError] = useState<string>('')
  const hint = formatDefault(defaultValue)

  useEffect(() => {
    setText(value === undefined ? '' : JSON.stringify(value, null, 2))
    setError('')
  }, [value])

  return (
    <div className="space-y-1">
      <Header label={label} hint={hint} hasOverride={hasOverride} onReset={() => onChange(name, undefined)} />
      <textarea
        value={text}
        placeholder={hint ?? ''}
        onChange={(event) => {
          const next = event.target.value
          setText(next)
          if (!next.trim()) {
            setError('')
            onChange(name, undefined)
            return
          }
          try {
            onChange(name, JSON.parse(next))
            setError('')
          } catch {
            setError('需要合法 JSON')
          }
        }}
        className="min-h-28 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

function Header({
  label,
  hint,
  hasOverride,
  onReset,
}: {
  label: string
  hint: string | null
  hasOverride: boolean
  onReset: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <label className="block text-xs text-muted-foreground">{label}</label>
        {hint && <p className="text-[11px] text-muted-foreground">默认值: {hint}</p>}
      </div>
      {hasOverride && (
        <button type="button" onClick={onReset} className="text-xs text-muted-foreground underline underline-offset-2">
          恢复默认
        </button>
      )}
    </div>
  )
}

function toggleItem(items: string[], value: string): string[] {
  return items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
}

function formatLabel(name: string): string {
  return name.replace(/^param\./, '').replaceAll('_', ' ')
}

function formatDefault(value: unknown): string | null {
  if (value === undefined || value === null || value === '') return null
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
