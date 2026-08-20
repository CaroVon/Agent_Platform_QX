/**
 * ============================================================
 * CitationMark —— Tiptap Mark 扩展（替换旧版 Citation.tsx）
 *
 * 核心变更：
 * 1. 使用 `[^数字]` 正则（而非旧版 `[数字]`）
 * 2. 渲染为 `<sup class="citation-badge">N</sup>`
 * 3. 点击角标 → 更新全局 `activeCitationId` 状态
 *    → 右侧 CitationsPanel 自动展示对应引用详情
 * 4. addInputRules() 实时匹配用户输入
 * ============================================================
 */

import {
  Mark,
  mergeAttributes,
  markInputRule,
  markPasteRule,
} from '@tiptap/core'
import type { MarkType } from '@tiptap/pm/model'

// ─── 常量 ──────────────────────────────────────────────────────

/** 匹配 [^数字] 格式 —— 如 [^1], [^23], [^456] */
const CITATION_REGEX = /\[\^(\d+)\]/

/** 全局粘贴/输入匹配 regex（全局匹配） */
const CITATION_GLOBAL_REGEX = /\[\^(\d+)\]/g

// ─── 接口 ──────────────────────────────────────────────────────

export interface CitationMarkOptions {
  /**
   * 引用编号到元信息的映射
   * { "1": { url: "https://...", title: "来源标题" } }
   */
  citationMap: Record<string, { url?: string; title?: string }>
  /** 点击回调：通知外部当前的 citationId 变更 */
  onCitationClick?: (citationId: string) => void
  /** 自定义 HTML 属性 */
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    citationMark: {
      /** 切换引用 Mark */
      toggleCitationMark: () => ReturnType
      /** 设置引用 Mark */
      setCitationMark: (citationId: string) => ReturnType
    }
  }
}

// ─── 输入规则 ──────────────────────────────────────────────────

/**
 * 当用户输入 `[^数字]` 时自动应用 CitationMark
 */
function citationInputRule(markType: MarkType) {
  return markInputRule({
    find: CITATION_REGEX,
    type: markType,
    getAttributes: (match: RegExpMatchArray) => ({
      citationId: match[1],
    }),
  })
}

/**
 * 粘贴时自动解析 `[^数字]`
 */
function citationPasteRule(markType: MarkType) {
  return markPasteRule({
    find: CITATION_GLOBAL_REGEX,
    type: markType,
    getAttributes: (match: RegExpMatchArray) => ({
      citationId: match[1],
    }),
  })
}

// ─── 扩展定义 ──────────────────────────────────────────────────

export const CitationMark = Mark.create<CitationMarkOptions>({
  name: 'citationMark',

  addOptions() {
    return {
      citationMap: {},
      onCitationClick: undefined,
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
        tag: 'sup[data-citation-id]',
      },
    ]
  },

  /**
   * 渲染为可点击的 <sup> 角标
   *
   * ```html
   * <sup
   *   data-citation-id="1"
   *   class="citation-badge"
   *   title="点击查看来源"
   * >1</sup>
   * ```
   */
  renderHTML({ mark, HTMLAttributes }) {
    const citationId = mark.attrs.citationId as string | undefined
    const meta = citationId ? this.options.citationMap[citationId] : undefined

    return [
      'sup',
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        'data-citation-id': citationId,
        class: 'citation-badge',
        title: meta?.title || `引用 [^${citationId}]`,
        // 通过自定义属性传递 onclick —— 由全局事件委托处理
        style: 'cursor: pointer; color: #6366f1; font-weight: 600;',
      }),
      citationId || '',
    ]
  },

  addCommands() {
    return {
      toggleCitationMark:
        () =>
        ({ commands }) => {
          return commands.toggleMark(this.name)
        },
      setCitationMark:
        (citationId: string) =>
        ({ commands }) => {
          return commands.setMark(this.name, { citationId })
        },
    }
  },

  addInputRules() {
    return [citationInputRule(this.type)]
  },

  addPasteRules() {
    return [citationPasteRule(this.type)]
  },
})
