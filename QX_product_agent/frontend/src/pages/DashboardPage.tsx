import { useState } from 'react'
import { Plus, FileText, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/common/button'
import { ProjectCard } from '@/components/projects/ProjectCard'
import { CreateProjectModal } from '@/components/projects/CreateProjectModal'
import { useProjectList } from '@/hooks/useProjects'

/**
 * 控制台页面（任务 2）
 *
 * 左侧边栏导航 + 主视图展示历史项目卡片列表。
 * 提供一个突出的"新建分析"按钮。
 */
export function DashboardPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const { data: projects, isLoading, isError, error } = useProjectList()

  return (
    <div className="space-y-6">
      {/* ─── 页面头部 ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">控制台</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            管理您的产品分析项目，创建新的分析报告或查看已有成果。
          </p>
        </div>
        <Button
          size="lg"
          onClick={() => setModalOpen(true)}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          新建分析
        </Button>
      </div>

      {/* ─── 加载状态 ─────────────────────────────────────────── */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">加载项目列表中...</p>
          </div>
        </div>
      )}

      {/* ─── 错误状态 ─────────────────────────────────────────── */}
      {isError && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3 text-destructive">
            <AlertCircle className="h-8 w-8" />
            <p className="text-sm font-medium">
              加载失败：{(error as Error)?.message ?? '未知错误'}
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
              重试
            </Button>
          </div>
        </div>
      )}

      {/* ─── 空状态 ───────────────────────────────────────────── */}
      {!isLoading && !isError && projects && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
            <FileText className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">暂无分析项目</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            点击"新建分析"按钮，开始您的第一份产品分析报告。
          </p>
          <Button
            className="mt-6 gap-2"
            onClick={() => setModalOpen(true)}
          >
            <Plus className="h-4 w-4" />
            新建分析
          </Button>
        </div>
      )}

      {/* ─── 项目卡片网格 ─────────────────────────────────────── */}
      {!isLoading && !isError && projects && projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      {/* ─── 新建模态框 ───────────────────────────────────────── */}
      <CreateProjectModal open={modalOpen} onOpenChange={setModalOpen} />
    </div>
  )
}
