import { useParams, Link } from 'react-router-dom'
import { useBriefingDetail } from '@/api/queries'

export function BriefingDetail() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useBriefingDetail(id)

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>
  if (!data?.briefing) return <div className="p-6 text-muted-foreground">简报不存在</div>

  const briefing = data.briefing

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <Link to="/results" className="text-xs text-blue-500 hover:underline">&larr; 返回</Link>
      <h1 className="text-xl font-semibold">简报 {briefing.run_id}</h1>
      <p className="text-xs text-muted-foreground">{briefing.created_at}</p>
      <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-sm">
        {briefing.content}
      </div>
    </div>
  )
}
