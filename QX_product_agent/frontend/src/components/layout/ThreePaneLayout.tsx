/**
 * ============================================================
 * ThreePaneLayout —— 现代三栏工作台骨架
 *
 * 布局结构（100vh，无全局滚动条，各栏独立滚动）：
 * ┌──────────┬──────────────────────┬────────────┐
 * │  左栏    │      中栏            │   右栏     │
 * │ (w-64)   │     (flex-1)         │  (w-80)    │
 * │          │                      │            │
 * │ 大纲目录 │ 编辑器 + 进度条      │ 引用/对话  │
 * │ 树      │                      │ (默认折叠) │
 * └──────────┴──────────────────────┴────────────┘
 * ============================================================
 */

import { type ReactNode, createContext, useContext, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import type { RightPanelView } from '@/types/index'

// ─── 面板状态 Context ──────────────────────────────────────────

interface ThreePaneContextType {
  rightPanel: RightPanelView
  setRightPanel: (view: RightPanelView) => void
  toggleRightPanel: () => void
}

const ThreePaneContext = createContext<ThreePaneContextType | null>(null)

export function useThreePane() {
  const ctx = useContext(ThreePaneContext)
  if (!ctx) throw new Error('useThreePane must be used within ThreePaneLayout')
  return ctx
}

// ─── 布局组件 ──────────────────────────────────────────────────

interface ThreePaneLayoutProps {
  /** 左栏：大纲目录树 */
  leftPane: ReactNode
  /** 中栏：编辑器 + 进度指示器 */
  centerPane: ReactNode
  /** 右栏：引用溯源 / Agent 对话（可选） */
  rightPane?: ReactNode
}

export function ThreePaneLayout({
  leftPane,
  centerPane,
  rightPane,
}: ThreePaneLayoutProps) {
  const [rightPanel, setRightPanel] = useState<RightPanelView>('citations')

  const toggleRightPanel = useCallback(() => {
    setRightPanel((prev) => (prev === 'closed' ? 'citations' : 'closed'))
  }, [])

  return (
    <ThreePaneContext.Provider value={{ rightPanel, setRightPanel, toggleRightPanel }}>
      <div className="flex h-screen w-full overflow-hidden bg-background">
        {/* ─── 左栏：大纲目录 ────────────────────────────────── */}
        <aside className="w-64 shrink-0 border-r border-border bg-card overflow-y-auto">
          {leftPane}
        </aside>

        {/* ─── 中栏：编辑器 ──────────────────────────────────── */}
        <main className="flex flex-1 flex-col min-w-0 overflow-hidden">
          {centerPane}
        </main>

        {/* ─── 右栏：引用/对话 ──────────────────────────────── */}
        {rightPane && (
          <aside
            className={cn(
              'shrink-0 border-l border-border bg-card transition-all duration-300 ease-in-out overflow-y-auto',
              rightPanel !== 'closed' ? 'w-80 opacity-100' : 'w-0 opacity-0 overflow-hidden',
            )}
          >
            <div className={cn('h-full', rightPanel === 'closed' && 'hidden')}>
              {rightPane}
            </div>
          </aside>
        )}
      </div>
    </ThreePaneContext.Provider>
  )
}
