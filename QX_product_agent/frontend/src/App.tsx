import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { ProductWorkspacePage } from '@/pages/ProductWorkspacePage'
import { ResearchHubPage } from '@/pages/ResearchHubPage'
import { PRDStudioPage } from '@/pages/PRDStudioPage'
import { DesignStudioPage } from '@/pages/DesignStudioPage'
// PresentationPage 引入 echarts+recharts（约 1.5MB），懒加载使其不进主包
const PresentationPage = lazy(() =>
  import('@/pages/PresentationPage').then((m) => ({ default: m.PresentationPage })))
import { PptAssetLibraryPage } from '@/pages/PptAssetLibraryPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { ProgressPage } from '@/pages/ProgressPage'
import { ReportPage } from '@/pages/ReportPage'

// ─── 重型页面路由级懒加载（Konva/GrapesJS/Playwright 依赖不进主包） ──
const EditorPage = lazy(() =>
  import('@/pages/EditorPage').then((m) => ({ default: m.EditorPage })))
const ExportPage = lazy(() =>
  import('@/pages/ExportPage').then((m) => ({ default: m.ExportPage })))
const PresentationEditorPage = lazy(() =>
  import('@/pages/PresentationEditorPage').then((m) => ({ default: m.PresentationEditorPage })))

/** 懒加载 Suspense 兜底（与纸张视觉一致的极简骨架） */
function PageFallback() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#F7F5F0',
      color: '#24415E',
      fontSize: 14,
      fontFamily: 'system-ui, sans-serif',
    }}>
      加载中…
    </div>
  )
}

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
      <Route element={<WorkspaceLayout />}>
        {/* 产品线收敛：控制台（v1 报告流水线）不再独立入口，重定向到 Product Workspace */}
        <Route path="/" element={<Navigate to="/workspace" replace />} />
        <Route path="/workspace" element={<ProductWorkspacePage />} />
        <Route path="/studio" element={<Navigate to="/workspace" replace />} />
        <Route path="/research" element={<ResearchHubPage />} />
        <Route path="/prd" element={<PRDStudioPage />} />
        <Route path="/design" element={<DesignStudioPage />} />
        <Route path="/presentation" element={
          <Suspense fallback={<PageFallback />}><PresentationPage /></Suspense>
        } />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/ppt-assets" element={<PptAssetLibraryPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/projects/:projectId/workspace" element={<WorkspacePage />} />
        <Route path="/projects/:projectId/progress" element={<ProgressPage />} />
        <Route path="/projects/:projectId/report" element={<ReportPage />} />
        {/* 兜底重定向 */}
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Route>
      {/* EditorPage 独立路由（不使用 Layout，全屏沉浸） */}
      <Route path="/projects/:projectId/editor" element={
        <Suspense fallback={<PageFallback />}><EditorPage /></Suspense>
      } />
      {/* ExportPage 独立路由（Playwright 打印专用） */}
      <Route path="/export/:productId" element={
        <Suspense fallback={<PageFallback />}><ExportPage /></Suspense>
      } />
      {/* Presentation 编辑器（GrapesJS，全屏） */}
      <Route path="/presentation/editor/:productId" element={
        <Suspense fallback={<PageFallback />}><PresentationEditorPage /></Suspense>
      } />
    </Routes>
  )
}
