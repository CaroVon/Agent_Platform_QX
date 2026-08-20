/**
 * ============================================================
 * TerminalTimeline —— 实时运行日志终端
 *
 * 渲染后端 Agent 执行过程中的业务级日志时间轴。
 * 外观设计为深色终端控制台风格，带有自动滚动和增量加载。
 *
 * Props:
 * - logs: 从 API 获取的日志列表
 * - isLoading: 是否正在加载
 * - maxHeight: 最大高度
 * ============================================================
 */

import { useEffect, useRef } from 'react'
import { Loader2, Terminal, AlertTriangle, CheckCircle2, CircleDot, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProjectLogResponse } from '@/types/api'

interface TerminalTimelineProps {
  logs: ProjectLogResponse[]
  isLoading: boolean
  maxHeight?: string
}

/** 根据日志级别返回对应的样式和图标 */
function getLogStyle(level: ProjectLogResponse['level']) {
  switch (level) {
    case 'milestone':
      return {
        dotClass: 'bg-emerald-500 border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]',
        lineClass: 'border-emerald-500/30',
        textClass: 'text-emerald-400',
        icon: CheckCircle2,
      }
    case 'error':
      return {
        dotClass: 'bg-red-500 border-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]',
        lineClass: 'border-red-500/30',
        textClass: 'text-red-400',
        icon: XCircle,
      }
    case 'warn':
      return {
        dotClass: 'bg-amber-500 border-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.3)]',
        lineClass: 'border-amber-500/30',
        textClass: 'text-amber-400',
        icon: AlertTriangle,
      }
    case 'info':
    default:
      return {
        dotClass: 'bg-blue-500 border-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.3)]',
        lineClass: 'border-blue-500/20',
        textClass: 'text-slate-300',
        icon: CircleDot,
      }
  }
}

export function TerminalTimeline({ logs, isLoading, maxHeight = '100%' }: TerminalTimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevLogCount = useRef(0)

  // ─── 新日志到达时自动滚动到底部 ──────────────────────────────
  useEffect(() => {
    if (logs.length > prevLogCount.current && scrollRef.current) {
      const container = scrollRef.current
      // 使用 requestAnimationFrame 确保 DOM 已更新
      requestAnimationFrame(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth',
        })
      })
    }
    prevLogCount.current = logs.length
  }, [logs.length])

  return (
    <div className="flex h-full flex-col">
      {/* ─── 头部 ──────────────────────────────────────────── */}
      <div className="flex items-center gap-2 border-b border-slate-700/50 px-4 py-3">
        <Terminal className="h-4 w-4 text-emerald-400" />
        <span className="text-sm font-medium text-slate-200">运行日志</span>
        {isLoading && (
          <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-slate-400" />
        )}
        <span className="ml-auto text-[10px] text-slate-500">
          {logs.length} 条
        </span>
      </div>

      {/* ─── 时间轴容器 ──────────────────────────────────────── */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        style={{ maxHeight }}
      >
        {logs.length === 0 && !isLoading ? (
          /* ─── 空状态 ─────────────────────────────────────── */
          <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
            <Terminal className="mb-3 h-8 w-8 text-slate-600" />
            <p className="text-xs text-slate-500">暂无运行日志</p>
            <p className="mt-1 text-[10px] text-slate-600">
              Agent 开始执行后，关键步骤将在此实时展示
            </p>
          </div>
        ) : (
          /* ─── 日志列表 ─────────────────────────────────────── */
          <div className="px-3 py-3">
            {logs.map((log) => {
              const style = getLogStyle(log.level)
              const IconComponent = style.icon

              return (
                <div
                  key={log.id}
                  className={cn(
                    'relative flex gap-3 pb-4',
                    'animate-in fade-in slide-in-from-bottom-1 duration-300',
                  )}
                >
                  {/* ── 时间轴线 ─────────────────────────── */}
                  <div className="flex flex-col items-center">
                    <div
                      className={cn(
                        'relative z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 bg-slate-900',
                        style.dotClass,
                      )}
                    >
                      <IconComponent className="h-3 w-3" />
                    </div>
                  </div>

                  {/* ── 日志内容 ──────────────────────────── */}
                  <div className="flex-1 min-w-0 pt-0.5">
                    <p
                      className={cn(
                        'text-xs leading-relaxed font-mono',
                        style.textClass,
                      )}
                    >
                      {log.icon && (
                        <span className="mr-1.5">{log.icon}</span>
                      )}
                      {log.message}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-600">
                      {new Date(log.created_at).toLocaleTimeString('zh-CN', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              )
            })}

            {/* ─── 加载指示器 ──────────────────────────────── */}
            {isLoading && (
              <div className="flex items-center gap-2 pb-3">
                <div className="flex h-6 w-6 items-center justify-center">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                </div>
                <p className="text-[10px] animate-pulse text-slate-500">
                  等待 Agent 执行...
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ─── 底部状态栏 ──────────────────────────────────────── */}
      <div className="border-t border-slate-700/50 px-4 py-1.5">
        <div className="flex items-center gap-3 text-[10px] text-slate-600">
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            里程碑
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            信息
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            警告
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
            错误
          </span>
        </div>
      </div>
    </div>
  )
}
