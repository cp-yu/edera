import { useParams, Link } from 'react-router-dom'
import { useAdviceDetail } from '@/api/queries'

export function AdviceDetail() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useAdviceDetail(Number(id) || 0)

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>
  if (!data?.advice) return <div className="p-6 text-muted-foreground">建议不存在</div>

  const advice = data.advice

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <Link to="/results" className="text-xs text-blue-500 hover:underline">&larr; 返回</Link>
      <h1 className="text-xl font-semibold">{advice.stock_name} ({advice.stock_code})</h1>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="rounded-lg border p-3">
          <div className="text-muted-foreground text-xs">方向</div>
          <div className="font-medium">{advice.direction}</div>
        </div>
        <div className="rounded-lg border p-3">
          <div className="text-muted-foreground text-xs">置信度</div>
          <div className="font-medium">{(advice.confidence * 100).toFixed(0)}%</div>
        </div>
        <div className="rounded-lg border p-3">
          <div className="text-muted-foreground text-xs">数据窗口</div>
          <div className="font-medium text-xs">{advice.data_window_start.slice(0, 10)} ~ {advice.data_window_end.slice(0, 10)}</div>
        </div>
      </div>
      <section className="space-y-2">
        <h2 className="text-sm font-medium">理由</h2>
        <p className="text-sm text-muted-foreground">{advice.reason}</p>
      </section>
      {advice.source_urls.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">来源</h2>
          <ul className="text-sm space-y-1">
            {advice.source_urls.map((url, i) => (
              <li key={i}>
                <a href={url} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline break-all">{url}</a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
