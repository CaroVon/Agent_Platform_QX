/**
 * ============================================================
 * Citation —— Tiptap 引用标注 Mark 扩展
 *
 * 渲染形如 [1] 的引用角标，hover 时显示 Tooltip。
 *
 * 使用方式：
 * - 在内容文本中标记 `[数字]` 格式
 * - 通过 `CitationOptions.citationMap` 提供 URL 映射
 *
 * TODO:
 * - 集成 BubbleMenu：选中引用角标 → 弹出编辑/删除面板
 * - 点击引用 → 在右侧面板展示对应 URL
 * ============================================================
 */

import { Mark, mergeAttributes } from '@tiptap/core'

export interface CitationOptions {
  /**
   * 引用编号到 URL 的映射
   * { "1": "https://example.com/article1" }
   */
  citationMap: Record<string, string>
  /** CSS class */
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    citation: {
      toggleCitation: () => ReturnType
      setCitation: (citationId: string) => ReturnType
    }
  }
}

export const Citation = Mark.create<CitationOptions>({
  name: 'citation',

  addOptions() {
    return {
      citationMap: {},
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      citationId: {
        default: null,
        parseHTML: (el) => (el as HTMLElement).getAttribute('data-citation-id'),
        renderHTML: (attrs) => {
          if (!attrs.citationId) return {}
          return { 'data-citation-id': attrs.citationId as string }
        },
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-citation-id]',
      },
    ]
  },

  renderHTML({ mark, HTMLAttributes }) {
    const citationId = mark.attrs.citationId as string | undefined
    const url = citationId ? this.options.citationMap[citationId] : undefined

    return [
      'a',
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        href: url || '#',
        target: '_blank',
        rel: 'noopener noreferrer',
        class: 'citation-sup',
        title: url || `引用 [${citationId}]`,
        'data-citation-id': citationId,
      }),
      `[${citationId}]`,
    ]
  },

  addCommands() {
    return {
      toggleCitation:
        () =>
        ({ commands }) => {
          return commands.toggleMark(this.name)
        },
      setCitation:
        (citationId: string) =>
        ({ commands }) => {
          return commands.setMark(this.name, { citationId })
        },
    }
  },
})
