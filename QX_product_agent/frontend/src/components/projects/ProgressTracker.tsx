import { cn } from '@/lib/utils'
import type { TaskResponse, TaskTypeEnum, TaskStatusEnum } from '@/types/api'
import { Check } from 'lucide-react'

/**
 * 进度阶段定义
 * ── 对应后端的 TaskType，用于可视化展示
 */
interface ProgressStep {
  type: TaskTypeEnum
  label: string
  icon: string
}

const PROGRESS_STEPS: ProgressStep[] = [
  { type: 'search', label: '搜集资料', icon: '🔍' },
  { type: 'build_knowledge_base', label: '知识库构建', icon: '📚' },
  { type: 'generate_outline', label: '规划大纲', icon: '📋' },
  { type: 'write_section', label: 'AI 撰写中', icon: '✍️' },
  { type: 'build_report', label: '报告排版', icon: '📄' },
  { type: 'generate_pdf', label: 'PDF 输出', icon: '📕' },
]

interface ProgressTrackerProps {
  tasks: TaskResponse[]
  percentage: number
  projectStatus: string
  currentStep?: { step: string; message: string; icon: string | null; level: string } | null
}

/**
 * 阶段指示器组件
 *
 * 将后端返回的 tasks 列表映射到可视化的进度节点。
 * 当后端状态变更时，前端会点亮对应的进度节点并显示当前环节动画。
 *
 * 状态映射规则：
 * - 已完成（completed） → 绿色勾 ✓
 * - 执行中（processing）→ 蓝色脉冲动画
 * - 待处理（pending）   → 灰色空心
 * - 失败（failed）      → 红色叉号
 */
export function ProgressTracker({ tasks, percentage, projectStatus, currentStep }: ProgressTrackerProps) {
  // ─── 构建步骤状态映射 ────────────────────────────────────────
  const stepStatusMap = new Map<TaskTypeEnum, TaskStatusEnum>()
  for (const step of PROGRESS_STEPS) {
    // 找到该类型中状态最靠前的 task
    const matchingTasks = tasks
      .filter((t) => t.task_type === step.type)
      .sort((a, b) => b.sequence_order - a.sequence_order)

    if (matchingTasks.length > 0) {
      stepStatusMap.set(step.type, matchingTasks[0].status)
    } else {
      stepStatusMap.set(step.type, 'pending')
    }
  }

  // ─── 找到当前进行中的步骤（用于动画） ─────────────────────────
  const currentStepIndex = PROGRESS_STEPS.findIndex((step) => {
    const status = stepStatusMap.get(step.type)
    return status === 'processing'
  })

  const isCompleted = projectStatus === 'completed'
  const isFailed = projectStatus === 'failed'

  return (
    <div className="w-full space-y-8">
      {/* ─── 进度条 ──────────────────────────────────────────── */}
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-700 ease-out',
            isCompleted
              ? 'bg-emerald-500'
              : isFailed
                ? 'bg-destructive'
                : 'progress-bar-indeterminate',
          )}
          style={{
            width: isCompleted || isFailed ? '100%' : `${Math.max(percentage, 8)}%`,
          }}
        />
      </div>

      {/* ─── 总体进度百分比 ───────────────────────────────────── */}
      <div className="text-center">
        <span className="text-3xl font-bold tracking-tight">
          {isCompleted ? '100' : isFailed ? '—' : percentage.toFixed(0)}
        </span>
        <span className="ml-1 text-sm text-muted-foreground">%</span>
        <p className="mt-1 text-sm text-muted-foreground">
          {isCompleted
            ? '分析报告已生成完毕'
            : isFailed
              ? '生成过程中出现错误'
              : currentStep?.message ?? '正在生成产品分析报告...'}
        </p>
      </div>

      {/* ─── 步骤指示器 ───────────────────────────────────────── */}
      <div className="relative">
        {/* 连接线 */}
        <div className="absolute left-[18px] top-0 h-full w-px bg-border md:left-1/2 md:-translate-x-px" />

        <div className="space-y-6">
          {PROGRESS_STEPS.map((step, index) => {
            const status = stepStatusMap.get(step.type) ?? 'pending'
            const isActive = status === 'processing'
            const isDone = status === 'completed'
            const isError = status === 'failed'
            const isPending = status === 'pending'

            return (
              <div
                key={step.type}
                className={cn(
                  'relative flex items-center gap-4 transition-opacity duration-300',
                  isPending && !isActive && 'opacity-40',
                )}
              >
                {/* ─── 节点图标 ──────────────────────────────── */}
                <div
                  className={cn(
                    'relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-sm transition-all duration-300',
                    isDone && 'border-emerald-500 bg-emerald-50 text-emerald-600',
                    isActive && 'border-primary bg-primary/10 text-primary',
                    isError && 'border-destructive bg-destructive/10 text-destructive',
                    isPending && !isActive && !isError && 'border-border bg-background text-muted-foreground',
                  )}
                >
                  {isDone ? (
                    <Check className="h-4 w-4" />
                  ) : isActive ? (
                    <span className="relative flex h-3 w-3">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
                      <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
                    </span>
                  ) : (
                    <span className="text-base">{step.icon}</span>
                  )}
                </div>

                {/* ─── 标签 ────────────────────────────────────── */}
                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      'text-sm font-medium',
                      isDone && 'text-emerald-600',
                      isActive && 'text-foreground',
                      isError && 'text-destructive',
                      isPending && 'text-muted-foreground',
                    )}
                  >
                    {step.label}
                    {isActive && (
                      <span className="ml-2 inline-flex gap-0.5">
                        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary" style={{ animationDelay: '0ms' }} />
                        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary" style={{ animationDelay: '300ms' }} />
                        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary" style={{ animationDelay: '600ms' }} />
                      </span>
                    )}
                  </p>
                  {isActive && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      正在进行中...
                    </p>
                  )}
                  {isDone && (
                    <p className="mt-0.5 text-xs text-emerald-600/70">已完成</p>
                  )}
                  {isError && (
                    <p className="mt-0.5 text-xs text-destructive">处理出错</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
