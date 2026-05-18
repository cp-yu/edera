import { create } from 'zustand'

interface AppState {
  selectedDagName: string
  selectedNodeId: string | null
  selectedEdgeId: string | null
  targetFilter: string[]
  theme: 'light' | 'dark'
  setSelectedDag: (name: string) => void
  setSelectedNode: (id: string | null) => void
  setSelectedEdge: (id: string | null) => void
  setTargetFilter: (targets: string[]) => void
  toggleTheme: () => void
}

const getInitialTheme = (): 'light' | 'dark' => {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useAppStore = create<AppState>((set) => ({
  selectedDagName: 'default',
  selectedNodeId: null,
  selectedEdgeId: null,
  targetFilter: [],
  theme: getInitialTheme(),
  setSelectedDag: (name) => set({ selectedDagName: name, selectedNodeId: null, selectedEdgeId: null }),
  setSelectedNode: (id) => set({ selectedNodeId: id, selectedEdgeId: null }),
  setSelectedEdge: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),
  setTargetFilter: (targets) => set({ targetFilter: targets }),
  toggleTheme: () =>
    set((state) => {
      const next = state.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('theme', next)
      document.documentElement.classList.toggle('dark', next === 'dark')
      return { theme: next }
    }),
}))
