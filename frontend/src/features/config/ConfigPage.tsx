import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'

export function ConfigPage() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<'portfolio' | 'system'>('portfolio')

  const portfolio = useQuery({
    queryKey: ['config', 'portfolio'],
    queryFn: () => apiFetch<{ content: string }>('/api/config/portfolio'),
  })

  const system = useQuery({
    queryKey: ['config', 'system'],
    queryFn: () => apiFetch<{ content: string }>('/api/config/system'),
  })

  const [portfolioText, setPortfolioText] = useState<string | null>(null)
  const [systemText, setSystemText] = useState<string | null>(null)

  const portfolioValue = portfolioText ?? portfolio.data?.content ?? ''
  const systemValue = systemText ?? system.data?.content ?? ''

  const savePortfolio = useMutation({
    mutationFn: (content: string) =>
      apiFetch('/api/config/portfolio', { method: 'PUT', body: JSON.stringify({ content }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['config', 'portfolio'] }); setPortfolioText(null) },
  })

  const saveSystem = useMutation({
    mutationFn: (content: string) =>
      apiFetch('/api/config/system', { method: 'PUT', body: JSON.stringify({ content }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['config', 'system'] }); setSystemText(null) },
  })

  const tabs = [
    { key: 'portfolio' as const, label: 'Portfolio' },
    { key: 'system' as const, label: 'System' },
  ]

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <h1 className="text-xl font-semibold">配置</h1>

      <div className="flex gap-1 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              activeTab === tab.key ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'portfolio' && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">Portfolio 配置 (JSON)</p>
          <textarea
            value={portfolioValue}
            onChange={(e) => setPortfolioText(e.target.value)}
            className="w-full h-[400px] rounded-md border bg-background px-3 py-2 text-sm font-mono resize-y"
            spellCheck={false}
          />
          <button
            onClick={() => savePortfolio.mutate(portfolioValue)}
            disabled={savePortfolio.isPending || portfolioText === null}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {savePortfolio.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      )}

      {activeTab === 'system' && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">System 配置</p>
          <textarea
            value={systemValue}
            onChange={(e) => setSystemText(e.target.value)}
            className="w-full h-[400px] rounded-md border bg-background px-3 py-2 text-sm font-mono resize-y"
            spellCheck={false}
          />
          <button
            onClick={() => saveSystem.mutate(systemValue)}
            disabled={saveSystem.isPending || systemText === null}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saveSystem.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      )}
    </div>
  )
}
