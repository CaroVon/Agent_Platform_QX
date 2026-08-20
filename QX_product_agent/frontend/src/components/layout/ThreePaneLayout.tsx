/**
 * ThreePaneLayout —— 现代商务三栏工作台
 */

import { type ReactNode, createContext, useContext, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import type { RightPanelView } from '@/types/index'

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

interface ThreePaneLayoutProps {
  leftPane: ReactNode
  centerPane: ReactNode
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
      <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden rounded-tl-xl bg-background">
        <aside className="w-64 shrink-0 overflow-y-auto border-r border-border bg-card/40">
          {leftPane}
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {centerPane}
        </main>

        {rightPane && (
          <aside
            className={cn(
              'shrink-0 overflow-y-auto border-l border-border bg-card/40 transition-all duration-300 ease-out',
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