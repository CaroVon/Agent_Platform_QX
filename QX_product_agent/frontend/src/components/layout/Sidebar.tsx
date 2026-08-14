import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  FileText,
  BookOpen,
  Sparkles,
  Rocket,
} from 'lucide-react'

const navItems = [
  { to: '/', label: '控制台', icon: LayoutDashboard, end: true },
  { to: '/studio', label: 'Product Studio', icon: Rocket, end: false },
]

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-60 border-r bg-sidebar text-sidebar-foreground flex flex-col">
      {/* ─── Logo 区域 ──────────────────────────────────────── */}
      <div className="flex h-14 items-center gap-2 border-b border-white/10 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Sparkles className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold leading-tight tracking-tight">
            Research Agent
          </span>
          <span className="text-[10px] text-muted-foreground/60">
            产品分析生成平台
          </span>
        </div>
      </div>

      {/* ─── 导航菜单 ─────────────────────────────────────────── */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-white/10 text-white'
                  : 'text-sidebar-foreground/60 hover:bg-white/5 hover:text-sidebar-foreground/80',
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* ─── 底部版本信息 ─────────────────────────────────────── */}
      <div className="border-t border-white/10 px-5 py-3">
        <p className="text-[10px] text-muted-foreground/40">v1.0.0 · 阶段二</p>
      </div>
    </aside>
  )
}
