import { Link } from 'react-router-dom'
import { useResults } from '@/api/queries'
import type { Advice } from '@/api/types'

type SummaryItem = Advice & { degraded?: unknown; direction_label?: unknown }

const directionLabels: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }

export function ResultsPage() {
  const { data, error, isError, isLoading } = useResults()

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>
  if (isError) return <div className="p-6 text-destructive">加载结果失败: {error?.message ?? '未知错误'}</div>
  if (!data) return <div className="p-6 text-muted-foreground">暂无数据</div>

  const summaryItems = data.summary_items.length > 0 ? data.summary_items : data.advices
  const failedSources = Object.entries(data.failed_sources)
  const hasResults =
    !!data.briefing ||
    data.briefings.length > 0 ||
    data.advices.length > 0 ||
    data.events.length > 0 ||
    data.summary_items.length > 0

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-xl font-semibold">结果概览</h1>

      {!hasResults && (
        <section className="rounded-lg border p-4 text-sm text-muted-foreground">
          当前数据库没有可展示结果。
        </section>
      )}

      <section className="rounded-lg border p-4 space-y-3">
        <h2 className="text-sm font-medium">当前周期</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
          <MetadataItem label="Run" value={String(data.metadata_bar.run_id ?? '无')} />
          <MetadataItem label="创建时间" value={String(data.metadata_bar.created_at ?? '') || '无'} />
          <MetadataItem label="数据窗口" value={String(data.metadata_bar.window ?? '无数据窗口')} />
          <MetadataItem label="失败源" value={String(data.metadata_bar.failed_count ?? 0)} />
        </div>
        <p className="text-xs text-muted-foreground">{String(data.metadata_bar.disclaimer ?? '')}</p>
      </section>

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

      {data.briefings.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">历史简报</h2>
          <div className="rounded-lg border divide-y">
            {data.briefings.slice(0, 5).map((briefing) => (
              <Link
                key={briefing.id}
                to={`/results/briefings/${briefing.id}`}
                className="block p-3 text-sm hover:bg-muted/30"
              >
                <div className="font-medium line-clamp-1">{briefing.content}</div>
                <div className="text-xs text-muted-foreground">{briefing.created_at}</div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {summaryItems.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">当前摘要</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {summaryItems.slice(0, 6).map((item, index) => {
              const adviceId = validResultId(item.id)
              const content = <SummaryCardContent item={item} />
              if (!adviceId) {
                return (
                  <div key={summaryItemKey(item, index)} className="rounded-lg border p-3 space-y-1 text-sm">
                    {content}
                    <div className="text-xs text-muted-foreground">详情不可用</div>
                  </div>
                )
              }
              return (
                <Link
                  key={adviceId}
                  to={`/results/advices/${adviceId}`}
                  className="rounded-lg border p-3 space-y-1 text-sm hover:bg-muted/30"
                >
                  {content}
                </Link>
              )
            })}
          </div>
        </section>
      )}

      {failedSources.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">失败源</h2>
          <div className="rounded-lg border divide-y">
            {failedSources.map(([name, reason]) => (
              <div key={name} className="p-3 text-sm">
                <div className="font-medium">{name}</div>
                <div className="text-xs text-red-500">{reason}</div>
              </div>
            ))}
          </div>
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
                {data.advices.map((advice, index) => {
                  const adviceId = validResultId(advice.id)
                  return (
                    <tr key={adviceId ?? summaryItemKey(advice, index)} className="border-t hover:bg-muted/30">
                      <td className="px-4 py-2">
                        {adviceId ? (
                          <Link to={`/results/advices/${adviceId}`} className="text-blue-500 hover:underline">
                            {advice.stock_code}
                          </Link>
                        ) : (
                          <span>{advice.stock_code}</span>
                        )}
                      </td>
                      <td className="px-4 py-2">{advice.direction}</td>
                      <td className="px-4 py-2">{(advice.confidence * 100).toFixed(0)}%</td>
                      <td className="px-4 py-2 text-muted-foreground">{advice.created_at.slice(0, 10)}</td>
                    </tr>
                  )
                })}
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

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium break-words">{value}</div>
    </div>
  )
}

function SummaryCardContent({ item }: { item: SummaryItem }) {
  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{item.stock_code}</span>
        <span className="text-xs text-muted-foreground">{summaryStateLabel(item)}</span>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-2">{item.reason}</p>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>置信度 {(item.confidence * 100).toFixed(0)}%</span>
        <span>{item.created_at.slice(0, 10)}</span>
      </div>
    </>
  )
}

function summaryStateLabel(item: SummaryItem) {
  if (item.low_confidence) return '低置信度'
  if (item.degraded) return '采集降级'
  return String(item.direction_label ?? directionLabels[item.direction] ?? item.direction)
}

function validResultId(value: unknown) {
  if (typeof value !== 'string') return null
  const id = value.trim()
  return id && id !== 'null' && id !== 'undefined' ? id : null
}

function summaryItemKey(item: SummaryItem, index: number) {
  return `${item.stock_code}-${item.created_at}-${index}`
}
