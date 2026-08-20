import { cn } from '@/lib/utils'
import type { ProjectStatusEnum, TaskStatusEnum } from '@/types/api'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | 'default'
    | 'secondary'
    | 'outline'
    | 'success'
    | 'warning'
    | 'destructive'
    | 'info'
    | 'processing'
  children?: React.ReactNode
}

export function Badge({
  className,
  variant = 'default',
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium leading-none transition-colors',
        {
          'bg-primary/15 text-primary': variant === 'default',
          'bg-secondary text-secondary-foreground': variant === 'secondary',
          'border border-border text-foreground': variant === 'outline',
          'bg-success/15 text-success': variant === 'success',
          'bg-warning/15 text-warning': variant === 'warning',
          'bg-destructive/15 text-destructive': variant === 'destructive',
          'bg-accent/15 text-accent': variant === 'info',
          'bg-primary/15 text-primary animate-pulse-dot': variant === 'processing',
        },
        className,
      )}
      {...props}
    >
      {variant === 'processing' && (
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
      )}
      {children}
    </span>
  )
}

const projectBadgeVariant: Record<ProjectStatusEnum, BadgeProps['variant']> = {
  preparing_data: 'processing',
  waiting_for_sources: 'warning',
  preparing_outline: 'processing',
  waiting_for_outline: 'warning',
  drafting: 'processing',
  completed: 'success',
  failed: 'destructive',
}

const projectBadgeLabel: Record<ProjectStatusEnum, string> = {
  preparing_data: '资料搜索中',
  waiting_for_sources: '待审核资料',
  preparing_outline: '大纲生成中',
  waiting_for_outline: '待确认大纲',
  drafting: 'AI 撰写中',
  completed: '已完成',
  failed: '失败',
}

export function ProjectStatusBadge({ status }: { status: ProjectStatusEnum }) {
  const variant = projectBadgeVariant[status]
  return <Badge variant={variant}>{projectBadgeLabel[status]}</Badge>
}

const taskBadgeVariant: Record<TaskStatusEnum, BadgeProps['variant']> = {
  pending: 'outline',
  processing: 'processing',
  completed: 'success',
  failed: 'destructive',
}

const taskBadgeLabel: Record<TaskStatusEnum, string> = {
  pending: '等待中',
  processing: '执行中',
  completed: '已完成',
  failed: '失败',
}

export function TaskStatusBadge({ status }: { status: TaskStatusEnum }) {
  const variant = taskBadgeVariant[status]
  return <Badge variant={variant}>{taskBadgeLabel[status]}</Badge>
}