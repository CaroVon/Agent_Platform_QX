/**
 * PageTransition —— 页面切换动效
 *
 * 监听 React Router 的 location.pathname 变化，
 * 当路径变化时为 Outlet 添加 page-enter 动画类，
 * 重新触发动画。
 *
 * 同时为路由切换提供：
 *  - 进入动效：fade + slide-up + 微弱 scale
 *  - 进度条：顶部 1px IBM 蓝细线，进度动画
 *  - 加载 fallback：IBM 蓝骨架 + 进度条
 */

import { useEffect, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

/* ─── 页面切换进度条 ─────────────────────────── */
export function TopProgressBar() {
  const location = useLocation()
  const [active, setActive] = useState(false)

  useEffect(() => {
    setActive(true)
    const t1 = setTimeout(() => setActive(false), 400)
    return () => clearTimeout(t1)
  }, [location.pathname])

  if (!active) return null
  return (
    <div className="pointer-events-none fixed left-0 right-0 top-0 z-[100] h-[2px] overflow-hidden">
      <div
        className="h-full origin-left bg-gradient-to-r from-primary via-accent to-primary"
        style={{
          animation: 'shimmer 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
          transform: 'scaleX(0)',
          width: '100%',
        }}
      />
    </div>
  )
}

/* ─── 页面切换包装 ───────────────────────────── */
export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation()
  return (
    <div key={location.pathname} className="page-enter">
      {children}
    </div>
  )
}

/* ─── 增强的 Suspense Fallback ─────────────────── */
export function LoadingFallback({
  message = '加载中',
}: {
  message?: string
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-5">
        <div className="relative h-14 w-10">
          <div className="absolute inset-0 animate-pulse-soft rounded-md bg-primary/20" />
          <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-primary shadow-elev-glow" />
          <div className="absolute inset-x-0 top-1/2 -mt-1.5 h-3 w-3 animate-pulse-dot rounded-full bg-primary" />
        </div>
        <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
          {message}
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </p>
      </div>
    </div>
  )
}

/* ─── 局部入场动画包装 ───────────────────────── */
export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  return (
    <div
      className={cn('animate-fade-in-up', className)}
      style={{ animationDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}