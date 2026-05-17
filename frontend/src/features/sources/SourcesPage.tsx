import { useSourcesHealth, useSourceLogs } from '@/api/queries'

export function SourcesPage() {
  const { data: healthData, isLoading } = useSourcesHealth()
  const { data: logsData } = useSourceLogs()

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>

  const sources = healthData?.sources ?? []
  const logs = logsData?.logs ?? []

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-xl font-semibold">信息源健康</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources.map((source) => (
          <div key={source.source_name} className="rounded-lg border p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{source.source_name}</span>
              <StatusBadge status={source.latest_status} />
            </div>
            <div className="text-xs text-muted-foreground space-y-1">
              {source.success_rate !== null && (
                <div>成功率: {(source.success_rate * 100).toFixed(0)}% ({source.window_size}次)</div>
              )}
              {source.latest_failure_reason && (
                <div className="text-red-500">失败: {source.latest_failure_reason}</div>
              )}
              {source.escalated && (
                <div className="text-orange-500">已升级: {source.escalation_reason}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {logs.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">执行日志</h2>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left">信息源</th>
                  <th className="px-4 py-2 text-left">状态</th>
                  <th className="px-4 py-2 text-left">时间</th>
                  <th className="px-4 py-2 text-left">错误</th>
                </tr>
              </thead>
              <tbody>
                {logs.slice(0, 20).map((log, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-4 py-2">{log.source_name}</td>
                    <td className="px-4 py-2">{log.node_status}</td>
                    <td className="px-4 py-2 text-muted-foreground">{log.started_at?.slice(0, 19)}</td>
                    <td className="px-4 py-2 text-red-500 text-xs">{log.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    succeeded: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    running: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    unknown: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${colors[status] ?? colors.unknown}`}>
      {status}
    </span>
  )
}
