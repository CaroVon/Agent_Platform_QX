/**
 * ============================================================
 * dataTransform —— 数据转换层 (Phase 3 v5)
 *
 * v5 重构（商业风格 + 内容密度优化）：
 * - 商业风格 slide 模板：左侧品牌色条 + 页眉(Logo/标题/页码) + 页脚
 * - 章节级渲染：配合后端 section-level DocumentBlock，减少碎片页
 * - 引用页尾优化：分隔线 + 紧凑排版 + 溢出检测
 * - 目录页：封面后自动插入 TOC 页
 * - 全局引用编号：跨章节 URL 去重 reconcile
 * - 双宽度高度估算：CJK/拉丁分别计算，减少提前分页
 * - 页码渲染：页眉右侧显示 Page N / M
 * - 移除冗余续页后缀：(续N) → 仅保持原标题
 * ============================================================
 */

import { marked, Token, Tokens } from 'marked'
import type { DocumentBlockResponse } from '@/types/api'
import type { CanvasElement } from '@/store/useCanvasStore'

// ══════════════════════════════════════════════════════════════
// 类型定义
// ══════════════════════════════════════════════════════════════

export interface KonvaSlide {
  pageNumber: number
  sectionTitle: string
  elements: CanvasElement[]
}

// ══════════════════════════════════════════════════════════════
// Layout Diversity — 类型定义 (v6)
// ══════════════════════════════════════════════════════════════

/** 12 种要点排列格式 */
export type ArrangementFormat =
  | 'vertical'          // 竖向排列（现有方式，稳定锚点）
  | 'bracket'           // 括弧排列
  | 'table_compact'     // 表格排列
  | 'horizontal_flow'   // 横向排列
  | 'card_grid'         // 卡片网格
  | 'connected_lines'   // 线段链接排列
  | 'numbered_circles'  // 编号圆圈
  | 'tag_flow'          // 标签流
  | 'callout_boxes'     // 标注框
  | 'checklist'         // 清单列表
  | 'timeline'          // 时间轴
  | 'comparison_cols'   // 对比列

/** 内容层级节点 — 从 flat tokens 构建的树模型 */
export interface ContentNode {
  type: string           // 'heading' | 'list_item' | 'paragraph' | 'table' | 'blockquote' | 'code'
  depth: number          // heading depth (2=h2, 3=h3, ...) 或 list nesting depth
  text: string           // plain text (stripMarkdown 之后)
  token: Token    // 原始 marked token（渲染时用）
  children: ContentNode[]
  breakBefore?: boolean  // 分页标记：在此节点前强制分页
  parent?: ContentNode   // 父节点引用（单级向上分页用）
}

/** 排列渲染器上下文 */
export interface ArrangementContext {
  contentX: number
  availableWidth: number
  isLeafGroup: boolean
  seedValue: number
}

// ══════════════════════════════════════════════════════════════
// 画布物理常量（16:9）
// ══════════════════════════════════════════════════════════════

export const CANVAS_WIDTH = 1280
export const CANVAS_HEIGHT = 720

/** 品牌色系 */
const BRAND = {
  primary: '#2d7cf6',    // 主品牌色（科技蓝）
  primaryLight: '#6366f1', // 前端 accent（indigo，保持兼容）
  dark: '#0f1117',       // 深色背景
  heading: '#0f172a',    // 标题色
  body: '#334155',       // 正文色
  muted: '#94a3b8',      // 次要文字
  mutedLight: '#cbd5e1', // 最淡次要
  divider: '#e2e8f0',    // 细分割线
  footerBg: '#f1f5f9',   // 页脚背景
  white: '#ffffff',
}

// ══════════════════════════════════════════════════════════════
// 布局常量（v5 商业风格）
// ══════════════════════════════════════════════════════════════

const SIDEBAR_WIDTH = 6          // 左侧品牌色条宽度
const HEADER_HEIGHT = 56         // 页眉区域高度
const FOOTER_HEIGHT = 24         // 页脚区域高度
const CONTENT_START_Y = 68       // 正文起始 Y（页眉分隔线下方）
const CITATION_ZONE_Y = 632      // 引用区起始 Y（参考文献固定钉在此处）
const CONTENT_END_Y = 624        // 正文截止 Y（为页底引用区预留空间，不许正文侵入）
const CONTENT_WIDTH = 1140       // 正文内容宽度（1280 - 左侧边距60 - 右侧边距80）
const BODY_FONT_SIZE = 18
const HEADING_FONT_SIZE = 24
const CITATION_FONT_SIZE = 12
const MAX_CITATION_TEXT_HEIGHT = CANVAS_HEIGHT - FOOTER_HEIGHT - 4 - (CITATION_ZONE_Y + 6)
const IMAGE_RENDER_WIDTH = 800
const IMAGE_RENDER_HEIGHT = 450
const BLOCKQUOTE_BAR_WIDTH = 4

// 图片占位框尺寸（每个章节首页右侧预留，正文环绕其下方）
const PLACEHOLDER_WIDTH = 420
const PLACEHOLDER_HEIGHT = 236

/** 内容 X 坐标（sidebar 右侧留白后） */
const CONTENT_X = 60
/** 列表缩进 X 坐标 */
const LIST_X = 80

// ══════════════════════════════════════════════════════════════
// 工具函数
// ══════════════════════════════════════════════════════════════

let _elementIdCounter = 0

function genId(): string {
  _elementIdCounter += 1
  return `el_${Date.now()}_${_elementIdCounter}_${Math.random().toString(36).substring(2, 6)}`
}

/**
 * 估算文本在 Canvas 中占据的高度（v5 双宽度字符计数版）。
 *
 * 对 CJK 字符和拉丁/数字分别计算宽度，比之前的全中文假设
 * 更准确，减少对中英混排段落的过高估算和提前分页。
 */
function isWideChar(ch: string): boolean {
  return /[一-鿿㐀-䶿぀-ヿ㄰-㆏　-〿＀-￯]/u.test(ch)
}

function estimateTextHeight(text: string, fontSize: number, width: number): number {
  const safeWidth = Math.max(width * 0.97, fontSize)
  const rawLines = text.split(/\r?\n/)
  let totalLines = 0

  for (const rawLine of rawLines) {
    const line = rawLine || ' '
    let totalCharWidth = 0
    for (const ch of line) {
      if (/\s/.test(ch)) {
        totalCharWidth += fontSize * 0.32
      } else if (isWideChar(ch)) {
        totalCharWidth += fontSize * 1.0 // CJK / 全角字符
      } else if (/[A-Z0-9]/.test(ch)) {
        totalCharWidth += fontSize * 0.62
      } else {
        totalCharWidth += fontSize * 0.58 // 拉丁 / 数字 / 标点半角
      }
    }
    totalLines += Math.max(Math.ceil(totalCharWidth / safeWidth), 1)
  }

  return Math.ceil(totalLines * (fontSize * 1.48) + 4)
}

function estimateCitationFooterHeight(
  activeCitations: Set<string>,
  citationsDict: Record<string, string>,
): number {
  if (activeCitations.size === 0) return 0

  const citationText = buildCitationText(activeCitations, citationsDict)
  if (!citationText) return 0

  const textHeight = estimateTextHeight(citationText, CITATION_FONT_SIZE, CONTENT_WIDTH)
  return Math.min(textHeight + 14, MAX_CITATION_TEXT_HEIGHT)
}

function estimateNodeCitations(node: ContentNode): Set<string> {
  const citations = new Set<string>()
  const visit = (current: ContentNode) => {
    for (const c of scanCitations(current.text)) citations.add(c)
    for (const child of current.children) visit(child)
  }
  visit(node)
  return citations
}

function mergeCitationSets(...sets: Array<Set<string>>): Set<string> {
  const merged = new Set<string>()
  for (const set of sets) {
    for (const item of set) merged.add(item)
  }
  return merged
}

function getCurrentPageCapacity(
  state: SlideBuildState,
  citationsDict: Record<string, string>,
  pendingCitations?: Set<string>,
): number {
  const reservedCitationHeight = estimateCitationFooterHeight(
    mergeCitationSets(state.activeCitations, pendingCitations || new Set<string>()),
    citationsDict,
  )
  const bodyBottom = reservedCitationHeight > 0
    ? Math.min(CONTENT_END_Y, CITATION_ZONE_Y - reservedCitationHeight - 8)
    : CONTENT_END_Y
  return bodyBottom - state.currentY
}

function getPageCapacityLimit(
  citationsDict: Record<string, string>,
  pendingCitations?: Set<string>,
): number {
  const reservedCitationHeight = estimateCitationFooterHeight(
    pendingCitations || new Set<string>(),
    citationsDict,
  )
  const bodyBottom = reservedCitationHeight > 0
    ? Math.min(CONTENT_END_Y, CITATION_ZONE_Y - reservedCitationHeight - 8)
    : CONTENT_END_Y
  return bodyBottom - CONTENT_START_Y
}

function isArrangeableLeaf(node: ContentNode): boolean {
  return node.type === 'list_item' && node.text.trim().length > 0 && node.children.every((child) => child.type !== 'list_item')
}

function isArrangeableGroup(node: ContentNode): boolean {
  const listChildren = node.children.filter((child) => child.type === 'list_item' && child.text.trim())
  if (listChildren.length < 2) return false
  return listChildren.every((child) => isArrangeableLeaf(child))
}

function looksLikeTimeline(text: string): boolean {
  return /(Q[1-4]|\b20\d{2}\b|阶段|里程碑|时间线|step\s*\d+|第[一二三四五六七八九十]阶段)/i.test(text)
}

function looksLikeKeyValue(text: string): boolean {
  return /[:：]/.test(text)
}

function looksLikeComparisonTitle(text: string): boolean {
  return /(对比|比较|方案|选型|路径|版本|档位|组合|矩阵)/.test(text)
}

function estimateArrangementHeight(node: ContentNode, arrangement: ArrangementFormat): number {
  const items = node.children.filter((child) => child.type === 'list_item' && child.text.trim())
  const labelHeight = node.text.trim()
    ? estimateTextHeight(node.text, BODY_FONT_SIZE, CONTENT_WIDTH) + 12
    : 0

  if (items.length === 0) return estimateVerticalNodeHeight(node)

  switch (arrangement) {
    case 'card_grid': {
      const cols = items.length <= 3 ? 1 : items.length <= 6 ? 2 : 3
      const cardWidth = Math.floor((CONTENT_WIDTH - CARD_GAP * (cols - 1)) / cols)
      const cardHeights = items.map((item) => Math.max(
        estimateTextHeight(item.text, BODY_FONT_SIZE, cardWidth - CARD_PADDING_X * 2) + CARD_PADDING_Y * 2 + 8,
        CARD_MIN_HEIGHT,
      ))
      let total = 0
      for (let row = 0; row < Math.ceil(items.length / cols); row++) {
        const rowHeights = cardHeights.slice(row * cols, row * cols + cols)
        total += Math.max(...rowHeights, CARD_MIN_HEIGHT)
      }
      total += Math.max(Math.ceil(items.length / cols) - 1, 0) * CARD_GAP
      return labelHeight + total + 8
    }
    case 'comparison_cols': {
      const nCols = Math.min(items.length, 3)
      const colW = Math.floor((CONTENT_WIDTH - (nCols - 1) * 12) / nCols)
      const maxColH = Math.max(...items.slice(0, nCols).map((item) => estimateTextHeight(item.text, BODY_FONT_SIZE, colW - 16) + 40))
      return labelHeight + Math.max(maxColH, 100) + 12
    }
    case 'timeline': {
      let total = 0
      for (const item of items) {
        const textH = estimateTextHeight(item.text, BODY_FONT_SIZE, CONTENT_WIDTH - TIMELINE_LINE_X_OFFSET - 30)
        total += Math.max(textH + 12, 40)
      }
      return labelHeight + total + 16
    }
    case 'horizontal_flow': {
      const lineHeight = BODY_FONT_SIZE * 1.35 + 6
      let rows = 1
      let rowWidth = 0
      for (let i = 0; i < items.length; i++) {
        const suffix = i < items.length - 1 ? '•' : ''
        const tokenWidth = estimateTextWidth(items[i].text + suffix, BODY_FONT_SIZE) + 12
        if (rowWidth > 0 && rowWidth + tokenWidth > CONTENT_WIDTH) {
          rows += 1
          rowWidth = 0
        }
        rowWidth += tokenWidth
      }
      return labelHeight + rows * lineHeight + 12
    }
    case 'tag_flow': {
      let rows = 1
      let rowWidth = 0
      for (const item of items) {
        const tagW = estimateTextWidth(item.text, TAG_FONT_SIZE) + TAG_PADDING_X * 2
        const fullW = tagW + 8
        if (rowWidth > 0 && rowWidth + fullW > CONTENT_WIDTH) {
          rows += 1
          rowWidth = 0
        }
        rowWidth += fullW
      }
      return labelHeight + rows * (TAG_FONT_SIZE * 1.35 + TAG_PADDING_Y * 2 + 6) + 6
    }
    case 'table_compact': {
      const hasKv = items.some((item) => looksLikeKeyValue(item.text))
      const rowH = 32
      const rows = items.length + 1
      return labelHeight + rows * rowH + 16 + (hasKv ? 0 : 0)
    }
    case 'numbered_circles':
    case 'checklist':
    case 'callout_boxes':
    case 'connected_lines':
    case 'bracket':
      return estimateVerticalNodeHeight(node) + (ARRANGEMENT_OVERHEAD[arrangement] || 0)
    default:
      return estimateVerticalNodeHeight(node)
  }
}

function pickArrangementCandidates(node: ContentNode): ArrangementFormat[] {
  const items = node.children.filter((child) => child.type === 'list_item' && child.text.trim())
  const itemTexts = items.map((item) => item.text.trim())
  const itemCount = itemTexts.length
  const avgLen = itemCount
    ? itemTexts.reduce((sum, text) => sum + text.length, 0) / itemCount
    : node.text.trim().length

  if (itemTexts.some((text) => looksLikeTimeline(text))) {
    return ['timeline', 'numbered_circles', 'connected_lines']
  }
  if (itemTexts.some((text) => looksLikeKeyValue(text))) {
    return itemCount <= 3
      ? ['comparison_cols', 'table_compact', 'callout_boxes']
      : ['table_compact', 'card_grid', 'callout_boxes']
  }
  if (looksLikeComparisonTitle(node.text) || itemCount === 2) {
    return ['comparison_cols', 'card_grid', 'horizontal_flow']
  }
  if (itemCount >= 6 && avgLen <= 28) {
    return ['tag_flow', 'checklist', 'numbered_circles']
  }
  if (avgLen <= 24) {
    return ['card_grid', 'tag_flow', 'horizontal_flow', 'numbered_circles']
  }
  if (avgLen <= 72) {
    return ['card_grid', 'callout_boxes', 'checklist', 'connected_lines']
  }
  return ['callout_boxes', 'checklist', 'bracket', 'vertical']
}

function getArrangementWidth(arrangement: ArrangementFormat, node: ContentNode): number {
  if (arrangement === 'card_grid') {
    const items = node.children.filter((child) => child.type === 'list_item' && child.text.trim())
    const cols = items.length <= 3 ? 1 : items.length <= 6 ? 2 : 3
    return Math.floor((CONTENT_WIDTH - CARD_GAP * (cols - 1)) / cols) - CARD_PADDING_X * 2
  }
  if (arrangement === 'comparison_cols') {
    const items = node.children.filter((child) => child.type === 'list_item' && child.text.trim())
    const nCols = Math.min(items.length, 3)
    return Math.floor((CONTENT_WIDTH - (nCols - 1) * 12) / nCols) - 16
  }
  if (arrangement === 'timeline') return CONTENT_WIDTH - TIMELINE_LINE_X_OFFSET - 30
  if (arrangement === 'tag_flow') return CONTENT_WIDTH
  if (arrangement === 'horizontal_flow') return CONTENT_WIDTH
  return CONTENT_WIDTH - 20
}

function getPrimaryBodyWidth(node: ContentNode): number {
  if (node.type === 'list_item' && node.text.trim()) return CONTENT_WIDTH - 20
  if (node.type === 'heading') return CONTENT_WIDTH
  if (node.type === 'paragraph') return CONTENT_WIDTH
  if (node.type === 'blockquote') return CONTENT_WIDTH - 20
  return CONTENT_WIDTH
}

function getNodeOwnHeight(node: ContentNode, arrangement?: ArrangementFormat): number {
  if (node.type === 'heading') {
    const headingFontSize = node.depth <= 2 ? 24 : node.depth === 3 ? 20 : 18
    return estimateTextHeight(node.text, headingFontSize, CONTENT_WIDTH) +
      (node.depth <= 2 ? 16 : node.depth === 3 ? 12 : 10)
  }
  if (node.type === 'list_item') {
    if (!node.text.trim()) return 0
    const width = arrangement ? getArrangementWidth(arrangement, node) : CONTENT_WIDTH - 20
    return estimateTextHeight(node.text, BODY_FONT_SIZE, width) + 8
  }
  if (node.type === 'paragraph') return estimateTextHeight(node.text, BODY_FONT_SIZE, CONTENT_WIDTH) + 12
  return estimateTokenHeight(node.token)
}

function getRequiredHeightForNode(node: ContentNode): number {
  if (node.type === 'list_item' && isArrangeableGroup(node)) {
    const arrangement = getNodeArrangement(node, hashString(node.text || node.token.raw || node.type))
    return estimateArrangementHeight(node, arrangement)
  }
  return estimateNodeHeight(node)
}

function ensureNodeFitsPage(
  node: ContentNode,
  state: SlideBuildState,
  citationsDict: Record<string, string>,
  flushCurrentPage: () => void,
): void {
  if (state.currentY <= CONTENT_START_Y) return
  const pendingCitations = estimateNodeCitations(node)
  const requiredHeight = getRequiredHeightForNode(node)
  if (requiredHeight <= getCurrentPageCapacity(state, citationsDict, pendingCitations)) return
  flushCurrentPage()
}

function updateNodePageBreaks(
  node: ContentNode,
  state: SlideBuildState,
  citationsDict: Record<string, string>,
): void {
  if (!isArrangeableGroup(node) || state.currentY <= CONTENT_START_Y) return
  const nodeH = getRequiredHeightForNode(node)
  const pendingCitations = estimateNodeCitations(node)
  const remainingSpace = getCurrentPageCapacity(state, citationsDict, pendingCitations)
  if (nodeH > remainingSpace && node.parent && !node.parent.breakBefore) {
    node.parent.breakBefore = true
  }
}

function getNodeArrangement(node: ContentNode, parentSeed: number): ArrangementFormat {
  return pickArrangement(node, parentSeed)
}

function pickArrangement(node: ContentNode, parentSeed: number): ArrangementFormat {
  const candidates = pickArrangementCandidates(node)
  const rng = mulberry32(hashString(node.text || node.token.raw || node.type) + parentSeed)
  const idx = Math.floor(rng() * candidates.length)
  return candidates[idx]
}

function isVerticalTextArrangement(arrangement: ArrangementFormat): boolean {
  return arrangement === 'vertical' || arrangement === 'callout_boxes' || arrangement === 'checklist' || arrangement === 'numbered_circles'
}

function shouldFallbackArrangement(
  node: ContentNode,
  arrangement: ArrangementFormat,
  currentY: number,
): boolean {
  if (arrangement === 'vertical') return false
  const estimated = estimateArrangementHeight(node, arrangement)
  return currentY + estimated > CONTENT_END_Y && estimated > CONTENT_END_Y - CONTENT_START_Y
}

function getNodeVisualStyle(node: ContentNode): { fill: string; fontWeight?: string; fontSize?: number } {
  if (node.type === 'heading') {
    return {
      fill: node.depth <= 2 ? BRAND.heading : BRAND.body,
      fontWeight: node.depth <= 3 ? 'bold' : '500',
      fontSize: node.depth <= 2 ? 24 : node.depth === 3 ? 20 : 18,
    }
  }
  if (node.type === 'list_item') {
    return {
      fill: node.depth <= 3 ? BRAND.heading : BRAND.body,
      fontWeight: node.depth <= 3 ? 'bold' : undefined,
      fontSize: node.depth <= 3 ? BODY_FONT_SIZE : BODY_FONT_SIZE,
    }
  }
  return { fill: BRAND.body }
}

function renderNodeTextBlock(
  node: ContentNode,
  state: SlideBuildState,
  width: number,
  options?: { x?: number; fontSize?: number; fontWeight?: string; fill?: string; marginBottom?: number },
): number {
  if (!node.text.trim()) return 0
  const style = getNodeVisualStyle(node)
  const fontSize = options?.fontSize || style.fontSize || BODY_FONT_SIZE
  const h = estimateTextHeight(node.text, fontSize, width)
  state.elements.push({
    id: genId(),
    type: 'text',
    x: options?.x ?? CONTENT_X,
    y: state.currentY,
    width,
    height: h + 4,
    text: node.text,
    fontSize,
    fontWeight: options?.fontWeight || style.fontWeight,
    fill: options?.fill || style.fill,
  })
  const advance = h + (options?.marginBottom ?? 8)
  state.currentY += advance
  return advance
}

function renderStructuredNode(
  node: ContentNode,
  state: SlideBuildState,
  parentSeed: number,
  options?: {
    ensureSpace?: (requiredHeight: number) => void
  },
): void {
  for (const c of scanCitations(node.text)) state.activeCitations.add(c)

  if (node.type === 'heading') {
    const headingStyle = getNodeVisualStyle(node)
    const totalH = getNodeOwnHeight(node)
    options?.ensureSpace?.(totalH)
    state.elements.push({
      id: genId(),
      type: 'text',
      x: CONTENT_X, y: state.currentY,
      width: CONTENT_WIDTH, height: totalH,
      text: node.text,
      fontSize: headingStyle.fontSize || BODY_FONT_SIZE,
      fontWeight: headingStyle.fontWeight,
      fill: headingStyle.fill,
    })
    state.currentY += totalH
    renderTreeWalk(node.children, state, parentSeed + hashString(node.text), options)
    return
  }

  if (node.type === 'list_item' && isArrangeableGroup(node)) {
    const pickedArrangement = getNodeArrangement(node, parentSeed)
    const arrangement = shouldFallbackArrangement(node, pickedArrangement, state.currentY)
      ? 'vertical'
      : pickedArrangement
    options?.ensureSpace?.(estimateArrangementHeight(node, arrangement))
    const ctx: ArrangementContext = {
      contentX: CONTENT_X,
      availableWidth: CONTENT_WIDTH,
      isLeafGroup: true,
      seedValue: parentSeed + hashString(node.text),
    }
    ARRANGEMENT_RENDERERS[arrangement](node, state, ctx)
    return
  }

  if (node.type === 'list_item') {
    if (node.children.length > 0) {
      if (node.text.trim()) {
        const required = getNodeOwnHeight(node)
        options?.ensureSpace?.(required)
        const accentColor = node.depth <= 3 ? BRAND.primary : BRAND.divider
        const boxFill = node.depth <= 3 ? '#f8fbff' : '#ffffff'
        const textX = CONTENT_X + (node.depth - 2) * 18
        const textW = CONTENT_WIDTH - (node.depth - 2) * 18 - 24
        const h = estimateTextHeight(node.text, BODY_FONT_SIZE, textW - 22)
        const blockH = h + 14
        state.elements.push({
          id: genId(),
          type: 'rect',
          x: textX,
          y: state.currentY,
          width: textW,
          height: blockH,
          fill: boxFill,
          stroke: BRAND.divider,
          strokeWidth: node.depth <= 3 ? 1 : 0.5,
          radius: 6,
          name: node.depth <= 3 ? 'arrangement-decor' : undefined,
        } as CanvasElement)
        state.elements.push({
          id: genId(),
          type: 'rect',
          x: textX,
          y: state.currentY,
          width: 4,
          height: blockH,
          fill: accentColor,
          radius: 4,
          name: 'arrangement-decor',
        })
        state.elements.push({
          id: genId(),
          type: 'text',
          x: textX + 16,
          y: state.currentY + 6,
          width: textW - 22,
          height: h + 4,
          text: node.text,
          fontSize: BODY_FONT_SIZE,
          fontWeight: node.depth <= 3 ? 'bold' : undefined,
          fill: BRAND.body,
        })
        state.currentY += blockH + 10
      }
      renderTreeWalk(node.children, state, parentSeed + hashString(node.text), options)
      return
    }

    if (node.text.trim()) {
      options?.ensureSpace?.(getNodeOwnHeight(node))
      renderBulletItem(node.text, state, node.depth - 2)
    }
    return
  }

  options?.ensureSpace?.(estimateTokenHeight(node.token))
  processToken(node.token, state)
}

function renderSectionCallout(
  text: string,
  state: SlideBuildState,
  options?: { ensureSpace?: (requiredHeight: number) => void },
): void {
  const plain = stripMarkdown(text)
  if (!plain.trim()) return
  const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH - BLOCKQUOTE_BAR_WIDTH - 24)
  const blockH = h + 18
  options?.ensureSpace?.(blockH + 8)
  state.elements.push({
    id: genId(), type: 'rect',
    x: CONTENT_X, y: state.currentY,
    width: CONTENT_WIDTH, height: blockH,
    fill: '#f8fafc',
    stroke: BRAND.divider,
    strokeWidth: 0.5,
    radius: 6,
  } as CanvasElement)
  state.elements.push({
    id: genId(), type: 'rect',
    x: CONTENT_X, y: state.currentY,
    width: BLOCKQUOTE_BAR_WIDTH, height: blockH,
    fill: BRAND.primary,
    radius: 4,
  })
  state.elements.push({
    id: genId(), type: 'text',
    x: CONTENT_X + BLOCKQUOTE_BAR_WIDTH + 12, y: state.currentY + 8,
    width: CONTENT_WIDTH - BLOCKQUOTE_BAR_WIDTH - 24, height: h + 4,
    text: plain,
    fontSize: BODY_FONT_SIZE,
    fontStyle: 'italic',
    fill: '#475569',
  })
  for (const c of scanCitations(text)) state.activeCitations.add(c)
  state.currentY += blockH + 12
}

function extractExecutiveSummary(tokens: Token[]): { summary?: Tokens.Blockquote; remaining: Token[] } {
  const remaining = [...tokens]
  const first = remaining[0]
  if (first?.type === 'blockquote') {
    remaining.shift()
    return { summary: first as Tokens.Blockquote, remaining }
  }
  return { remaining }
}

/**
 * 预处理：从 Markdown 中提取所有脚注定义 `[^n]: URL`，
 * 存入字典并从原文中删除。同时截断 LLM 自动附加的参考资料区域。
 */
function extractCitations(markdown: string): {
  cleanedMarkdown: string
  citationsDict: Record<string, string>
} {
  const citationsDict: Record<string, string> = {}

  // Step 1: 优先提取脚注定义 [^n]: text → 存入字典
  const regex = /(?:^|\n)\[\^(\d+)\]:\s*(.+)/g
  const fragments: Array<{ full: string; id: string; text: string }> = []
  let match: RegExpExecArray | null
  while ((match = regex.exec(markdown)) !== null) {
    fragments.push({ full: match[0], id: match[1], text: match[2].trim() })
  }

  for (const f of fragments) {
    citationsDict[f.id] = f.text
  }

  // Step 2: 清理脚注行 — 从原文中删除提取出来的独立脚注定义行
  let cleaned = markdown
  for (const f of fragments) {
    cleaned = cleaned.replace(f.full, '')
  }

  // Step 3: 幽灵页截断 — 截断 LLM 自作主张生成的尾部参考资料区域
  // 增强版：同时匹配带和不带 emoji 的变体
  cleaned = cleaned.replace(
    /(?:^|\n)#{1,6}\s*[\s📚📖]*[\s]*(参考资料|参考来源|参考文献|资料来源|References|Bibliography)[\s\S]*$/i,
    '',
  )
  // 截断末尾残留的 --- 分隔线
  cleaned = cleaned.replace(/\n---\n\s*$/, '')
  cleaned = cleaned.replace(/\n---\s*$/, '')

  return { cleanedMarkdown: cleaned.trim(), citationsDict }
}

function scanCitations(text: string): Set<string> {
  const active = new Set<string>()
  const regex = /\[\^(\d+)\]/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    active.add(match[1])
  }
  return active
}

function buildCitationText(
  activeCitations: Set<string>,
  citationsDict: Record<string, string>,
): string {
  if (activeCitations.size === 0) return ''
  const lines: string[] = []
  const sorted = [...activeCitations].sort((a, b) => Number(a) - Number(b))
  for (const id of sorted) {
    const text = citationsDict[id]
    if (text) {
      lines.push(`[${id}] ${text}`)
    }
  }
  return lines.join('  ')
}

// ══════════════════════════════════════════════════════════════
// 旧版兼容：stripMarkdown
// ══════════════════════════════════════════════════════════════

export function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[.*?\]\(.*?\)/g, '')
    .replace(/\[([^\]]*?)\]\(.*?\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1')
    .replace(/^[\s]*[-*+]\s+/gm, '• ')
    .replace(/^[\s]*\d+\.\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^[-*_]{3,}\s*$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\[\^(\d+)\]/g, '[$1]')
    .trim()
}

// ══════════════════════════════════════════════════════════════
// 图片 URL 解析
// ══════════════════════════════════════════════════════════════

/** 将相对图片路径补全为可访问的完整 URL，并编码非 ASCII 字符 */
function resolveImageUrl(href: string): string {
  const trimmed = href.trim()
  let resolved: string

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    resolved = trimmed
  } else {
    // 去除可能的前导 ../
    let normalized = trimmed
    while (normalized.startsWith('../')) {
      normalized = normalized.slice(3)
    }
    // outputs/ 目录通过 /api/v1/files 静态挂载对外提供服务
    if (normalized.startsWith('outputs/')) {
      resolved = `/api/v1/files/${normalized.slice('outputs/'.length)}`
    } else if (!normalized.startsWith('/') && !normalized.startsWith('http')) {
      // 其他相对路径：作为服务器根路径处理（Vite dev proxy 自动转发 /api）
      resolved = `/${normalized}`
    } else {
      resolved = normalized
    }
  }

  try {
    const decoded = decodeURI(resolved)
    return encodeURI(decoded)
  } catch {
    return encodeURI(resolved)
  }
}

// ══════════════════════════════════════════════════════════════
// v5 商业风格 slide 装饰构建
// ══════════════════════════════════════════════════════════════

interface SlideDecorParams {
  sectionTitle: string
  logoUrl?: string
  pageNumber?: number
  totalPages?: number
}

function buildSlideDecor(params: SlideDecorParams): CanvasElement[] {
  const { sectionTitle, logoUrl, pageNumber, totalPages } = params
  const elements: CanvasElement[] = []

  // 白色背景
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 0, y: 0,
    width: CANVAS_WIDTH, height: CANVAS_HEIGHT,
    fill: BRAND.white,
  })

  // 左侧品牌色竖条（全高）
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 0, y: 0,
    width: SIDEBAR_WIDTH, height: CANVAS_HEIGHT,
    fill: BRAND.primary,
  })

  // ── 页眉区域 ──

  // Logo（如果有）
  if (logoUrl) {
    elements.push({
      id: genId(), type: 'image', name: 'decor',
      src: resolveImageUrl(logoUrl),
      x: 24, y: 6,
      width: 120, height: 60,
    })
  }

  // 章节标题
  const titleX = logoUrl ? 180 : CONTENT_X
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: titleX, y: 14,
    width: CANVAS_WIDTH - titleX - 160, height: 36,
    text: sectionTitle,
    fontSize: 20,
    fontWeight: 'bold',
    fill: BRAND.heading,
  })

  // 页码（右侧）
  if (pageNumber !== undefined) {
    const pageText = totalPages ? `${pageNumber} / ${totalPages}` : `${pageNumber}`
    elements.push({
      id: genId(), type: 'text', name: 'decor',
      x: CANVAS_WIDTH - 140, y: 18,
      width: 120, height: 24,
      text: pageText,
      fontSize: 12,
      fill: BRAND.muted,
      align: 'right',
    })
  }

  // 页眉分隔线（品牌色，全宽）
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: SIDEBAR_WIDTH, y: HEADER_HEIGHT,
    width: CANVAS_WIDTH - SIDEBAR_WIDTH, height: 2,
    fill: BRAND.primary,
  })

  // ── 页脚区域 ──
  const footerY = CANVAS_HEIGHT - FOOTER_HEIGHT

  // 页脚背景
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: SIDEBAR_WIDTH, y: footerY,
    width: CANVAS_WIDTH - SIDEBAR_WIDTH, height: FOOTER_HEIGHT,
    fill: BRAND.footerBg,
  })

  // 页脚左侧文字
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: CONTENT_X, y: footerY + 4,
    width: 400, height: 16,
    text: 'CONFIDENTIAL · 产品深度研究',
    fontSize: 9,
    fill: BRAND.muted,
  })

  // 页脚右侧品牌色点
  elements.push({
    id: genId(), type: 'circle', name: 'decor',
    x: CANVAS_WIDTH - 80, y: footerY + 8,
    width: 8, height: 8,
    radius: 4,
    fill: BRAND.primary,
  })

  return elements
}

// ══════════════════════════════════════════════════════════════
// 封面页构建（v5 增强版）
// ══════════════════════════════════════════════════════════════

function buildCoverSlide(topic: string): CanvasElement[] {
  const elements: CanvasElement[] = []

  // 深色背景
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 0, y: 0,
    width: CANVAS_WIDTH, height: CANVAS_HEIGHT,
    fill: BRAND.dark,
  })

  // 左侧品牌色竖条
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 80, y: 200,
    width: 6, height: 280,
    fill: BRAND.primary,
  })

  // 标签行（带边框）
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: 120, y: 160,
    width: 300, height: 28,
    text: 'PRODUCT DEEP RESEARCH',
    fontSize: 10,
    fontWeight: '600',
    fill: BRAND.primary,
  })

  // 主标题
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: 120, y: 210,
    width: CANVAS_WIDTH - 240, height: 80,
    text: topic,
    fontSize: 38, fontWeight: 'bold',
    fill: BRAND.white,
  })

  // 品牌色分割线
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 120, y: 320,
    width: 200, height: 4,
    fill: BRAND.primary,
  })

  // 副标题
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: 120, y: 350,
    width: CANVAS_WIDTH - 240, height: 40,
    text: '产品深度研究路演方案',
    fontSize: 18,
    fill: '#bcc8e0',
  })

  // 日期
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: 120, y: 420,
    width: CANVAS_WIDTH - 240, height: 30,
    text: new Date().toLocaleDateString('zh-CN', {
      year: 'numeric', month: 'long', day: 'numeric',
    }),
    fontSize: 14,
    fill: '#64748b',
  })

  // 底部出品信息
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: 120, y: 630,
    width: CANVAS_WIDTH - 240, height: 60,
    text: '出品机构 · 产品前沿战略研究院\n核心引擎 · AI 多模态视觉管道\n数据溯源 · 混合 RAG 权威检索链路',
    fontSize: 11,
    fill: '#64748b',
  })

  return elements
}

// ══════════════════════════════════════════════════════════════
// 目录页构建
// ══════════════════════════════════════════════════════════════

function buildTOCSlide(
  sections: Array<{ title: string }>,
  logoUrl?: string,
): CanvasElement[] {
  const elements: CanvasElement[] = []

  // 白色背景
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 0, y: 0,
    width: CANVAS_WIDTH, height: CANVAS_HEIGHT,
    fill: BRAND.white,
  })

  // 左侧品牌色竖条
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: 0, y: 0,
    width: SIDEBAR_WIDTH, height: CANVAS_HEIGHT,
    fill: BRAND.primary,
  })

  // Logo
  if (logoUrl) {
    elements.push({
      id: genId(), type: 'image', name: 'decor',
      src: resolveImageUrl(logoUrl),
      x: 24, y: 8,
      width: 40, height: 40,
    })
  }

  // "目录" 标题（居中，大字号）
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: SIDEBAR_WIDTH, y: 12,
    width: CANVAS_WIDTH - SIDEBAR_WIDTH, height: 40,
    text: '目录',
    fontSize: 28, fontWeight: 'bold',
    fill: BRAND.heading,
    align: 'center',
  })

  // 页眉分隔线
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: SIDEBAR_WIDTH, y: HEADER_HEIGHT,
    width: CANVAS_WIDTH - SIDEBAR_WIDTH, height: 2,
    fill: BRAND.primary,
  })

  // 章节列表：≤7 项用单栏居中，>7 项用双栏
  const lineHeight = 44
  const ITEM_FONT_SIZE = 18

  if (sections.length <= 7) {
    // 单栏居中布局（更舒展）
    const colWidth = 640
    const colX = (CANVAS_WIDTH - colWidth) / 2
    const blockH = sections.length * lineHeight
    const startY = Math.max(96, (CONTENT_START_Y + CONTENT_END_Y - blockH) / 2)

    sections.forEach((section, i) => {
      const y = startY + i * lineHeight
      elements.push({
        id: genId(), type: 'circle', name: 'decor',
        x: colX, y: y + lineHeight / 2 - 4,
        width: 8, height: 8,
        radius: 4,
        fill: BRAND.primary,
      })
      elements.push({
        id: genId(), type: 'text',
        x: colX + 20, y: y + (lineHeight - ITEM_FONT_SIZE * 1.2) / 2,
        width: colWidth - 20, height: ITEM_FONT_SIZE * 1.2,
        text: `${String(i + 1).padStart(2, '0')}  ${section.title}`,
        fontSize: ITEM_FONT_SIZE,
        fill: BRAND.body,
      })
    })
  } else {
    // 双栏布局
    const colWidth = 540
    const colGap = 40
    const leftColX = CONTENT_X
    const rightColX = CONTENT_X + colWidth + colGap
    const startY = 84
    const maxPerCol = Math.floor((CONTENT_END_Y - startY) / lineHeight)

    sections.forEach((section, i) => {
      const col = Math.floor(i / maxPerCol)
      const row = i % maxPerCol
      const x = col === 0 ? leftColX : rightColX
      const y = startY + row * lineHeight

      if (y > CONTENT_END_Y - 20) return // 防溢出

      elements.push({
        id: genId(), type: 'circle', name: 'decor',
        x: x, y: y + lineHeight / 2 - 4,
        width: 8, height: 8,
        radius: 4,
        fill: BRAND.primary,
      })
      elements.push({
        id: genId(), type: 'text',
        x: x + 20, y: y + (lineHeight - ITEM_FONT_SIZE * 1.2) / 2,
        width: colWidth - 20, height: ITEM_FONT_SIZE * 1.2,
        text: `${String(i + 1).padStart(2, '0')}  ${section.title}`,
        fontSize: ITEM_FONT_SIZE,
        fill: BRAND.body,
      })
    })
  }

  // 页脚
  const footerY = CANVAS_HEIGHT - FOOTER_HEIGHT
  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: SIDEBAR_WIDTH, y: footerY,
    width: CANVAS_WIDTH - SIDEBAR_WIDTH, height: FOOTER_HEIGHT,
    fill: BRAND.footerBg,
  })
  elements.push({
    id: genId(), type: 'text', name: 'decor',
    x: CONTENT_X, y: footerY + 4,
    width: 400, height: 16,
    text: 'CONFIDENTIAL · 产品深度研究',
    fontSize: 9,
    fill: BRAND.muted,
  })

  return elements
}

// ══════════════════════════════════════════════════════════════
// Layout Diversity — 层级树构建器 (v6)
// ══════════════════════════════════════════════════════════════

/**
 * 确定性伪随机数生成器 (mulberry32)。
 * 相同 seed 总是产生相同序列，保证同内容同排版。
 */
function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** 简单字符串哈希（用于 arrangement 种子） */
function hashString(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + ch
    hash |= 0
  }
  return Math.abs(hash)
}

/** 从 token 中提取纯文本 */
function extractTokenText(token: Token): string {
  if ('text' in token) {
    const t = token as { text: string }
    return stripMarkdown(t.text || '')
  }
  return ''
}

/**
 * 递归构建 list item 子树。
 * 处理 marked 的 item.tokens 中的嵌套 List 和段落，
 * 将扁平结构转为深度正确的 ContentNode 树。
 */
function buildListItemNode(
  item: Tokens.ListItem,
  depth: number,
): ContentNode {
  const children: ContentNode[] = []
  const inlineTextParts: string[] = []

  for (const childToken of item.tokens || []) {
    if (childToken.type === 'list') {
      // 嵌套列表 → 递归构建子节点（depth + 1）
      const nestedList = childToken as Tokens.List
      for (const nestedItem of nestedList.items) {
        const nestedNode = buildListItemNode(nestedItem, depth + 1)
        children.push(nestedNode)
      }
    } else if (childToken.type === 'text' || childToken.type === 'paragraph') {
      // 仅提取本层内联文本；不再转成 paragraph child，避免同层内容重复渲染
      const t = extractTokenText(childToken).trim()
      if (t) {
        inlineTextParts.push(t)
      }
    }
  }

  const inlineText = inlineTextParts.join(' ').trim()

  return {
    type: 'list_item',
    depth,
    text: inlineText || stripMarkdown(item.text || ''),
    token: item as unknown as Token,
    children,
  }
}

/**
 * 将 marked.lexer() 产生的扁平 Token 数组转换为层级 ContentNode 树。
 *
 * 层级规则：
 * - ## → depth 2 (Level 0，章节根)
 * - ### → depth 3 (Level 1)
 * - #### → depth 4 (Level 2)
 * - 顶层 - 列表项 → 承袭父标题 depth + 1
 * - 嵌套 - 列表项 → depth 递增
 *
 * 每个 list item 的 children 数组包含其嵌套子项。
 * 每个 heading 节点的 children 包含其下的所有内容。
 */
function buildHierarchyTree(tokens: Token[]): ContentNode[] {
  const roots: ContentNode[] = []
  const stack: ContentNode[] = [] // 当前嵌套路径（heading 层级栈）

  for (const token of tokens) {
    if (token.type === 'heading') {
      const hToken = token as Tokens.Heading
      const node: ContentNode = {
        type: 'heading',
        depth: hToken.depth,
        text: hToken.text,
        token,
        children: [],
      }

      // 弹出栈中所有 depth ≥ 当前 heading depth 的节点
      // 保证 ## 下可以嵌套 ###，### 下可以嵌套 ####
      while (stack.length > 0 && stack[stack.length - 1].depth >= hToken.depth) {
        stack.pop()
      }

      if (stack.length === 0) {
        roots.push(node)
      } else {
        const parent = stack[stack.length - 1]
        node.parent = parent
        parent.children.push(node)
      }

      stack.push(node)
    } else if (token.type === 'list') {
      const listToken = token as Tokens.List
      // 找到当前段落归属的父节点
      const currentParent = stack.length > 0 ? stack[stack.length - 1] : null
      const listDepth = currentParent ? currentParent.depth + 1 : 2

      for (const item of listToken.items) {
        const itemNode = buildListItemNode(item, listDepth)
        if (currentParent) {
          itemNode.parent = currentParent
          currentParent.children.push(itemNode)
        } else {
          roots.push(itemNode)
        }
      }
    } else if (hasSubstance(token)) {
      // 段落 / 表格 / 引用块 → 叶节点
      const currentParent = stack.length > 0 ? stack[stack.length - 1] : null
      const leafDepth = currentParent ? currentParent.depth + 1 : 2
      const node: ContentNode = {
        type: token.type,
        depth: leafDepth,
        text: extractTokenText(token),
        token,
        children: [],
      }
      if (currentParent) {
        node.parent = currentParent
        currentParent.children.push(node)
      } else {
        roots.push(node)
      }
    }
    // space / hr 忽略
  }

  return roots
}

// ══════════════════════════════════════════════════════════════
// 内部状态
// ══════════════════════════════════════════════════════════════

interface SlideBuildState {
  elements: CanvasElement[]
  currentY: number
  activeCitations: Set<string>
}

function clampContentY(currentY: number): number {
  return Math.min(currentY, CONTENT_END_Y)
}

function estimateVerticalNodeHeight(node: ContentNode): number {
  let h = 0
  if (node.text.trim()) {
    h += estimateTextHeight(node.text, BODY_FONT_SIZE, CONTENT_WIDTH - 20) + 8
  }
  for (const child of node.children) {
    h += estimateNodeHeight(child)
  }
  return h + 4
}

function getArrangementEstimate(node: ContentNode, arrangement: ArrangementFormat): number {
  if (arrangement === 'vertical') return estimateVerticalNodeHeight(node)
  return estimateArrangementHeight(node, arrangement)
}

function toLinePoints(x1: number, y1: number, x2: number, y2: number): number[] {
  return [x1, y1, x2, y2]
}

function buildLineElement(
  groupId: string,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: string,
  strokeWidth: number,
): CanvasElement {
  return {
    id: genId(),
    type: 'line',
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    points: toLinePoints(x1, y1, x2, y2),
    stroke,
    strokeWidth,
    groupId,
    name: 'arrangement-decor',
  }
}

// ══════════════════════════════════════════════════════════════
// AST Token → CanvasElement 精确映射（v5 商业风格版）
// ══════════════════════════════════════════════════════════════

/**
 * 检查段落 token 中是否包含内嵌图片，如有则提取渲染。
 */
function tryRenderParagraphImages(
  token: Tokens.Paragraph,
  state: SlideBuildState,
): boolean {
  const inlineTokens = (token as any).tokens as Token[] | undefined
  if (!inlineTokens || inlineTokens.length === 0) return false

  let hasImage = false
  for (const t of inlineTokens) {
    if (t.type === 'image') {
      const imgToken = t as Tokens.Image
      const href = imgToken.href
      const resolvedUrl = resolveImageUrl(href)

      state.elements.push({
        id: genId(),
        type: 'image',
        x: CONTENT_X,
        y: state.currentY,
        width: IMAGE_RENDER_WIDTH,
        height: IMAGE_RENDER_HEIGHT,
        src: resolvedUrl,
      })
      state.currentY += IMAGE_RENDER_HEIGHT + 20
      hasImage = true
    }
  }

  return hasImage
}

// ══════════════════════════════════════════════════════════════
// Layout Diversity — 树遍历渲染器 (v6 Phase 1)
// ══════════════════════════════════════════════════════════════

/**
 * 渲染单个 list_item 节点为圆点 + 文本。
 * 从 processToken 的 `case 'list'` 提取而来，支持独立调用。
 */
function renderBulletItem(
  plain: string,
  state: SlideBuildState,
  indentLevel: number,
): void {
  const indentX = (indentLevel - 1) * 24 // 每级缩进 24px
  const itemX = LIST_X + indentX
  const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH - 20 - indentX)

  const bulletY = state.currentY + BODY_FONT_SIZE * 0.675 - 4
  state.elements.push({
    id: genId(),
    type: 'circle',
    x: itemX - 8, y: bulletY,
    width: 8, height: 8,
    radius: 4,
    fill: BRAND.primary,
  } as CanvasElement)

  state.elements.push({
    id: genId(),
    type: 'text',
    x: itemX + 16, y: state.currentY,
    width: CONTENT_WIDTH - 36 - indentX, height: h + 8,
    text: plain,
    fontSize: BODY_FONT_SIZE,
    fill: BRAND.body,
  })
  state.currentY += h + 8
}

/**
 * 渲染单个有序列表项。
 */
function renderOrderedItem(
  plain: string,
  index: number,
  state: SlideBuildState,
  indentLevel: number,
): void {
  const indentX = (indentLevel - 1) * 24
  const itemX = LIST_X + indentX
  const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH - 20 - indentX)
  const displayText = `${index}. ${plain}`

  state.elements.push({
    id: genId(),
    type: 'text',
    x: itemX, y: state.currentY,
    width: CONTENT_WIDTH - 20 - indentX, height: h + 8,
    text: displayText,
    fontSize: BODY_FONT_SIZE,
    fill: BRAND.body,
  })
  state.currentY += h + 8
}

/**
 * 递归遍历 ContentNode 树，将所有节点渲染为 CanvasElement。
 *
 * Phase 1 行为：所有层级均使用 vertical 排列（保留现有行为）。
 * heading 按原样渲染；list_item 渲染为圆点+文本并递归子节点；
 * 其他 token 委托 processToken。
 */
function renderTreeWalk(
  nodes: ContentNode[],
  state: SlideBuildState,
  parentSeed: number,
  options?: {
    ensureSpace?: (requiredHeight: number) => void
  },
): void {
  for (const node of nodes) {
    renderStructuredNode(node, state, parentSeed, options)
  }
}

/** 原有的 processToken — 保留用于叶节点渲染 */
function processToken(
  token: Token,
  state: SlideBuildState,
): void {
  switch (token.type) {
    // ── 标题 ──────────────────────────────────────────────
    case 'heading': {
      const t = token as Tokens.Heading
      const text = t.text
      for (const c of scanCitations(text)) state.activeCitations.add(c)

      const h = estimateTextHeight(text, HEADING_FONT_SIZE, CONTENT_WIDTH)
      state.elements.push({
        id: genId(),
        type: 'text',
        x: CONTENT_X, y: state.currentY,
        width: CONTENT_WIDTH, height: h + 16,
        text,
        fontSize: HEADING_FONT_SIZE,
        fontWeight: 'bold',
        fill: BRAND.heading,
      })
      state.currentY += h + 16
      break
    }

    // ── 段落（含图片捕获） ──────────────────────────────
    case 'paragraph': {
      const t = token as Tokens.Paragraph

      const hasImage = tryRenderParagraphImages(t, state)
      if (hasImage) {
        const text = t.text
        for (const c of scanCitations(text)) state.activeCitations.add(c)
        break
      }

      const text = t.text
      for (const c of scanCitations(text)) state.activeCitations.add(c)

      const plain = stripMarkdown(text)
      if (!plain.trim()) { state.currentY += 8; break }

      const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH)
      state.elements.push({
        id: genId(),
        type: 'text',
        x: CONTENT_X, y: state.currentY,
        width: CONTENT_WIDTH, height: h + 12,
        text: plain,
        fontSize: BODY_FONT_SIZE,
        fill: BRAND.body,
      })
      state.currentY += h + 12
      break
    }

    // ── 列表（品牌色圆点） ────────────────────────────────
    case 'list': {
      const t = token as Tokens.List
      let itemIndex = 0
      for (const item of t.items) {
        const rawText = item.text || ''
        for (const c of scanCitations(rawText)) state.activeCitations.add(c)

        const plain = stripMarkdown(rawText)
        if (!plain.trim()) continue

        const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH - 20)

        if (t.ordered) {
          itemIndex++
          const displayText = `${itemIndex}. ${plain}`
          state.elements.push({
            id: genId(),
            type: 'text',
            x: LIST_X, y: state.currentY,
            width: CONTENT_WIDTH - 20, height: h + 8,
            text: displayText,
            fontSize: BODY_FONT_SIZE,
            fill: BRAND.body,
          })
        } else {
          // 圆点对齐首行垂直中心（基于字号而非整体高度，避免多行项目圆点过高）
          const bulletY = state.currentY + BODY_FONT_SIZE * 0.675 - 4
          state.elements.push({
            id: genId(),
            type: 'circle',
            x: LIST_X - 8, y: bulletY,
            width: 8, height: 8,
            radius: 4,
            fill: BRAND.primary,
          } as CanvasElement)

          state.elements.push({
            id: genId(),
            type: 'text',
            x: LIST_X + 16, y: state.currentY,
            width: CONTENT_WIDTH - 36, height: h + 8,
            text: plain,
            fontSize: BODY_FONT_SIZE,
            fill: BRAND.body,
          })
        }

        state.currentY += h + 8
      }
      state.currentY += 4
      break
    }

    // ── 表格 ──────────────────────────────────────────────
    case 'table': {
      const t = token as Tokens.Table
      const header = t.header.map((cell) => cell.text.replace(/^"|"$/g, '').trim())
      const rows = t.rows.map((row) => row.map((cell) => cell.text.replace(/^"|"$/g, '').trim()))
      const data = [header, ...rows]
      const rowH = 36
      const tableH = data.length * rowH
      const tableW = Math.min(CONTENT_WIDTH, header.length * 200)

      for (const row of data) {
        for (const cell of row) {
          for (const c of scanCitations(cell)) state.activeCitations.add(c)
        }
      }

      state.elements.push({
        id: genId(),
        type: 'table',
        x: CONTENT_X, y: state.currentY,
        width: tableW, height: tableH,
        tableData: data,
        headerFill: BRAND.primary,
        headerColor: BRAND.white,
        rowAltFill: '#f8fafc',
        tableBorderColor: BRAND.divider,
      } as CanvasElement)
      state.currentY += tableH + 16
      break
    }

    // ── 引用块 ──────────────────────────────────────────────
    case 'blockquote': {
      const t = token as Tokens.Blockquote
      const text = t.text
      for (const c of scanCitations(text)) state.activeCitations.add(c)

      const plain = stripMarkdown(text)
      if (!plain.trim()) { state.currentY += 4; break }

      const h = estimateTextHeight(plain, BODY_FONT_SIZE, CONTENT_WIDTH - 20)
      const blockH = h + 16

      // 浅色背景
      state.elements.push({
        id: genId(), type: 'rect',
        x: CONTENT_X, y: state.currentY,
        width: CONTENT_WIDTH, height: blockH,
        fill: '#f8fafc',
      })

      // 左侧蓝色竖条
      state.elements.push({
        id: genId(), type: 'rect',
        x: CONTENT_X, y: state.currentY,
        width: BLOCKQUOTE_BAR_WIDTH, height: blockH,
        fill: BRAND.primary,
      })

      // 文字
      state.elements.push({
        id: genId(), type: 'text',
        x: CONTENT_X + BLOCKQUOTE_BAR_WIDTH + 12, y: state.currentY + 8,
        width: CONTENT_WIDTH - BLOCKQUOTE_BAR_WIDTH - 20, height: h + 8,
        text: plain,
        fontSize: BODY_FONT_SIZE,
        fontStyle: 'italic',
        fill: '#64748b',
      })
      state.currentY += blockH + 12
      break
    }

    // ── 空白 ──────────────────────────────────────────────
    case 'space':
      state.currentY += 6  // 略微减少空白行间距
      break

    // ── 代码块 ────────────────────────────────────────────
    case 'code': {
      const t = token as Tokens.Code
      const lines = t.text.split('\n').length
      state.currentY += lines * 18 + 12
      break
    }

    default:
      state.currentY += 4
      break
  }
}

// ══════════════════════════════════════════════════════════════
// Layout Diversity — 排列格式渲染器 (v6 Phase 3-4)
// ══════════════════════════════════════════════════════════════

/** 排列渲染器函数签名 */
type ArrangementRendererFn = (
  parent: ContentNode,      // 父 list_item 节点（作为组标签）
  state: SlideBuildState,
  ctx: ArrangementContext,
) => void

/** 排列格式注册表 */
const ARRANGEMENT_RENDERERS: Record<ArrangementFormat, ArrangementRendererFn> = {
  vertical: renderArrangementVertical,
  bracket: renderArrangementBracket,
  table_compact: renderArrangementTableCompact,
  horizontal_flow: renderArrangementHorizontalFlow,
  card_grid: renderArrangementCardGrid,
  connected_lines: renderArrangementConnectedLines,
  numbered_circles: renderArrangementNumberedCircles,
  tag_flow: renderArrangementTagFlow,
  callout_boxes: renderArrangementCalloutBoxes,
  checklist: renderArrangementChecklist,
  timeline: renderArrangementTimeline,
  comparison_cols: renderArrangementComparisonCols,
}

/** 排列类型的装饰开销（用于分页预估，Phase 5） */
const ARRANGEMENT_OVERHEAD: Partial<Record<ArrangementFormat, number>> = {
  bracket: 24,
  connected_lines: 20,
  timeline: 20,
  callout_boxes: 16,
  card_grid: 8,
  comparison_cols: 20,
}

// ── 通用辅助 ─────────────────────────────────────────────────

/** 生成组 ID（同一组内所有元素共享） */
function genGroupId(): string {
  return `grp_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`
}

// ── 1. 竖向排列（现有方式，稳定锚点） ──────────────────────

function renderArrangementVertical(
  parent: ContentNode,
  state: SlideBuildState,
  _ctx: ArrangementContext,
): void {
  // 与 Phase 1 renderTreeWalk 中 list_item 行为一致
  // 父节点文本渲染为 bullet
  if (parent.text.trim()) {
    renderBulletItem(parent.text, state, parent.depth - 2)
  }
  // 递归子节点（保持现有垂直排列）
  for (const child of parent.children) {
    if (child.type === 'list_item') {
      if (child.text.trim()) {
        renderBulletItem(child.text, state, child.depth - 2)
      }
      // 再递归更深子节点
      renderTreeWalk(child.children, state, _ctx.seedValue)
    } else {
      renderTreeWalk([child], state, _ctx.seedValue)
    }
  }
  state.currentY += 4 // 组尾间距
}

// ── 2. 括弧排列 ────────────────────────────────────────────
//     两遍式：Pass 1 计算子项包围盒，Pass 2 绘制花括号 + 子项

function renderArrangementBracket(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  const startY = state.currentY
  const braceX = ctx.contentX + 40

  // Pass 1: 计算子项包围盒
  let contentMinY = Infinity, contentMaxY = -Infinity
  let dryY = startY
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, ctx.availableWidth - 80)
    dryY += labelH + 12
  }
  const textX = braceX + 24
  const textW = ctx.availableWidth - 80

  for (const item of items) {
    const itemH = estimateTextHeight(item.text, BODY_FONT_SIZE, textW) + 8
    contentMinY = Math.min(contentMinY, dryY)
    contentMaxY = Math.max(contentMaxY, dryY + itemH)
    dryY += itemH
  }

  const bbH = contentMaxY - contentMinY

  // 渲染父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, ctx.availableWidth - 80)
    state.elements.push({
      id: genId(), type: 'text',
      x: braceX + 24, y: state.currentY,
      width: textW, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  const braceStartY = state.currentY

  // Pass 2: 绘制装饰花括号（线段组成 `{` 形状）
  const braceTop = braceStartY
  const braceBot = braceStartY + bbH
  const braceMid = (braceTop + braceBot) / 2
  const braceSegments: Array<{ x1: number; y1: number; x2: number; y2: number }> = [
    // 上弯钩: 从 braceX+8 弯到 braceX 再到 braceX+8
    { x1: braceX + 12, y1: braceTop, x2: braceX + 12, y2: braceTop + 14 },
    { x1: braceX + 12, y1: braceTop + 14, x2: braceX, y2: braceTop + 14 },
    { x1: braceX, y1: braceTop + 14, x2: braceX, y2: braceMid },
    // 下弯钩
    { x1: braceX, y1: braceMid, x2: braceX, y2: braceBot - 14 },
    { x1: braceX, y1: braceBot - 14, x2: braceX + 12, y2: braceBot - 14 },
    { x1: braceX + 12, y1: braceBot - 14, x2: braceX + 12, y2: braceBot },
    // 尖角
    { x1: braceX, y1: braceMid, x2: braceX + 8, y2: braceMid - 5 },
    { x1: braceX, y1: braceMid, x2: braceX + 8, y2: braceMid + 5 },
  ]
  for (const seg of braceSegments) {
    state.elements.push(
      buildLineElement(
        groupId,
        seg.x1,
        seg.y1,
        seg.x2,
        seg.y2,
        BRAND.primary,
        2,
      ),
    )
  }

  // 渲染子项文本
  for (const item of items) {
    const itemH = estimateTextHeight(item.text, BODY_FONT_SIZE, textW)
    state.elements.push({
      id: genId(), type: 'text',
      x: textX, y: state.currentY,
      width: textW, height: itemH + 8,
      text: item.text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
    state.currentY += itemH + 8
  }
  state.currentY += 8
}

// ── 3. 表格排列 ───────────────────────────────────────────

function renderArrangementTableCompact(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  // 尝试将 ": " 或 "：" 分隔的文本拆分为键值对
  const rows: string[][] = []
  let hasKv = false
  for (const item of items) {
    const kvMatch = item.text.match(/^(.+?)[：:]\s*(.+)$/)
    if (kvMatch) {
      rows.push([kvMatch[1].trim(), kvMatch[2].trim()])
      hasKv = true
    } else {
      rows.push([item.text, ''])
    }
  }

  // 无键值对 → 单列表格（仅一列）
  const columns = hasKv ? 2 : 1
  const colW = Math.floor((ctx.availableWidth - 40) / columns)
  const rowH = 32
  const header = columns === 2 ? ['维度', '说明'] : [parent.text || '要点']

  const tableData = hasKv
    ? [header, ...rows.map((r) => [r[0], r[1]])]
    : [header, ...rows.map((r) => [r[0]])]

  const tableH = tableData.length * rowH
  const tableW = colW * columns

  state.elements.push({
    id: genId(), type: 'table',
    x: ctx.contentX, y: state.currentY,
    width: Math.min(tableW, ctx.availableWidth), height: tableH,
    tableData,
    headerFill: BRAND.primary, headerColor: BRAND.white,
    rowAltFill: '#f8fafc', tableBorderColor: BRAND.divider,
    groupId,
  } as CanvasElement)
  state.currentY += tableH + 16
}

// ── 4. 横向排列 ───────────────────────────────────────────

function renderArrangementHorizontalFlow(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  // 父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  // 横向流式布局：在一行上尽量排布，超出宽度时换行
  const flowX = ctx.contentX
  let cursorX = flowX
  const flowStartY = state.currentY
  const sep = '  •  '
  const maxW = ctx.availableWidth

  for (const item of items) {
    const itemText = item.text
    const estW = estimateTextWidth(itemText + sep, BODY_FONT_SIZE)

    if (cursorX + estW > flowX + maxW && cursorX > flowX) {
      // 换行
      cursorX = flowX
      state.currentY += BODY_FONT_SIZE * 1.35 + 6
    }

    state.elements.push({
      id: genId(), type: 'text',
      x: cursorX, y: state.currentY,
      width: estW, height: BODY_FONT_SIZE * 1.35 + 4,
      text: itemText + (items.indexOf(item) < items.length - 1 ? sep.replace(/\s+/g, '') : ''),
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
    cursorX += estW
  }

  state.currentY += BODY_FONT_SIZE * 1.35 + 12
}

/** 粗略估计文本宽度（与 estimateTextHeight 使用同套字符宽度模型） */
function estimateTextWidth(text: string, fontSize: number): number {
  let w = 0
  for (const ch of text) {
    if (/\s/.test(ch)) w += fontSize * 0.32
    else if (isWideChar(ch)) w += fontSize * 1.0
    else if (/[A-Z0-9]/.test(ch)) w += fontSize * 0.62
    else w += fontSize * 0.58
  }
  return w
}

// ── 5. 线段链接排列 ────────────────────────────────────────
//     从父节点向每个子节点绘制连接线

function renderArrangementConnectedLines(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  const treeX = ctx.contentX + 60
  const textX = treeX + 20
  const textW = ctx.availableWidth - 100

  // Pass 1: 计算所有子项位置
  type ConnPos = { y: number; textH: number }
  const positions: ConnPos[] = []
  let dryY = state.currentY

  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    dryY += labelH + 12
  }

  for (const item of items) {
    const itemH = estimateTextHeight(item.text, BODY_FONT_SIZE, textW) + 8
    positions.push({ y: dryY, textH: itemH })
    dryY += itemH
  }

  const parentConnY = parent.text.trim()
    ? state.currentY + estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH) / 2
    : state.currentY

  // 渲染父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: treeX, y: state.currentY,
      width: CONTENT_WIDTH - 80, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  // 垂直主干线
  const itemsStartY = state.currentY
  const itemsEndY = dryY
  state.elements.push({
    id: genId(), type: 'rect',
    x: treeX - 1, y: parentConnY,
    width: 2, height: itemsEndY - parentConnY + 8,
    fill: BRAND.primary,
    groupId, name: 'arrangement-decor',
  })

  // Pass 2: 渲染每个子节点（水平分支线 + 文本）
  for (let i = 0; i < items.length; i++) {
    const pos = positions[i]

    // 水平分支线
    state.elements.push(
      buildLineElement(
        groupId,
        treeX,
        pos.y + pos.textH / 2,
        textX,
        pos.y + pos.textH / 2,
        BRAND.muted,
        1,
      ),
    )

    // 圆点
    state.elements.push({
      id: genId(), type: 'circle',
      x: treeX - 3, y: pos.y + pos.textH / 2 - 3,
      width: 6, height: 6, radius: 3,
      fill: BRAND.primary,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 文本
    state.elements.push({
      id: genId(), type: 'text',
      x: textX, y: pos.y,
      width: textW, height: pos.textH,
      text: items[i].text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
  }

  state.currentY = itemsEndY + 8
}

// ── 7. 编号圆圈排列 ────────────────────────────────────────

function renderArrangementNumberedCircles(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  const numCircleR = 16
  const textOffsetX = 56

  // 父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 16
  }

  for (let i = 0; i < items.length; i++) {
    const textH = estimateTextHeight(items[i].text, BODY_FONT_SIZE, ctx.availableWidth - textOffsetX)

    // 编号圆
    state.elements.push({
      id: genId(), type: 'circle',
      x: ctx.contentX + 8, y: state.currentY + 2,
      width: numCircleR * 2, height: numCircleR * 2,
      radius: numCircleR,
      fill: BRAND.primary,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 编号文字
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX + 8 + numCircleR - 6, y: state.currentY + 6,
      width: 20, height: 20,
      text: String(i + 1),
      fontSize: 14, fontWeight: 'bold',
      fill: BRAND.white,
      groupId, name: 'arrangement-decor',
    })

    // 文本
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX + textOffsetX, y: state.currentY,
      width: ctx.availableWidth - textOffsetX, height: Math.max(textH + 8, numCircleR * 2 + 4),
      text: items[i].text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
    state.currentY += Math.max(textH + 12, numCircleR * 2 + 8)
  }
  state.currentY += 8
}

// ── 8. 标签流排列 ──────────────────────────────────────────

const TAG_FONT_SIZE = 13
const TAG_PADDING_X = 14
const TAG_PADDING_Y = 6
const TAG_RADIUS = 14
const TAG_COLORS = ['#eff6ff', '#f0fdf4', '#fefce8', '#fef2f2', '#f5f3ff', '#f0f9ff']

function renderArrangementTagFlow(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  const tagStartY = state.currentY
  let cursorX = ctx.contentX

  for (let i = 0; i < items.length; i++) {
    const text = items[i].text
    const tagW = estimateTextWidth(text, TAG_FONT_SIZE) + TAG_PADDING_X * 2

    // 换行检测
    if (cursorX + tagW > ctx.contentX + ctx.availableWidth && cursorX > ctx.contentX) {
      cursorX = ctx.contentX
      state.currentY += TAG_FONT_SIZE * 1.35 + TAG_PADDING_Y * 2 + 6
    }

    const bgColor = TAG_COLORS[i % TAG_COLORS.length]

    // 标签背景
    state.elements.push({
      id: genId(), type: 'rect',
      x: cursorX, y: state.currentY,
      width: tagW, height: TAG_FONT_SIZE * 1.35 + TAG_PADDING_Y * 2,
      fill: bgColor, stroke: BRAND.divider, strokeWidth: 0.5,
      radius: TAG_RADIUS,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 标签文本
    state.elements.push({
      id: genId(), type: 'text',
      x: cursorX + TAG_PADDING_X,
      y: state.currentY + TAG_PADDING_Y,
      width: tagW - TAG_PADDING_X * 2,
      height: TAG_FONT_SIZE * 1.35 + 2,
      text,
      fontSize: TAG_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })

    cursorX += tagW + 8
  }

  state.currentY += TAG_FONT_SIZE * 1.35 + TAG_PADDING_Y * 2 + 12
}

// ── 9. 标注框排列（两遍式 Bounding Box） ──────────────────

const CALLOUT_COLORS = ['#eff6ff', '#f0fdf4', '#fefce8', '#fef2f2', '#f5f3ff']
const CALLOUT_ACCENTS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6']

function renderArrangementCalloutBoxes(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  const boxX = ctx.contentX
  const accentW = 4
  const padX = 14
  const padY = 10
  const textW = ctx.availableWidth - accentW - padX * 2

  // 父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  for (let i = 0; i < items.length; i++) {
    const text = items[i].text
    const h = estimateTextHeight(text, BODY_FONT_SIZE, textW)
    const boxH = h + padY * 2
    const accentColor = CALLOUT_ACCENTS[i % CALLOUT_ACCENTS.length]
    const bgColor = CALLOUT_COLORS[i % CALLOUT_COLORS.length]

    // 背景 rect
    state.elements.push({
      id: genId(), type: 'rect',
      x: boxX, y: state.currentY,
      width: ctx.availableWidth, height: boxH,
      fill: bgColor, stroke: BRAND.divider, strokeWidth: 0.5,
      radius: 4,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 左侧 accent 竖条
    state.elements.push({
      id: genId(), type: 'rect',
      x: boxX, y: state.currentY,
      width: accentW, height: boxH,
      fill: accentColor,
      groupId, name: 'arrangement-decor',
    })

    // 文本
    state.elements.push({
      id: genId(), type: 'text',
      x: boxX + accentW + padX,
      y: state.currentY + padY,
      width: textW, height: h + 4,
      text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })

    state.currentY += boxH + 8
  }
  state.currentY += 4
}

// ── 10. 清单列表排列 ───────────────────────────────────────

function renderArrangementChecklist(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length === 0) {
    renderArrangementVertical(parent, state, ctx)
    return
  }

  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  for (const item of items) {
    const h = estimateTextHeight(item.text, BODY_FONT_SIZE, ctx.availableWidth - 30)

    // 勾选图标 ✓
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY + 2,
      width: 24, height: h + 4,
      text: '✓',
      fontSize: BODY_FONT_SIZE,
      fontWeight: 'bold',
      fill: BRAND.primary,
      groupId, name: 'arrangement-decor',
    })

    // 文本
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX + 28, y: state.currentY,
      width: ctx.availableWidth - 28, height: h + 8,
      text: item.text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
    state.currentY += h + 10
  }
  state.currentY += 4
}

// ── 12. 对比列排列 ─────────────────────────────────────────

function renderArrangementComparisonCols(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())
  if (items.length < 2) {
    // 少于 2 项无法对比 → 降级 vertical
    renderArrangementVertical(parent, state, ctx)
    return
  }

  const nCols = Math.min(items.length, 3) // 最多 3 列
  const colW = Math.floor((ctx.availableWidth - (nCols - 1) * 12) / nCols)
  const colX = ctx.contentX

  // 父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  const colsStartY = state.currentY
  const colAccents = ['#3b82f6', '#22c55e', '#eab308']

  // Pass 1: 计算每列最大高度
  const colMaxH: number[] = Array(nCols).fill(0)
  for (let c = 0; c < nCols; c++) {
    const item = items[c]
    const h = estimateTextHeight(item.text, BODY_FONT_SIZE, colW - 16) + 40 // 40 = header
    colMaxH[c] = h
  }
  const maxColH = Math.max(...colMaxH)

  // Pass 2: 渲染列
  for (let c = 0; c < nCols; c++) {
    const item = items[c]
    const cx = colX + c * (colW + 12)
    const colH = colMaxH[c]

    // 列背景
    state.elements.push({
      id: genId(), type: 'rect',
      x: cx, y: colsStartY,
      width: colW, height: Math.max(colH, 100),
      fill: '#f8fafc', stroke: BRAND.divider, strokeWidth: 0.5,
      radius: 6,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 列标题 accent
    state.elements.push({
      id: genId(), type: 'rect',
      x: cx, y: colsStartY,
      width: colW, height: 4,
      fill: colAccents[c % colAccents.length],
      radius: 0,
      groupId, name: 'arrangement-decor',
    })

    // 列文本
    const textH = estimateTextHeight(item.text, BODY_FONT_SIZE, colW - 16)
    state.elements.push({
      id: genId(), type: 'text',
      x: cx + 8, y: colsStartY + 16,
      width: colW - 16, height: textH + 8,
      text: item.text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
  }

  state.currentY = colsStartY + maxColH + 12
}

const CARD_GAP = 12
const CARD_MIN_WIDTH = 320
const CARD_MIN_HEIGHT = 64
const CARD_RADIUS = 8
const CARD_PADDING_X = 16
const CARD_PADDING_Y = 10

function renderArrangementCardGrid(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())

  if (items.length === 0) {
    // 无有效子项 → 降级 vertical
    if (parent.text.trim()) renderBulletItem(parent.text, state, parent.depth - 2)
    return
  }

  // 确定列数：≤3 项 → 1 列, 4-6 项 → 2 列, ≥7 项 → 3 列
  const cols = items.length <= 3 ? 1 : items.length <= 6 ? 2 : 3
  const cardWidth = Math.floor((ctx.availableWidth - CARD_GAP * (cols - 1)) / cols)

  // Pass 1: 计算每个卡片的内容高度 + 整体 bounding box
  const cardHeights: number[] = []
  for (const item of items) {
    const textH = estimateTextHeight(item.text, BODY_FONT_SIZE, cardWidth - CARD_PADDING_X * 2)
    const cardH = Math.max(textH + CARD_PADDING_Y * 2 + 8, CARD_MIN_HEIGHT)
    cardHeights.push(cardH)
  }

  const rowHeights: number[] = []
  for (let row = 0; row < Math.ceil(items.length / cols); row++) {
    let rowMaxH = CARD_MIN_HEIGHT
    for (let col = 0; col < cols; col++) {
      const idx = row * cols + col
      if (idx >= items.length) break
      rowMaxH = Math.max(rowMaxH, cardHeights[idx])
    }
    rowHeights.push(rowMaxH)
  }

  const totalGridHeight = rowHeights.reduce((sum, rowH) => sum + rowH, 0) +
    Math.max(rowHeights.length - 1, 0) * CARD_GAP

  // 渲染父标签
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX, y: state.currentY,
      width: CONTENT_WIDTH, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 12
  }

  const gridStartY = state.currentY

  // Pass 2: 渲染卡片（含装饰框 + 文本）
  let rowOffsetY = 0
  for (let row = 0; row < rowHeights.length; row++) {
    const rowStartX = ctx.contentX
    const rowMaxH = rowHeights[row]
    const rowStartIdx = row * cols

    for (let col = 0; col < cols; col++) {
      const itemIdx = rowStartIdx + col
      if (itemIdx >= items.length) break

      const cardX = rowStartX + col * (cardWidth + CARD_GAP)
      const cardY = gridStartY + rowOffsetY
      const bgH = Math.max(cardHeights[itemIdx], rowMaxH)

      // 卡片背景
      state.elements.push({
        id: genId(), type: 'rect',
        x: cardX, y: cardY, width: cardWidth, height: bgH,
        fill: '#f8fafc', stroke: BRAND.divider, strokeWidth: 1,
        radius: CARD_RADIUS,
        groupId, name: 'arrangement-decor',
      } as CanvasElement)

      // 卡片文本
      state.elements.push({
        id: genId(), type: 'text',
        x: cardX + CARD_PADDING_X,
        y: cardY + CARD_PADDING_Y,
        width: cardWidth - CARD_PADDING_X * 2,
        height: bgH - CARD_PADDING_Y * 2,
        text: items[itemIdx].text,
        fontSize: BODY_FONT_SIZE,
        fill: BRAND.body,
        groupId,
      } as CanvasElement)
    }

    rowOffsetY += rowMaxH + CARD_GAP
  }

  state.currentY = gridStartY + totalGridHeight + 8 // 组尾间距
}

// ── 11. 时间轴排列 ─────────────────────────────────────────

const TIMELINE_LINE_X_OFFSET = 40
const TIMELINE_DOT_RADIUS = 6
const TIMELINE_LINE_WIDTH = 2

function renderArrangementTimeline(
  parent: ContentNode,
  state: SlideBuildState,
  ctx: ArrangementContext,
): void {
  const groupId = genGroupId()
  const items = parent.children.filter((c) => c.type === 'list_item' && c.text.trim())

  if (items.length === 0) {
    if (parent.text.trim()) renderBulletItem(parent.text, state, parent.depth - 2)
    return
  }

  // 父标签
  const startY = state.currentY
  if (parent.text.trim()) {
    const labelH = estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH - TIMELINE_LINE_X_OFFSET)
    state.elements.push({
      id: genId(), type: 'text',
      x: ctx.contentX + TIMELINE_LINE_X_OFFSET + 24, y: state.currentY,
      width: CONTENT_WIDTH - TIMELINE_LINE_X_OFFSET - 24, height: labelH + 4,
      text: parent.text,
      fontSize: BODY_FONT_SIZE, fontWeight: 'bold',
      fill: BRAND.heading,
      groupId,
    })
    state.currentY += labelH + 16
  }

  const lineStartY = parent.text.trim() ? startY + estimateTextHeight(parent.text, BODY_FONT_SIZE, CONTENT_WIDTH) + 20 : state.currentY
  const lineX = ctx.contentX + TIMELINE_LINE_X_OFFSET
  let lastDotY = lineStartY

  // Pass 1: 计算所有节点的位置
  type TimelinePos = { dotY: number; text: string; textH: number }
  const positions: TimelinePos[] = []
  let cursorY = lineStartY

  for (let i = 0; i < items.length; i++) {
    const textH = estimateTextHeight(items[i].text, BODY_FONT_SIZE, ctx.availableWidth - TIMELINE_LINE_X_OFFSET - 30)
    positions.push({ dotY: cursorY, text: items[i].text, textH })
    cursorY += Math.max(textH + 12, 40) // 最小间距 40px
    lastDotY = cursorY
  }

  // Pass 2: 渲染时间轴竖线（装饰元素）
  const timelineH = lastDotY - lineStartY + 8
  state.elements.push({
    id: genId(), type: 'rect',
    x: lineX - TIMELINE_LINE_WIDTH / 2, y: lineStartY,
    width: TIMELINE_LINE_WIDTH, height: Math.max(timelineH, TIMELINE_DOT_RADIUS * 2),
    fill: BRAND.primary,
    groupId, name: 'arrangement-decor',
  })

  // Pass 3: 渲染每个节点（圆点 + 文本）
  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i]

    // 圆点
    state.elements.push({
      id: genId(), type: 'circle',
      x: lineX - TIMELINE_DOT_RADIUS, y: pos.dotY,
      width: TIMELINE_DOT_RADIUS * 2, height: TIMELINE_DOT_RADIUS * 2,
      radius: TIMELINE_DOT_RADIUS,
      fill: BRAND.white,
      stroke: BRAND.primary, strokeWidth: 2,
      groupId, name: 'arrangement-decor',
    } as CanvasElement)

    // 文本
    state.elements.push({
      id: genId(), type: 'text',
      x: lineX + 18, y: pos.dotY - 2,
      width: ctx.availableWidth - TIMELINE_LINE_X_OFFSET - 30,
      height: pos.textH + 8,
      text: pos.text,
      fontSize: BODY_FONT_SIZE,
      fill: BRAND.body,
      groupId,
    })
  }

  state.currentY = lastDotY + 8
}

// ══════════════════════════════════════════════════════════════
// 高度预估（用于分页判断）
// ══════════════════════════════════════════════════════════════

function estimateTokenHeight(token: Token): number {
  switch (token.type) {
    case 'heading': {
      const t = token as Tokens.Heading
      return estimateTextHeight(t.text, HEADING_FONT_SIZE, CONTENT_WIDTH) + 16
    }
    case 'paragraph': {
      const t = token as Tokens.Paragraph
      const inlineTokens = (t as any).tokens as Token[] | undefined
      if (inlineTokens) {
        let imgH = 0
        for (const it of inlineTokens) {
          if (it.type === 'image') {
            imgH += IMAGE_RENDER_HEIGHT + 20
          }
        }
        if (imgH > 0) return imgH
      }
      return estimateTextHeight(stripMarkdown(t.text), BODY_FONT_SIZE, CONTENT_WIDTH) + 12
    }
    case 'list': {
      const t = token as Tokens.List
      let total = 0
      for (const item of t.items) {
        const raw = item.text || ''
        total += estimateTextHeight(stripMarkdown(raw), BODY_FONT_SIZE, CONTENT_WIDTH - 20) + 8
      }
      return total + 4
    }
    case 'table': {
      const t = token as Tokens.Table
      return (t.rows.length + 1) * 36 + 16
    }
    case 'blockquote': {
      const t = token as Tokens.Blockquote
      return estimateTextHeight(stripMarkdown(t.text), BODY_FONT_SIZE, CONTENT_WIDTH - 20) + 16 + 12
    }
    case 'code': {
      const t = token as Tokens.Code
      return t.text.split('\n').length * 18 + 12
    }
    case 'space':
      return 6
    default:
      return 4
  }
}

function hasSubstance(token: Token): boolean {
  return token.type !== 'space' && token.type !== 'hr'
}

// ══════════════════════════════════════════════════════════════
// 引用页尾渲染（v5：分隔线 + 溢出检测）
// ══════════════════════════════════════════════════════════════

function appendCitationFooter(
  elements: CanvasElement[],
  activeCitations: Set<string>,
  citationsDict: Record<string, string>,
  currentY: number,
): number {
  if (activeCitations.size === 0) return currentY

  const citationText = buildCitationText(activeCitations, citationsDict)
  if (!citationText) return currentY

  const citationHeight = estimateCitationFooterHeight(activeCitations, citationsDict)
  const safeCurrentY = clampContentY(currentY)
  const maxSeparatorY = CANVAS_HEIGHT - FOOTER_HEIGHT - 4 - citationHeight
  const separatorY = Math.min(Math.max(safeCurrentY + 8, CITATION_ZONE_Y), maxSeparatorY)

  if (separatorY <= safeCurrentY) {
    return currentY
  }

  elements.push({
    id: genId(), type: 'rect', name: 'decor',
    x: CONTENT_X, y: separatorY,
    width: CONTENT_WIDTH, height: 1,
    fill: BRAND.divider,
  })

  elements.push({
    id: genId(), type: 'text',
    x: CONTENT_X, y: separatorY + 6,
    width: CONTENT_WIDTH, height: citationHeight,
    text: citationText,
    fontSize: CITATION_FONT_SIZE,
    fill: BRAND.muted,
  })

  return separatorY + citationHeight
}

// ══════════════════════════════════════════════════════════════
// 正文分页引擎（v5：商业风格 + 章节级渲染）
// ══════════════════════════════════════════════════════════════

function buildContentSlides(
  sectionTitle: string,
  content: string,
  citationsDict: Record<string, string>,
  logoUrl?: string,
  startPageNumber?: number,
  totalPages?: number,
  withImagePlaceholder = false,
): CanvasElement[][] {
  const slidesElements: CanvasElement[][] = []

  const rawTokens = marked.lexer(content)
  if (rawTokens.length === 0) {
    slidesElements.push([
      ...buildSlideDecor({
        sectionTitle,
        logoUrl,
        pageNumber: startPageNumber,
        totalPages,
      }),
    ])
    return slidesElements
  }

  let firstHeadingRemoved = false
  const filteredTokens = rawTokens.filter((token) => {
    if (token.type === 'space') return false
    if (!firstHeadingRemoved && token.type === 'heading') {
      firstHeadingRemoved = true
      return false
    }
    return true
  })

  const { summary, remaining } = extractExecutiveSummary(filteredTokens)
  const tokens = remaining

  if (tokens.length === 0 && !summary) {
    slidesElements.push([
      ...buildSlideDecor({
        sectionTitle,
        logoUrl,
        pageNumber: startPageNumber,
        totalPages,
      }),
    ])
    return slidesElements
  }

  const tree = buildHierarchyTree(tokens)

  let currentPageNum = startPageNumber || 1
  let state: SlideBuildState = {
    elements: [
      ...buildSlideDecor({
        sectionTitle,
        logoUrl,
        pageNumber: currentPageNum,
        totalPages,
      }),
    ],
    currentY: CONTENT_START_Y,
    activeCitations: new Set<string>(),
  }

  if (withImagePlaceholder) {
    const phX = CANVAS_WIDTH - 80 - PLACEHOLDER_WIDTH
    state.elements.push({
      id: genId(),
      type: 'placeholder',
      x: phX, y: CONTENT_START_Y,
      width: PLACEHOLDER_WIDTH, height: PLACEHOLDER_HEIGHT,
      text: '🖼  双击插入图片',
    } as CanvasElement)
    state.currentY = CONTENT_START_Y + PLACEHOLDER_HEIGHT + 16
  }

  const resetPage = () => {
    currentPageNum++
    state = {
      elements: [
        ...buildSlideDecor({
          sectionTitle,
          logoUrl,
          pageNumber: currentPageNum,
          totalPages,
        }),
      ],
      currentY: CONTENT_START_Y,
      activeCitations: new Set<string>(),
    }
  }

  const flushCurrentPage = () => {
    appendCitationFooter(
      state.elements,
      state.activeCitations,
      citationsDict,
      clampContentY(state.currentY),
    )
    slidesElements.push(state.elements)
    resetPage()
  }

  const ensureSpace = (requiredHeight: number) => {
    if (state.currentY <= CONTENT_START_Y) return
    if (requiredHeight <= getCurrentPageCapacity(state, citationsDict)) return
    flushCurrentPage()
  }

  if (summary) {
    renderSectionCallout(summary.text, state, { ensureSpace })
  }

  const treeSeed = hashString(sectionTitle + content)

  function walkAndPaginate(nodes: ContentNode[]): void {
    for (const node of nodes) {
      if (node.breakBefore && state.currentY > CONTENT_START_Y) {
        flushCurrentPage()
      }

      updateNodePageBreaks(node, state, citationsDict)
      ensureNodeFitsPage(node, state, citationsDict, flushCurrentPage)

      const pageCapacity = getPageCapacityLimit(citationsDict, estimateNodeCitations(node))
      const nodeH = getRequiredHeightForNode(node)
      const useOversizedVerticalFallback =
        node.type === 'list_item' &&
        isArrangeableGroup(node) &&
        nodeH > pageCapacity

      if (useOversizedVerticalFallback) {
        ensureSpace(estimateVerticalNodeHeight(node))
        renderArrangementVertical(node, state, {
          contentX: CONTENT_X,
          availableWidth: CONTENT_WIDTH,
          isLeafGroup: false,
          seedValue: treeSeed,
        })
      } else if (node.type === 'heading' || node.type === 'list_item') {
        renderTreeWalk([node], state, treeSeed, { ensureSpace })
      } else {
        ensureSpace(estimateTokenHeight(node.token))
        processToken(node.token, state)
      }
    }
  }

  walkAndPaginate(tree)

  appendCitationFooter(
    state.elements,
    state.activeCitations,
    citationsDict,
    clampContentY(state.currentY),
  )
  slidesElements.push(state.elements)

  return slidesElements
}

/** 🆕 v6: 递归估算 ContentNode 及其所有子节点的总高度 */
function estimateNodeHeight(node: ContentNode): number {
  let h = 0

  if (node.type === 'list_item') {
    if (isArrangeableGroup(node)) {
      const arrangement = getNodeArrangement(node, hashString(node.text || node.token.raw || node.type))
      return getArrangementEstimate(node, arrangement)
    }

    if (node.text.trim()) {
      h += getNodeOwnHeight(node)
    }
    for (const child of node.children) {
      h += estimateNodeHeight(child)
    }
    h += 4
  } else if (node.type === 'heading') {
    h += getNodeOwnHeight(node)
    for (const child of node.children) {
      h += estimateNodeHeight(child)
    }
  } else {
    h += estimateTokenHeight(node.token)
  }

  return h
}

/** 🆕 v6: 判断 ContentNode 是否有实质内容（非空白/装饰） */
function nodeHasSubstance(node: ContentNode): boolean {
  if (node.type === 'list_item') {
    return node.text.trim().length > 0 || node.children.length > 0
  }
  return hasSubstance(node.token)
}

// ══════════════════════════════════════════════════════════════
// 全局引用编号 reconcile
// ══════════════════════════════════════════════════════════════

/**
 * 将多个 block 的 per-section citationsDict 合并为全局引用字典。
 * 相同 URL 的引用会映射到同一个全局 ID，避免不同章节的 [^1]
 * 指向不同 URL 造成混淆。
 */
function reconcileCitationsGlobal(
  blockCitationDicts: Array<Record<string, string>>,
): {
  globalDicts: Array<Record<string, string>>  // 每个 block 重新映射后的字典
  globalDict: Record<string, string>          // 全局完整字典
} {
  const urlToGlobalId: Record<string, string> = {}
  const globalDict: Record<string, string> = {}
  let nextGlobalId = 1

  const globalDicts: Array<Record<string, string>> = []

  for (const localDict of blockCitationDicts) {
    const remapped: Record<string, string> = {}

    for (const [localId, urlOrText] of Object.entries(localDict)) {
      // 提取纯 URL（去除可能的 "来源链接: <url>" 包装）
      let cleanUrl = urlOrText
      const urlMatch = urlOrText.match(/<(https?:\/\/[^>]+)>/)
      if (urlMatch) {
        cleanUrl = urlMatch[1]
      } else if (urlOrText.startsWith('来源链接: ')) {
        cleanUrl = urlOrText.replace('来源链接: ', '').trim()
      }

      // 检查是否已注册
      const existingGlobalId = urlToGlobalId[cleanUrl]
      if (existingGlobalId) {
        remapped[localId] = cleanUrl
        // 映射 localId → existingGlobalId（渲染时替换）
      } else {
        const gid = String(nextGlobalId)
        urlToGlobalId[cleanUrl] = gid
        globalDict[gid] = cleanUrl
        remapped[localId] = cleanUrl
        nextGlobalId++
      }
    }

    globalDicts.push(remapped)
  }

  return { globalDicts, globalDict }
}

// ══════════════════════════════════════════════════════════════
// 公开 API
// ══════════════════════════════════════════════════════════════

/**
 * 将后端 DocumentBlock 数组转换为 Konva 幻灯片数组（v5 商业风格版）。
 *
 * 两遍扫描策略：
 * 1. 第一遍：生成所有 slide 元素，确定总页数
 * 2. 第二遍：将正确的页码信息注入每个 slide 的装饰元素中
 */
export function convertBlocksToKonvaSlides(
  topic: string,
  blocks: Pick<DocumentBlockResponse, 'section_title' | 'content' | 'order_index'>[],
  logoUrl?: string,
): KonvaSlide[] {
  _elementIdCounter = 0

  const sorted = [...blocks].sort((a, b) => a.order_index - b.order_index)

  // ── Step 1: 提取所有 block 的引用字典，进行全局 reconcile ──
  const blockCitationDicts: Array<Record<string, string>> = []
  const blockCleanedMarkdowns: string[] = []

  for (const block of sorted) {
    const rawContent = block.content || ''
    const { cleanedMarkdown, citationsDict } = extractCitations(rawContent)
    blockCitationDicts.push(citationsDict)
    blockCleanedMarkdowns.push(cleanedMarkdown)
  }

  const { globalDict } = reconcileCitationsGlobal(blockCitationDicts)

  // ── Step 2: 第一遍 — 生成所有 slide 元素（页码暂为占位） ──
  interface SlideInfo {
    sectionTitle: string
    elements: CanvasElement[]
  }
  const allSlideInfos: SlideInfo[] = []

  // 封面
  allSlideInfos.push({
    sectionTitle: '封面',
    elements: buildCoverSlide(topic),
  })

  // 目录
  const sectionList = sorted.map((block) => ({
    title: block.section_title || '章节',
  }))
  allSlideInfos.push({
    sectionTitle: '目录',
    elements: buildTOCSlide(sectionList, logoUrl),
  })

  // 正文
  for (let bIdx = 0; bIdx < sorted.length; bIdx++) {
    const block = sorted[bIdx]
    const title = block.section_title || '章节'
    const cleanedMarkdown = blockCleanedMarkdowns[bIdx]

    const pageElements = buildContentSlides(
      title,
      cleanedMarkdown,
      globalDict,
      logoUrl,
      undefined,
      undefined,
      true, // 每章节首页预留图片占位框
    )

    for (const elements of pageElements) {
      allSlideInfos.push({ sectionTitle: title, elements })
    }
  }

  // ── Step 3: 注入正确的页码 ──
  const totalPages = allSlideInfos.length
  for (let i = 0; i < allSlideInfos.length; i++) {
    const slideInfo = allSlideInfos[i]
    // 找到页码 text 元素并更新
    for (const el of slideInfo.elements) {
      if (el.name === 'decor' && el.type === 'text' && el.fontSize === 12 &&
          el.x === CANVAS_WIDTH - 140 && el.y === 18) {
        el.text = `${i} / ${totalPages - 1}`
        break
      }
    }
    // 封面和目录页不显示页码（封面无页码元素，目录页也无）
    if (i <= 1) {
      // 移除目录页可能带有的页码（如果 buildTOCSlide 没有添加则无需处理）
    }
  }

  // ── Step 4: 组装最终结果 ──
  const slides: KonvaSlide[] = allSlideInfos.map((info, i) => ({
    pageNumber: i,
    sectionTitle: info.sectionTitle,
    elements: info.elements,
  }))

  return slides
}

/**
 * 创建一个空白的新幻灯片。
 */
export function createBlankSlide(pageNumber: number): KonvaSlide {
  return {
    pageNumber,
    sectionTitle: `空白页 ${pageNumber}`,
    elements: [
      {
        id: `blank_bg_${pageNumber}`,
        type: 'rect',
        x: 0, y: 0,
        width: CANVAS_WIDTH, height: CANVAS_HEIGHT,
        fill: BRAND.white,
        name: 'decor',
      },
    ],
  }
}
