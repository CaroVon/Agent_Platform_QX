import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { DashboardPage } from '@/pages/DashboardPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { EditorPage } from '@/pages/EditorPage'
import { ProgressPage } from '@/pages/ProgressPage'
import { ReportPage } from '@/pages/ReportPage'
import { ProductStudioPage } from '@/pages/ProductStudioPage'
import { ExportPage } from '@/pages/ExportPage'

/**
 * 应用根路由
 *
 * 路由架构：
 * /                    → 控制台（项目列表 + 新建入口）
 * /projects/:id/workspace → 🌟 项目管理工作台（大纲审核 + 状态监控）
 * /projects/:id/editor  → 🎨 Canvas 编辑器（全屏排版 + AI 辅助 + PDF 导出）
 * /projects/:id/progress → 生成进度页（轮询，兼容旧链接）
 * /projects/:id/report  → 报告阅读器（含溯源，兼容旧链接）
 * /studio               → 🚀 AI Product Studio（多 Agent 产品工作台）
 * /export/:productId    → 🖨️ 导出专用路由（Playwright 打印，无 UI 外壳）
 */
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/studio" element={<ProductStudioPage />} />
        <Route path="/projects/:projectId/workspace" element={<WorkspacePage />} />
        <Route path="/projects/:projectId/progress" element={<ProgressPage />} />
        <Route path="/projects/:projectId/report" element={<ReportPage />} />
        {/* 兜底重定向 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
      {/* EditorPage 独立路由（不使用 Layout，全屏沉浸） */}
      <Route path="/projects/:projectId/editor" element={<EditorPage />} />
      {/* ExportPage 独立路由（Playwright 打印专用） */}
      <Route path="/export/:productId" element={<ExportPage />} />
    </Routes>
  )
}
