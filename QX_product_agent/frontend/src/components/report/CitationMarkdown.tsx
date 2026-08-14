/**
 * ============================================================
 * 带有溯源气泡 (Citation Hover) 的 Markdown 渲染组件
 *
 * 核心交互：
 * - 后端返回的报告内容是包含 [^1], [^2] 角标的 Markdown
 * - 同时返回引用映射字典 { "1": "https://...", "2": "https://..." }
 * - 该组件自定义 react-markdown 渲染器，
 *   将 [^n] 替换为交互式悬浮气泡（Popover/Tooltip）
 * ============================================================
 */

import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { CitationMap } from '@/types/api'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/common/popover'
import { ExternalLink } from 'lucide-react'

interface CitationMarkdownProps {
  /** Markdown 正文（可能包含 [^n] 角标） */
  content: string
  /** 引用映射字典 */
  citationMap: CitationMap
}

/**
 * 将 Markdown 中的 [^n] 替换为可点击的 Popover 角标
 *
 * 实现思路：
 * 1. 用正则替换 [^n] → `<sup data-citation="n">[n]</sup>`
 * 2. react-markdown 的 rehypeRaw 插件允许渲染 HTML
 * 3. 自定义渲染器捕获 sup 元素，渲染 Popover 组件
 *
 * 注意：我们通过 rehypeRaw 直接在 Markdown 中嵌入 HTML，
 *    然后通过自定义渲染器覆写 sup 标签的渲染。
 */
export function CitationMarkdown({ content, citationMap }: CitationMarkdownProps) {
  // ─── 预处理：将 Markdown 中的 [^n] 替换为 HTML sup 标签 ────
  const processedContent = content.replace(
    /\[\^(\d+)\]/g,
    (_, num) => `<sup data-citation="${num}" class="citation-ref">[${num}]</sup>`,
  )

  // ─── 检查是否有引用 ─────────────────────────────────────────
  const hasCitations = Object.keys(citationMap).length > 0

  // ─── 自定义渲染器 ────────────────────────────────────────────
  const components: Components = {
    // 覆写 sup 标签的渲染
    sup: ({ node, children, ...props }) => {
      // 从 data-citation 属性中提取引用编号
      const citationNum = (node?.properties as Record<string, string>)?.['data-citation']

      if (citationNum && hasCitations) {
        const url = citationMap[citationNum]
        if (url) {
          return (
            <CitationBubble citationNum={citationNum} url={url}>
              {children}
            </CitationBubble>
          )
        }
      }

      // 如果没有对应的引用，直接渲染为普通上标
      return <sup className="prose-citation-sup" {...props}>{children}</sup>
    },
    // 让链接在新标签页打开
    a: ({ href, children, ...props }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 underline underline-offset-2 hover:text-blue-800"
        {...props}
      >
        {children}
      </a>
    ),
    // 代码块样式
    code: ({ className, children, ...props }) => {
      const isInline = !className
      if (isInline) {
        return (
          <code className="rounded bg-muted px-1.5 py-0.5 text-sm font-mono" {...props}>
            {children}
          </code>
        )
      }
      return (
        <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-sm">
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      )
    },
  }

  return (
    <div className="prose prose-slate max-w-none dark:prose-invert prose-headings:font-semibold prose-a:no-underline">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  )
}

// ─── 引用气泡子组件 ────────────────────────────────────────────

interface CitationBubbleProps {
  citationNum: string
  url: string
  children: React.ReactNode
}

function CitationBubble({ citationNum, url, children }: CitationBubbleProps) {
  // 提取简短的域名作为展示标题
  let displayTitle = url
  try {
    const parsed = new URL(url)
    displayTitle = parsed.hostname.replace('www.', '')
  } catch {
    // 如果 URL 不合法，直接用原字符串
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <sup className="prose-citation-sup cursor-pointer">{children}</sup>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="center"
        className="w-80 animate-slide-in-right p-0"
      >
        <div className="flex flex-col">
          {/* 气泡头部 */}
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
              {citationNum}
            </span>
            <span className="text-xs font-medium text-muted-foreground">
              参考来源 #{citationNum}
            </span>
          </div>

          {/* 气泡内容 */}
          <div className="space-y-2 px-4 py-3">
            <p className="text-xs text-muted-foreground line-clamp-2 break-all">
              {url}
            </p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              <ExternalLink className="h-3 w-3" />
              打开原文链接
            </a>
          </div>

          {/* 底部来源域名 */}
          <div className="border-t bg-muted/50 px-4 py-2">
            <span className="text-[10px] text-muted-foreground">
              来源: {displayTitle}
            </span>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
