/**
 * PRDViewer —— PRD 阅读器
 * 渲染 prd_sections（结构化章节：标题 + Markdown 正文）。
 *
 * 正文为 Markdown 文本（不含 HTML/CSS），由 react-markdown 渲染，
 * 样式由本组件控制 —— 符合"LLM 不生成 HTML/CSS"的约定。
 */

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PRDSection } from '@/types/studio'

export function PRDViewer({ sections }: { sections: PRDSection[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <FileText className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">PRD 文档</h3>
      </div>

      <div className="space-y-2">
        {sections.map((section, index) => {
          const isOpen = openIndex === index
          return (
            <div key={section.title} className="overflow-hidden rounded-lg border">
              <button
                type="button"
                onClick={() => setOpenIndex(isOpen ? null : index)}
                className="flex w-full items-center justify-between bg-secondary/50 px-4 py-3 text-left"
              >
                <span className="text-sm font-medium">
                  {index + 1}. {section.title}
                </span>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 text-muted-foreground transition-transform',
                    isOpen && 'rotate-180',
                  )}
                />
              </button>
              {isOpen && (
                <div className="prose prose-sm max-w-none px-4 py-3 text-sm leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {section.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
