import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

/**
 * 全局布局组件
 *
 * 左侧固定侧边栏 + 右侧主内容区
 * 使用 Tailwind CSS 建立冷静的 B 端企业级色系（Zinc/Slate）
 */
export function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />

      {/* ─── 主内容区 ─────────────────────────────────────────── */}
      <main className="pl-60">
        {/* 顶栏占位（后续可添加面包屑/用户菜单） */}
        <div className="sticky top-0 z-30 h-14 border-b bg-background/80 backdrop-blur-sm" />

        <div className="p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
