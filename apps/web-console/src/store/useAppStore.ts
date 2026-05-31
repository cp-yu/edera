import { create } from 'zustand'

interface AppState {
  selectedDagName: string
  selectedNodeId: string | null
  selectedEdgeId: string | null
  inspectorTab: 'config' | 'runtime' | 'triggers'
  entityFilter: string[]
  theme: 'light' | 'dark'
  setSelectedDag: (name: string) => void
  setSelectedNode: (id: string | null) => void
  setSelectedEdge: (id: string | null) => void
  setInspectorTab: (tab: 'config' | 'runtime' | 'triggers') => void
  setEntityFilter: (entities: string[]) => void
  toggleTheme: () => void
}

const SELECTED_DAG_STORAGE_KEY = 'workbench:selectedDagName'

const getInitialSelectedDag = (): string => localStorage.getItem(SELECTED_DAG_STORAGE_KEY) || 'default'

const getInitialTheme = (): 'light' | 'dark' => {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useAppStore = create<AppState>((set) => ({
  selectedDagName: getInitialSelectedDag(),
  selectedNodeId: null,
  selectedEdgeId: null,
  inspectorTab: 'config',
  entityFilter: [],
  theme: getInitialTheme(),
  setSelectedDag: (name) => {
    localStorage.setItem(SELECTED_DAG_STORAGE_KEY, name)
    set({ selectedDagName: name, selectedNodeId: null, selectedEdgeId: null, inspectorTab: 'config' })
  },
  setSelectedNode: (id) => set({ selectedNodeId: id, selectedEdgeId: null, inspectorTab: 'config' }),
  setSelectedEdge: (id) => set({ selectedEdgeId: id, selectedNodeId: null, inspectorTab: 'config' }),
  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  setEntityFilter: (entities) => set({ entityFilter: entities }),
  toggleTheme: () =>
    set((state) => {
      const next = state.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('theme', next)
      document.documentElement.classList.toggle('dark', next === 'dark')
      return { theme: next }
    }),
}))
