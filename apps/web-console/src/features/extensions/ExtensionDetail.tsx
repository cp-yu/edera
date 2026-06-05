import type { ExtensionDetail as ExtensionDetailData } from '@/api/types'

export type UninstallStrategy = 'purge' | 'keep-modified' | 'deactivate'

export function ExtensionDetail({
  detail,
  onClose,
}: {
  detail: ExtensionDetailData
  onClose: () => void
}) {
  const manifest = detail.manifest
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-lg border bg-background p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">{manifest.name}</h2>
          <button type="button" onClick={onClose} className="h-8 w-8 rounded border text-sm hover:bg-muted">x</button>
        </div>
        <dl className="grid grid-cols-[120px_1fr] gap-3 text-sm">
          <dt className="text-muted-foreground">版本</dt>
          <dd>{manifest.version}</dd>
          <dt className="text-muted-foreground">描述</dt>
          <dd>{manifest.description ?? '-'}</dd>
          <dt className="text-muted-foreground">依赖</dt>
          <dd>{(manifest.depends ?? []).join(', ') || '-'}</dd>
          <dt className="text-muted-foreground">Handlers</dt>
          <dd>{(manifest.handlers ?? []).map((item) => item.name).join(', ') || '-'}</dd>
          <dt className="text-muted-foreground">Entity Types</dt>
          <dd>{(manifest.entity_types ?? []).map((item) => item.name).join(', ') || '-'}</dd>
          <dt className="text-muted-foreground">Imports</dt>
          <dd>{(manifest.imports?.entities ?? []).join(', ') || '-'}</dd>
          <dt className="text-muted-foreground">Import Records</dt>
          <dd>{(detail.import_records ?? []).map((item) => `${item.entity_ref ?? item.import_path}:${item.status}`).join(', ') || '-'}</dd>
        </dl>
      </div>
    </div>
  )
}

export function UninstallDialog({
  name,
  onClose,
  onConfirm,
}: {
  name: string
  onClose: () => void
  onConfirm: (strategy: UninstallStrategy) => void
}) {
  const strategies: { value: UninstallStrategy; label: string }[] = [
    { value: 'deactivate', label: '停用' },
    { value: 'keep-modified', label: '保留修改' },
    { value: 'purge', label: '清除' },
  ]
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg border bg-background p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">卸载 {name}</h2>
          <button type="button" onClick={onClose} className="h-8 w-8 rounded border text-sm hover:bg-muted">x</button>
        </div>
        <div className="grid gap-2">
          {strategies.map((strategy) => (
            <button
              key={strategy.value}
              type="button"
              onClick={() => onConfirm(strategy.value)}
              className="h-10 rounded border px-3 text-left text-sm hover:bg-muted"
            >
              {strategy.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
