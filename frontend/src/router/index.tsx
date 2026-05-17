import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { WorkbenchPage } from '@/features/workbench/WorkbenchPage'
import { ResultsPage } from '@/features/results/ResultsPage'
import { AdviceDetail } from '@/features/results/AdviceDetail'
import { BriefingDetail } from '@/features/results/BriefingDetail'
import { SourcesPage } from '@/features/sources/SourcesPage'
import { ConfigPage } from '@/features/config/ConfigPage'

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <WorkbenchPage /> },
      { path: 'workbench', element: <WorkbenchPage /> },
      { path: 'results', element: <ResultsPage /> },
      { path: 'results/advices/:id', element: <AdviceDetail /> },
      { path: 'results/briefings/:id', element: <BriefingDetail /> },
      { path: 'sources', element: <SourcesPage /> },
      { path: 'config', element: <ConfigPage /> },
    ],
  },
])
