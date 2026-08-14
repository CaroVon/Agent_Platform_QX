import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { DashboardPage } from '@/pages/DashboardPage'
import { ProductWorkspacePage } from '@/pages/ProductWorkspacePage'
import { ResearchHubPage } from '@/pages/ResearchHubPage'
import { PRDStudioPage } from '@/pages/PRDStudioPage'
import { DesignStudioPage } from '@/pages/DesignStudioPage'
import { PresentationPage } from '@/pages/PresentationPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { EditorPage } from '@/pages/EditorPage'
import { ProgressPage } from '@/pages/ProgressPage'
import { ReportPage } from '@/pages/ReportPage'
import { ExportPage } from '@/pages/ExportPage'

/**
 * 应用根路由（productize: 8 模块信息架构）
 *
 * /workspace     Product Workspace（四段式主工作区）
 * /research      Research Hub     /prd    PRD Studio
 * /design        Design Studio    /presentation  Presentation
 * /knowledge     Knowledge Base   /templates    Templates
 * /settings      Settings
 * /projects/:id/*  旧工作台（保留兼容）
 * /export/:id      Playwright 打印专用
 */
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/workspace" element={<ProductWorkspacePage />} />
        <Route path="/studio" element={<Navigate to="/workspace" replace />} />
        <Route path="/research" element={<ResearchHubPage />} />
        <Route path="/prd" element={<PRDStudioPage />} />
        <Route path="/design" element={<DesignStudioPage />} />
        <Route path="/presentation" element={<PresentationPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/projects/:projectId/workspace" element={<WorkspacePage />} />
        <Route path="/projects/:projectId/progress" element={<ProgressPage />} />
        <Route path="/projects/:projectId/report" element={<ReportPage />} />
        {/* 兜底重定向 */}
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Route>
      {/* EditorPage 独立路由（不使用 Layout，全屏沉浸） */}
      <Route path="/projects/:projectId/editor" element={<EditorPage />} />
      {/* ExportPage 独立路由（Playwright 打印专用） */}
      <Route path="/export/:productId" element={<ExportPage />} />
    </Routes>
  )
}
