import { Link } from 'react-router-dom'
import { useResults } from '@/api/queries'

export function ResultsPage() {
  const { data, isLoading } = useResults()

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>
  if (!data) return <div className="p-6 text-muted-foreground">暂无数据</div>

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-xl font-semibold">结果概览</h1>

      {data.briefing && (
        <section className="rounded-lg border p-4 space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">最新简报</h2>
            <Link to={`/results/briefings/${data.briefing.id}`} className="text-xs text-blue-500 hover:underline">
              详情
            </Link>
          </div>
          <p className="text-sm text-muted-foreground line-clamp-3">{data.briefing.content}</p>
          <p className="text-xs text-muted-foreground">{data.briefing.created_at}</p>
        </section>
      )}

      {data.advices.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">建议</h2>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left">股票</th>
                  <th className="px-4 py-2 text-left">方向</th>
                  <th className="px-4 py-2 text-left">置信度</th>
                  <th className="px-4 py-2 text-left">时间</th>
                </tr>
              </thead>
              <tbody>
                {data.advices.map((advice) => (
                  <tr key={advice.id} className="border-t hover:bg-muted/30">
                    <td className="px-4 py-2">
                      <Link to={`/results/advices/${advice.id}`} className="text-blue-500 hover:underline">
                        {advice.stock_code}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{advice.direction}</td>
                    <td className="px-4 py-2">{(advice.confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 text-muted-foreground">{advice.created_at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data.events.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">事件</h2>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left">股票</th>
                  <th className="px-4 py-2 text-left">标题</th>
                  <th className="px-4 py-2 text-left">热度</th>
                  <th className="px-4 py-2 text-left">状态</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <tr key={event.id} className="border-t hover:bg-muted/30">
                    <td className="px-4 py-2">{event.stock_code}</td>
                    <td className="px-4 py-2">{event.title}</td>
                    <td className="px-4 py-2">{event.heat_score}</td>
                    <td className="px-4 py-2 text-muted-foreground">{event.status}</td>
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
