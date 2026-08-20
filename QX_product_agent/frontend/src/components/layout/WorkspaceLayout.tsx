/**
 * WorkspaceLayout —— 全局布局（v3：圆角商务版）
 */

import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { cn } from '@/lib/utils'
import {
  PageTransition,
  TopProgressBar,
} from '@/components/motion/PageTransition'

const COLLAPSE_KEY = 'qx-sidebar-collapsed'

export function WorkspaceLayout() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <TopProgressBar />
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />

      <main
        className={cn(
          'relative z-10 transition-[padding-left] duration-300 ease-out',
          collapsed ? 'pl-16' : 'pl-64',
        )}
      >
        <Header />
        {/* 内容区：贴侧边栏全宽布局，左/右留白约 1.5cm（56px），不再居中限宽 */}
        <div className="w-full px-6 py-8 lg:px-14 lg:py-10">
          <PageTransition>
            <Outlet />
          </PageTransition>
        </div>
      </main>
    </div>
  )
}