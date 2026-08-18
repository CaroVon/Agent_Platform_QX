/**
 * Sidebar —— Vintage Linear 风格侧边栏（frontedUI.md）
 *
 * 结构：
 *   Logo → Workspace selector → 分组导航 → 当前项目指示 → 用户资料区
 * 折叠状态持久化 localStorage；当前项目来自 qx-current-project。
 */

import { NavLink } from 'react-router-dom'
import {
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  ChevronsUpDown,
  Database,
  FileDown,
  FileText,
  LayoutDashboard,
  LayoutTemplate,
  MonitorPlay,
  PenTool,
  Settings,
  Sparkles,
  Telescope,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: typeof Sparkles
  end?: boolean
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: '工作台',
    items: [{ to: '/workspace', label: 'Product Workspace', icon: LayoutDashboard }],
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
      { to: '/ppt-assets', label: 'PPT 资产库', icon: FileDown },
      { to: '/knowledge', label: 'Knowledge Base', icon: Database },
      { to: '/templates', label: 'Templates', icon: LayoutTemplate },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

function readCurrentProject(): string {
  try {
    return localStorage.getItem('qx-current-project') ?? ''
  } catch {
    return ''
  }
}

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  const currentProject = readCurrentProject()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-white/5 bg-sidebar text-sidebar-foreground',
        'transition-[width] duration-200 ease-in-out',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* ─── Logo ──────────────────────────────────────────── */}
      <div
        className={cn(
          'flex h-14 items-center border-b border-white/5',
          collapsed ? 'justify-center px-2' : 'gap-2.5 px-5',
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-foreground/10">
          <Sparkles className="h-4 w-4 text-sidebar-foreground/90" />
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="font-editorial truncate text-sm font-semibold tracking-tight">
              QX Product Studio
            </span>
            <span className="truncate text-[10px] text-sidebar-foreground/45">
              AI 产品研发工作室
            </span>
          </div>
        )}
      </div>

      {/* ─── Workspace selector ────────────────────────────── */}
      {!collapsed && (
        <div className="px-3 pt-4">
          <button
            type="button"
            className="flex w-full items-center gap-2.5 rounded-lg border border-white/5 bg-white/[0.04] px-3 py-2.5 text-left transition-colors hover:bg-white/[0.08]"
          >
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-sidebar-foreground/10 text-[10px] font-bold">
              QX
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium">AI Product Workspace</div>
              <div className="truncate text-[10px] text-sidebar-foreground/45">Personal Workspace</div>
            </div>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-sidebar-foreground/40" />
          </button>
        </div>
      )}

      {/* ─── 导航菜单 ─────────────────────────────────────────── */}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <div className="mb-1.5 px-3 text-[10px] font-medium uppercase tracking-[0.14em] text-sidebar-foreground/35">
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
                      'flex items-center gap-3 rounded-lg text-[13px] font-medium transition-colors duration-150',
                      collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2',
                      isActive
                        ? 'bg-sidebar-foreground/10 text-sidebar-foreground'
                        : 'text-sidebar-foreground/55 hover:bg-sidebar-foreground/[0.06] hover:text-sidebar-foreground/85',
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

      {/* ─── 当前项目指示 ─────────────────────────────────── */}
      {!collapsed && currentProject && (
        <div className="mx-3 mb-2 flex items-center gap-2.5 rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2.5">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[11px] font-medium text-sidebar-foreground/80">
              {currentProject}
            </div>
            <div className="text-[10px] text-sidebar-foreground/40">当前项目</div>
          </div>
          <BookOpen className="h-3.5 w-3.5 shrink-0 text-sidebar-foreground/40" />
        </div>
      )}

      {/* ─── 用户资料区 ─────────────────────────────────────── */}
      <div className="border-t border-white/5 px-3 py-3">
        <div
          className={cn(
            'flex items-center gap-2.5 rounded-lg px-2 py-2',
            collapsed && 'justify-center',
          )}
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#C87E4F] to-[#3F6B4F] text-[10px] font-semibold text-white">
            A
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-sidebar-foreground/85">
                Administrator
              </div>
              <div className="truncate text-[10px] text-sidebar-foreground/40">本地工作区</div>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
          className={cn(
            'mt-1 flex w-full items-center gap-3 rounded-lg px-2 py-2 text-[11px] text-sidebar-foreground/45 transition-colors hover:bg-white/5 hover:text-sidebar-foreground/80',
            collapsed && 'justify-center',
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
      </div>
    </aside>
  )
}
