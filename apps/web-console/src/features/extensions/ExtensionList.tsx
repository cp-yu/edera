import type { ExtensionSummary } from '@/api/types'

export function ExtensionList({
  title,
  items,
  actionLabel,
  onAction,
  onSelect,
  disabled,
}: {
  title: string
  items: ExtensionSummary[]
  actionLabel: string
  onAction: (name: string) => void
  onSelect: (name: string) => void
  disabled?: boolean
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">{title}</h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">版本</th>
              <th className="px-4 py-2 text-left">状态</th>
              <th className="w-28 px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.name} className="border-t">
                <td className="px-4 py-2 font-medium">
                  <button type="button" onClick={() => onSelect(item.name)} className="hover:underline">
                    {item.name}
                  </button>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{item.version}</td>
                <td className="px-4 py-2">
                  {typeof item.enabled === 'boolean' ? (item.enabled ? '启用' : '停用') : '可安装'}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onAction(item.name)}
                    className="h-8 w-20 rounded border text-xs hover:bg-muted disabled:opacity-50"
                  >
                    {actionLabel}
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm text-muted-foreground">暂无扩展</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
