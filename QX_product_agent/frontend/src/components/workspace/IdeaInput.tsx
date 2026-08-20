/**
 * IdeaInput —— 大居中产品想法输入区（AI 创作画布核心交互）
 */

import { Loader2, Rocket, Sparkles } from 'lucide-react'
import { Button } from '@/components/common/button'

export function IdeaInput({
  value,
  onChange,
  onSubmit,
  creating,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  creating: boolean
}) {
  return (
    <div className="relative flex flex-col items-center py-10 text-center">
      <div className="animate-breathe mb-6 flex h-12 w-12 items-center justify-center rounded-2xl border bg-card">
        <Sparkles className="h-5 w-5 text-[#24415E]" />
      </div>

      <h1 className="font-serif max-w-2xl text-3xl font-semibold leading-snug tracking-tight lg:text-4xl">
        Describe the product you want to build
      </h1>
      <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground">
        你的 AI 产品团队（研究 / 产品 / 设计 / 演示）将围绕这个想法展开完整工作流。
      </p>

      {/* 输入行：与卡片同宽（不再限宽） */}
      <div className="mt-8 flex w-full gap-3">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
          placeholder='例如: "为新中产打造国潮风格的智能床品"'
          className="h-12 flex-1 rounded-xl border bg-card px-5 text-sm outline-none transition-shadow focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button size="lg" onClick={onSubmit} disabled={creating || !value.trim()} className="h-12 px-7">
          {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
          Generate
        </Button>
      </div>
    </div>
  )
}
