import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { ProductWorkspacePage } from '@/pages/ProductWorkspacePage'
import { ResearchHubPage } from '@/pages/ResearchHubPage'
import { PRDStudioPage } from '@/pages/PRDStudioPage'
import { DesignStudioPage } from '@/pages/DesignStudioPage'
import { ProjectAssetLibraryPage } from '@/pages/ProjectAssetLibraryPage'
import { KeywordsPage } from '@/pages/KeywordsPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { PptAssetLibraryPage } from '@/pages/PptAssetLibraryPage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { ProgressPage } from '@/pages/ProgressPage'
import { ReportPage } from '@/pages/ReportPage'
import { LoadingFallback } from '@/components/motion/PageTransition'

// 重型页面路由级懒加载（Konva/GrapesJS/Playwright/echarts 不进主包）
const MemoryPage = lazy(() =>
  import('@/pages/MemoryPage').then((m) => ({ default: m.MemoryPage })))
const PresentationPage = lazy(() =>
  import('@/pages/PresentationPage').then((m) => ({ default: m.PresentationPage })))
const EditorPage = lazy(() =>
  import('@/pages/EditorPage').then((m) => ({ default: m.EditorPage })))
const ExportPage = lazy(() =>
  import('@/pages/ExportPage').then((m) => ({ default: m.ExportPage })))
const PresentationEditorPage = lazy(() =>
  import('@/pages/PresentationEditorPage').then((m) => ({ default: m.PresentationEditorPage })))

/**
 * 应用根路由（productize: 8 模块信息架构）
 *
 * /workspace        Product Workspace（四段式主工作区）
 * /research         Research Hub          /prd            PRD Studio
 * /design           Design Studio         /presentation   Presentation（懒加载）
 * /keywords         Keywords              /memory         Memory Graph
 * /project-assets   项目资产库            /ppt-assets     PPT 资产库
 * /knowledge        Knowledge Base        /templates      Templates
 * /settings         Settings
 * /projects/:id/*   旧工作台（保留兼容）
 * /export/:id       Playwright 打印专用
 */
export function App() {
  return (
    <Routes>
      <Route element={<WorkspaceLayout />}>
        {/* 产品线收敛：根路径与 /studio 重定向到 Product Workspace */}
        <Route path="/" element={<Navigate to="/workspace" replace />} />
        <Route path="/workspace" element={<ProductWorkspacePage />} />
        <Route path="/studio" element={<Navigate to="/workspace" replace />} />

        {/* 创作模块 */}
        <Route path="/research" element={<ResearchHubPage />} />
        <Route path="/prd" element={<PRDStudioPage />} />
        <Route path="/design" element={<DesignStudioPage />} />
        <Route
          path="/presentation"
          element={
            <Suspense fallback={<LoadingFallback message="加载演示文稿" />}>
              <PresentationPage />
            </Suspense>
          }
        />
        <Route path="/keywords" element={<KeywordsPage />} />

        {/* 资源模块 */}
        <Route path="/project-assets" element={<ProjectAssetLibraryPage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/ppt-assets" element={<PptAssetLibraryPage />} />
        <Route path="/templates" element={<TemplatesPage />} />

        {/* 系统 */}
        <Route path="/settings" element={<SettingsPage />} />

        {/* 旧工作台路由（保留兼容） */}
        <Route path="/projects/:projectId/workspace" element={<WorkspacePage />} />
        <Route path="/projects/:projectId/progress" element={<ProgressPage />} />
        <Route path="/projects/:projectId/report" element={<ReportPage />} />

        {/* 兜底 */}
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Route>

      {/* 全屏沉浸路由（不走 Layout） */}
      <Route
        path="/projects/:projectId/editor"
        element={
          <Suspense fallback={<LoadingFallback message="加载编辑器" />}>
            <EditorPage />
          </Suspense>
        }
      />
      <Route
        path="/export/:productId"
        element={
          <Suspense fallback={<LoadingFallback message="准备导出" />}>
            <ExportPage />
          </Suspense>
        }
      />
      <Route
        path="/presentation/editor/:productId"
        element={
          <Suspense fallback={<LoadingFallback message="加载演示编辑器" />}>
            <PresentationEditorPage />
          </Suspense>
        }
      />
    </Routes>
  )
}