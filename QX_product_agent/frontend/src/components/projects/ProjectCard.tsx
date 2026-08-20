import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Clock, ArrowRight, Trash2 } from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'
import { ProjectStatusBadge } from '@/components/common/badge'
import { Button } from '@/components/common/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/common/dialog'
import { useDeleteProject } from '@/hooks/useProjects'
import type { ProjectResponse } from '@/types/api'

interface ProjectCardProps {
  project: ProjectResponse
}

/**
 * 项目卡片组件
 *
 * 在控制台/项目列表中展示单个项目的信息缩略，
 * 支持删除操作（含确认对话框）。
 */
export function ProjectCard({ project }: ProjectCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const deleteProject = useDeleteProject()

  const isProcessing = project.status === 'preparing_data'
    || project.status === 'waiting_for_sources'
    || project.status === 'preparing_outline'
    || project.status === 'waiting_for_outline'
    || project.status === 'drafting'
  const isCompleted = project.status === 'completed'
  const isFailed = project.status === 'failed'
  const isAwaitingApproval = project.status === 'waiting_for_outline'
  const isAwaitingSources = project.status === 'waiting_for_sources'

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setShowDeleteDialog(true)
  }

  const handleConfirmDelete = async () => {
    await deleteProject.mutateAsync(project.id)
    setShowDeleteDialog(false)
  }

  return (
    <>
      <Link
        to={`/projects/${project.id}/workspace`}
        className={cn(
          'group relative flex flex-col gap-3 rounded-xl border bg-card p-5 transition-all duration-200',
          'hover:shadow-md hover:border-primary/20',
          'active:scale-[0.98]',
        )}
      >
        {/* ── 删除按钮 ────────────────────────────────────────── */}
        <button
          type="button"
          onClick={handleDeleteClick}
          className={cn(
            'absolute top-3 right-3 z-10 flex h-7 w-7 items-center justify-center rounded-md',
            'text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10',
            'opacity-0 group-hover:opacity-100 transition-all duration-200',
            'focus:opacity-100 focus:outline-none',
          )}
          title="删除项目"
          aria-label="删除项目"
        >
          <Trash2 className="h-4 w-4" />
        </button>

        {/* ─── 顶部行：主题 + 状态 ──────────────────────────────── */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-secondary">
              <FileText className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold leading-tight">
                {project.topic}
              </h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                <Clock className="mr-1 inline h-3 w-3" />
                {formatDate(project.created_at)}
              </p>
            </div>
          </div>
          <ProjectStatusBadge status={project.status} />
        </div>

        {/* ─── 进度指示 / 操作入口 ──────────────────────────────── */}
        <div className="mt-auto flex items-center justify-between">
          {isProcessing && (
            <span className="text-xs text-muted-foreground">
              {isAwaitingSources ? '待审核资料...' : isAwaitingApproval ? '待确认大纲...' : '正在生成中...'}
            </span>
          )}
          {isCompleted && (
            <span className="flex items-center gap-1 text-xs font-medium text-primary">
              查看报告
              <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
            </span>
          )}
          {isFailed && (
            <span className="text-xs text-destructive">查看错误详情</span>
          )}
          {isProcessing && (
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
          )}
        </div>
      </Link>

      {/* ─── 删除确认对话框 ──────────────────────────────────────── */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确定删除项目？</DialogTitle>
            <DialogDescription>
              此操作不可撤销。项目「{project.topic}」及其所有关联数据
              （报告、任务、日志）将被永久删除。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleteProject.isPending}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              loading={deleteProject.isPending}
            >
              确定删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}