import { Outlet } from 'react-router-dom'
import { SideNav } from './SideNav'

export function AppShell() {
  return (
    <div className="flex h-screen w-full overflow-hidden">
      <SideNav />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
