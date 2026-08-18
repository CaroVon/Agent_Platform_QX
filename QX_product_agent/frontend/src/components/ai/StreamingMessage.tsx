/**
 * ai/StreamingMessage —— 生成中的流式状态信息
 */

import { useEffect, useState } from 'react'

const MESSAGES = [
  'AI 产品团队正在协作…',
  '研究市场格局，分析竞品态势…',
  '沉淀产品策略与用户画像…',
  '编排演示叙事，评审视觉质量…',
  '汇总结构化资产包…',
]

export function StreamingMessage({
  active,
  latestEvent,
}: {
  active: boolean
  /** 最新真实执行事件：有数据时展示真实过程，替代轮播文案 */
  latestEvent?: { node: string; status: string; detail?: string } | undefined
}) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!active || latestEvent) return
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % MESSAGES.length)
    }, 3200)
    return () => window.clearInterval(timer)
  }, [active, latestEvent])

  if (!active) return null

  const realText = latestEvent
    ? `${latestEvent.node} · ${latestEvent.status}${latestEvent.detail ? ` — ${latestEvent.detail}` : ''}`
    : MESSAGES[index]

  return (
    <div className="flex items-center gap-3 rounded-xl border bg-card px-5 py-3.5">
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#24415E]/70"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </span>
      <span key={latestEvent ? `real-${realText}` : index} className="text-sm text-muted-foreground">
        {realText}
      </span>
    </div>
  )
}
