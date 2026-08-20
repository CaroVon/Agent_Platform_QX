/**
 * Header —— 顶栏（面包屑 + 状态徽标，Breathable 低噪音）
 */

import { useLocation } from 'react-router-dom'
import { Github } from 'lucide-react'

const ROUTE_LABELS: Record<string, string> = {
  '/workspace': '产品工作台',
  '/research': '调研中心',
  '/prd': 'PRD 工作室',
  '/design': '设计工作室',
  '/presentation': '演示文稿',
  '/ppt-assets': 'PPT 资产库',
  '/knowledge': '知识库',
  '/templates': '模板',
  '/settings': '设置',
  '/': '控制台',
}

export function Header() {
  const location = useLocation()
  const path = Object.keys(ROUTE_LABELS).find(
    (p) => location.pathname === p || location.pathname.startsWith(`${p}/`),
  )
  const label = ROUTE_LABELS[path ?? ''] ?? '产品工作室'

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/85 px-8 backdrop-blur-sm lg:px-12">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="text-muted-foreground/60">产品工作室</span>
        <span className="text-muted-foreground/40">/</span>
        <span className="font-medium text-foreground">{label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-[11px] text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          服务正常
        </span>
        <a
          href="https://github.com/CaroVon/Agent_Platform_QX"
          target="_blank"
          rel="noreferrer"
          title="GitHub"
          className="text-muted-foreground/60 transition-colors hover:text-foreground"
        >
          <Github className="h-4 w-4" />
        </a>
      </div>
    </header>
  )
}
