import { NavLink } from 'react-router-dom'
import { LayoutDashboard, BarChart3, Radio, Settings, Moon, Sun, Workflow, Boxes } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'

const links = [
  { to: '/workbench', label: '工作台', icon: LayoutDashboard },
  { to: '/results', label: '结果', icon: BarChart3 },
  { to: '/sources', label: '信息源', icon: Radio },
  { to: '/entities', label: '实体', icon: Boxes },
  { to: '/nodes', label: '节点', icon: Workflow },
  { to: '/config', label: '配置', icon: Settings },
]

export function SideNav() {
  const { theme, toggleTheme } = useAppStore()

  return (
    <nav className="flex w-14 flex-col items-center border-r bg-card py-4 gap-2">
      {links.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          title={label}
          className={({ isActive }) =>
            cn(
              'flex h-10 w-10 items-center justify-center rounded-md transition-colors',
              isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/50',
            )
          }
        >
          <Icon size={20} />
        </NavLink>
      ))}
      <div className="mt-auto">
        <button
          onClick={toggleTheme}
          title="切换主题"
          className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-accent/50 transition-colors"
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </div>
    </nav>
  )
}
