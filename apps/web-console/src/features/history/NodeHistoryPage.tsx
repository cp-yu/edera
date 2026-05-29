import { useParams } from 'react-router-dom'
import { useNodeHistory } from '@/api/queries'

export function NodeHistoryPage() {
  const { dagName = '', nodeId = '' } = useParams()
  const history = useNodeHistory(dagName, nodeId)
  const items = history.data?.history ?? []

  return (
    <div className="h-full overflow-auto p-6">
      <div className="mb-4">
        <h1 className="text-lg font-semibold">{nodeId}</h1>
        <p className="text-sm text-muted-foreground">{dagName}</p>
      </div>
      <div className="space-y-3">
        {items.length === 0 && (
          <div className="rounded-md border p-4 text-sm text-muted-foreground">暂无历史记录</div>
        )}
        {items.map((item) => (
          <details key={`${item.node_run.run_id}-${item.node_run.id}`} className="rounded-md border bg-card p-4">
            <summary className="cursor-pointer text-sm">
              <span className="font-medium">{item.node_run.status}</span>
              <span className="ml-3 text-muted-foreground">{item.node_run.run_id}</span>
              {item.run.retry_of && <span className="ml-3 text-muted-foreground">retry of {item.run.retry_of}</span>}
            </summary>
            <div className="mt-3 grid gap-2 text-xs">
              <HistoryRow label="started" value={item.node_run.started_at ?? '-'} />
              <HistoryRow label="ended" value={item.node_run.ended_at ?? '-'} />
              {item.node_run.error && <HistoryRow label="error" value={item.node_run.error} />}
              <div className="mt-2 space-y-2">
                {item.outputs.length === 0 ? (
                  <p className="text-muted-foreground">暂无输出</p>
                ) : item.outputs.map((output) => (
                  <pre key={output.id} className="max-h-48 overflow-auto rounded-md bg-muted/40 p-3 text-[11px]">
                    {JSON.stringify(output.attributes.payload ?? output.attributes, null, 2)}
                  </pre>
                ))}
              </div>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}

function HistoryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all">{value}</span>
    </div>
  )
}
