/**
 * Sidebar —— 商务深色侧栏（v3：圆角版）
 */

import { NavLink } from 'react-router-dom'
import {
  Archive,
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  ChevronsUpDown,
  Database,
  FileText,
  LayoutDashboard,
  LayoutTemplate,
  MonitorPlay,
  Network,
  PenTool,
  Settings,
  Sparkles,
  Tags,
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
    items: [{ to: '/workspace', label: '产品工作台', icon: LayoutDashboard }],
  },
  {
    label: '创作',
    items: [
      { to: '/research', label: '调研中心', icon: Telescope },
      { to: '/prd', label: 'PRD 工作室', icon: FileText },
      { to: '/design', label: '设计工作室', icon: PenTool },
      { to: '/presentation', label: '演示文稿', icon: MonitorPlay },
      { to: '/keywords', label: '关键词', icon: Tags },
    ],
  },
  {
    label: '资产库',
    items: [
      { to: '/project-assets', label: '项目资产库', icon: Archive },
      { to: '/memory', label: '记忆图谱', icon: Network },
      { to: '/ppt-assets', label: 'PPT 资产库', icon: MonitorPlay },
      { to: '/knowledge', label: '知识库', icon: Database },
      { to: '/templates', label: '模板', icon: LayoutTemplate },
    ],
  },
  {
    label: '系统',
    items: [{ to: '/settings', label: '设置', icon: Settings }],
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
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-sidebar bg-sidebar text-sidebar-foreground shadow-elev-md',
        'transition-[width] duration-300 ease-out',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-sidebar-foreground/10',
          collapsed ? 'justify-center px-2' : 'gap-3 px-4',
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary shadow-elev-glow">
          <Sparkles className="h-4 w-4 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="font-serif text-[15px] font-semibold tracking-tight text-foreground">
              QX 产品
            </span>
            <span className="text-[11px] text-muted-foreground">AI 产品工作室</span>
          </div>
        )}
      </div>

      {/* Workspace selector */}
      {!collapsed && (
        <div className="border-b border-sidebar-foreground/10 px-3 py-3">
          <button
            type="button"
            className="group flex w-full items-center gap-2.5 rounded-lg border border-sidebar-foreground/10 bg-sidebar-foreground/[0.03] px-3 py-2 text-left transition-all hover:border-primary/50 hover:bg-primary/10"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/15 font-mono text-[10px] font-semibold text-primary">
              QX
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-foreground">
                AI 工作区
              </div>
              <div className="truncate text-[11px] text-muted-foreground">
                个人工作区 · 01
              </div>
            </div>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
          </button>
        </div>
      )}

      {/* 导航 */}
      <nav className="flex-1 overflow-y-auto px-2 py-4">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={cn(gi > 0 && 'mt-5')}>
            {!collapsed && (
              <div className="mb-1.5 px-3 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70">
                {group.label}
              </div>
            )}
            <div className="space-y-1">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-200',
                      collapsed ? 'justify-center' : '',
                      isActive
                        ? 'bg-primary/15 text-primary shadow-elev-sm'
                        : 'text-sidebar-foreground/70 hover:bg-sidebar-foreground/[0.04] hover:text-foreground',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary shadow-[0_0_10px_hsl(var(--primary))]" />
                      )}
                      <item.icon
                        className={cn(
                          'h-4 w-4 shrink-0 transition-colors',
                          isActive ? 'text-primary' : 'text-sidebar-foreground/55 group-hover:text-foreground',
                        )}
                      />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* 当前项目指示 */}
      {!collapsed && currentProject && (
        <div className="mx-3 mb-2 rounded-lg border border-primary/30 bg-primary/10 p-3 shadow-elev-xs">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary/90">
              当前项目
            </span>
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary" />
          </div>
          <div className="truncate text-[12px] font-medium text-foreground">
            {currentProject}
          </div>
        </div>
      )}

      {/* 用户区 */}
      <div className="border-t border-sidebar-foreground/10 px-3 py-3">
        <div
          className={cn(
            'flex items-center gap-2.5 px-2 py-1.5',
            collapsed && 'justify-center',
          )}
        >
          <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent font-serif text-[12px] font-semibold text-primary-foreground shadow-elev-sm">
            A
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-foreground">
                Administrator
              </div>
              <div className="truncate text-[11px] text-muted-foreground">本地工作区</div>
            </div>
          )}
          {!collapsed && <BookOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />}
        </div>
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
          className={cn(
            'mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:bg-sidebar-foreground/5 hover:text-foreground',
            collapsed && 'justify-center',
          )}
        >
          {collapsed ? (
            <ChevronsRight className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <>
              <ChevronsLeft className="h-3.5 w-3.5 shrink-0" />
              <span>折叠</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}