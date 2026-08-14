/**
 * Sidebar —— 8 模块导航 + 可折叠 + 分组（Notion/Linear 风格）
 *
 * 模块分组：
 *   WORKSPACE  Product Workspace
 *   STUDIO     Research Hub / PRD Studio / Design Studio / Presentation
 *   MANAGE     Knowledge Base / Templates / Settings
 */

import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  BookOpen,
  Boxes,
  ChevronsLeft,
  ChevronsRight,
  Database,
  FileText,
  LayoutDashboard,
  LayoutTemplate,
  MonitorPlay,
  PenTool,
  Settings,
  Sparkles,
  Telescope,
} from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: typeof Sparkles
  end?: boolean
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: '工作台',
    items: [{ to: '/workspace', label: 'Product Workspace', icon: LayoutDashboard, end: false }],
  },
  {
    label: '创作',
    items: [
      { to: '/research', label: 'Research Hub', icon: Telescope },
      { to: '/prd', label: 'PRD Studio', icon: FileText },
      { to: '/design', label: 'Design Studio', icon: PenTool },
      { to: '/presentation', label: 'Presentation', icon: MonitorPlay },
    ],
  },
  {
    label: '管理',
    items: [
      { to: '/knowledge', label: 'Knowledge Base', icon: Database },
      { to: '/templates', label: 'Templates', icon: LayoutTemplate },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-sidebar text-sidebar-foreground',
        'transition-[width] duration-200 ease-in-out',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* ─── Logo 区域 ──────────────────────────────────────── */}
      <div
        className={cn(
          'flex h-14 items-center border-b border-white/10',
          collapsed ? 'justify-center px-2' : 'gap-2 px-5',
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary">
          <Sparkles className="h-4 w-4 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold leading-tight tracking-tight">
              Product Studio
            </span>
            <span className="truncate text-[10px] text-muted-foreground/60">
              AI 产品研发平台
            </span>
          </div>
        )}
      </div>

      {/* ─── 导航菜单 ─────────────────────────────────────────── */}
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <div className="mb-1.5 px-3 text-[10px] font-medium uppercase tracking-widest text-muted-foreground/50">
                {group.label}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  title={item.label}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg text-sm font-medium transition-colors duration-150',
                      collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2',
                      isActive
                        ? 'bg-white/10 text-white'
                        : 'text-sidebar-foreground/60 hover:bg-white/5 hover:text-sidebar-foreground/85',
                    )
                  }
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* ─── 折叠开关 + 版本 ─────────────────────────────────── */}
      <div className="border-t border-white/10 px-3 py-3">
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
          className={cn(
            'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs text-sidebar-foreground/50 transition-colors hover:bg-white/5 hover:text-sidebar-foreground/80',
            collapsed && 'justify-center px-2',
          )}
        >
          {collapsed ? (
            <ChevronsRight className="h-4 w-4 shrink-0" />
          ) : (
            <>
              <ChevronsLeft className="h-4 w-4 shrink-0" />
              <span>折叠侧边栏</span>
            </>
          )}
        </button>
        {!collapsed && (
          <p className="mt-1 px-3 text-[10px] text-muted-foreground/40">
            v1.1 · AI Product Studio
          </p>
        )}
      </div>
    </aside>
  )
}
