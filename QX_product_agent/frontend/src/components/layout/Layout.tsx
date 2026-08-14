import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { cn } from '@/lib/utils'

const COLLAPSE_KEY = 'qx-sidebar-collapsed'

/**
 * 全局布局组件（Breathing UI）
 *
 * 左侧可折叠侧边栏（8 模块）+ 右侧大留白主内容区。
 * 折叠状态持久化到 localStorage。
 */
export function Layout() {
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
      /* 隐私模式下忽略 */
    }
  }, [collapsed])

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />

      {/* ─── 主内容区 ─────────────────────────────────────────── */}
      <main
        className={cn(
          'transition-[padding-left] duration-200 ease-in-out',
          collapsed ? 'pl-16' : 'pl-60',
        )}
      >
        {/* 顶栏：轻量，呼吸感 */}
        <div className="sticky top-0 z-30 h-14 border-b bg-background/80 backdrop-blur-sm" />

        {/* 大留白内容区 */}
        <div className="mx-auto max-w-6xl px-8 py-10 lg:px-12">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
