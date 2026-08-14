import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { cn } from '@/lib/utils'

const COLLAPSE_KEY = 'qx-sidebar-collapsed'

/**
 * WorkspaceLayout —— 全局布局（Vintage + Breathable）
 *
 * 深墨蓝可折叠侧边栏 + 纸感大留白主内容区（页面 padding 32-48px）。
 */
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
      /* 隐私模式忽略 */
    }
  }, [collapsed])

  return (
    <div className="bg-paper min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />

      <main
        className={cn(
          'transition-[padding-left] duration-200 ease-in-out',
          collapsed ? 'pl-16' : 'pl-64',
        )}
      >
        <Header />

        {/* 大留白内容区（32-48px 页面边距） */}
        <div className="mx-auto max-w-6xl px-10 py-12 lg:px-12">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
