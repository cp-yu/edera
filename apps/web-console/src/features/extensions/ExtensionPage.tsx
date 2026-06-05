import { useState } from 'react'
import { useAvailableExtensions, useExtensionDetail, useInstalledExtensions } from '@/api/queries'
import { useInstallExtension, useUninstallExtension } from '@/api/mutations'
import { ExtensionDetail, UninstallDialog, type UninstallStrategy } from './ExtensionDetail'
import { ExtensionList } from './ExtensionList'

export function ExtensionPage() {
  const [uninstallName, setUninstallName] = useState<string | null>(null)
  const [detailName, setDetailName] = useState<string | null>(null)
  const available = useAvailableExtensions()
  const installed = useInstalledExtensions()
  const detail = useExtensionDetail(detailName)
  const install = useInstallExtension()
  const uninstall = useUninstallExtension()

  if (available.isLoading || installed.isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>
  if (available.isError || installed.isError) {
    return <div className="p-6 text-sm text-red-600">加载扩展失败</div>
  }

  const installedNames = new Set((installed.data?.extensions ?? []).map((item) => item.name))
  const availableOnly = (available.data?.extensions ?? []).filter((item) => !installedNames.has(item.name))

  function confirmUninstall(strategy: UninstallStrategy) {
    if (!uninstallName) return
    uninstall.mutate({ name: uninstallName, strategy })
    setUninstallName(null)
  }

  return (
    <div className="max-w-5xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">扩展</h1>
      </div>
      <ExtensionList
        title="已安装"
        items={installed.data?.extensions ?? []}
        actionLabel="卸载"
        disabled={uninstall.isPending}
        onAction={setUninstallName}
        onSelect={setDetailName}
      />
      <ExtensionList
        title="可用"
        items={availableOnly}
        actionLabel="安装"
        disabled={install.isPending}
        onAction={(name) => install.mutate(name)}
        onSelect={setDetailName}
      />
      {uninstallName && (
        <UninstallDialog
          name={uninstallName}
          onClose={() => setUninstallName(null)}
          onConfirm={confirmUninstall}
        />
      )}
      {detailName && detail.data && (
        <ExtensionDetail detail={detail.data} onClose={() => setDetailName(null)} />
      )}
    </div>
  )
}
