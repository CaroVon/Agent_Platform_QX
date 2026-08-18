/**
 * ai/AgentStatus —— 单个 AI Agent 的状态行（assistant-ui 风格 + 步骤流转动画）
 */

import { AlertCircle, Check, Loader2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentPhase = 'pending' | 'running' | 'completed' | 'recovered' | 'failed'

const PHASE_META: Record<
  AgentPhase,
  { label: string; iconCls: string; rowCls: string }
> = {
  pending: { label: '等待调度', iconCls: 'border-2 border-border', rowCls: 'text-muted-foreground/70' },
  running: { label: '工作中', iconCls: 'bg-[#24415E] text-white animate-soft-pulse', rowCls: 'text-foreground' },
  completed: { label: '已完成', iconCls: 'bg-emerald-600 text-white', rowCls: 'text-foreground' },
  recovered: { label: '已恢复', iconCls: 'bg-emerald-500 text-white', rowCls: 'text-foreground' },
  failed: { label: '失败', iconCls: 'bg-destructive text-white', rowCls: 'text-destructive' },
}

function TypingDots() {
  return (
    <span className="ml-1 inline-flex items-center text-[#24415E]">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </span>
  )
}

export function AgentStatus({
  name,
  task,
  phase,
  detail,
}: {
  name: string
  task: string
  phase: AgentPhase
  detail?: string
}) {
  const meta = PHASE_META[phase]

  return (
    <div
      key={phase}
      className={cn(
        'flex items-start gap-4 py-3.5 transition-colors',
        phase === 'running' && 'rounded-lg bg-[#24415E]/4 px-2 -mx-2 animate-step-in',
        phase === 'completed' && 'animate-step-in',
        phase === 'recovered' && 'animate-step-in',
        phase === 'failed' && 'animate-step-in',
      )}
    >
      {/* 状态图标 */}
      <span
        className={cn(
          'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-all',
          meta.iconCls,
        )}
      >
        {phase === 'completed' && <Check className="h-3.5 w-3.5" />}
        {phase === 'recovered' && <RefreshCw className="h-3.5 w-3.5" />}
        {phase === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {phase === 'failed' && <AlertCircle className="h-3.5 w-3.5" />}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span className={cn('text-sm font-medium', meta.rowCls)}>{name}</span>
          <span className="text-[11px] text-muted-foreground/70">{meta.label}</span>
        </div>
        <p className="mt-0.5 flex items-center text-[13px] leading-relaxed text-muted-foreground">
          {phase === 'running' && (
            <span className="mr-1.5 inline-block h-3 w-[2px] animate-pulse rounded bg-[#24415E]/50 align-middle" />
          )}
          <span>{task}</span>
          {phase === 'running' && <TypingDots />}
        </p>
        {detail && <p className="mt-0.5 text-[11px] text-muted-foreground/60">{detail}</p>}
      </div>
    </div>
  )
}
