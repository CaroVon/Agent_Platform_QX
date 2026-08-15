/**
 * editor/studio/dslBridge —— Presentation DSL ↔ GrapesJS 双向转换
 *
 * 通道设计：每个 DSL 组件映射为带 data-dsl-* 属性的 GrapesJS 块；
 * 组件数据用 GrapesJS 的 {[ attr ]} 插值绑定 attributes，
 * traits（属性面板）直接编辑这些 attributes → 保存时反向收集。
 */

import type { PresentationComponent, PresentationDSL, PresentationPage } from '@/types/presentation'
import type { Component as GComponent, Editor } from 'grapesjs'

export interface DslMeta {
  type: PresentationComponent['type']
  id: string
  data: Record<string, unknown>
}

// ─── DSL → GrapesJS HTML ────────────────────────────────────

export function componentToHtml(comp: PresentationComponent): string {
  const data = comp.data ?? {}
  const json = JSON.stringify(data).replace(/"/g, '&quot;')
  const head = `data-dsl-type="${comp.type}" data-dsl-id="${comp.id}" data-dsl-data="${json}"`

  switch (comp.type) {
    case 'text': {
      const title = String(data.title ?? '')
      const text = String(data.text ?? data.content ?? '')
      return `
        <div ${head} class="dsl-text">
          ${title ? `<div class="dsl-text-title">${title}</div>` : ''}
          <div class="dsl-text-body" contenteditable="true">${text}</div>
        </div>`
    }
    case 'metric': {
      return `
        <div ${head} class="dsl-metric"
             data-value="${String(data.value ?? '')}" data-label="${String(data.label ?? '')}">
          <div class="dsl-metric-value">${String(data.value ?? '')}</div>
          <div class="dsl-metric-label">${String(data.label ?? '')}</div>
        </div>`
    }
    case 'card': {
      const title = String(data.title ?? '')
      const desc = String(data.description ?? '')
      return `
        <div ${head} class="dsl-card" data-title="${title}" data-description="">
          <div class="dsl-card-title">${title}</div>
          <div class="dsl-card-desc" contenteditable="true">${desc}</div>
        </div>`
    }
    case 'quote': {
      const quote = String(data.quote ?? data.text ?? '')
      return `
        <div ${head} class="dsl-quote">
          <div class="dsl-quote-body" contenteditable="true">${quote}</div>
        </div>`
    }
    case 'image': {
      const src = String(data.src ?? '')
      const alt = String(data.alt ?? data.text ?? '')
      return `
        <div ${head} class="dsl-image" data-src="${src}" data-alt="${alt}">
          ${src
            ? `<img src="${src}" alt="${alt}" />`
            : `<div class="dsl-image-placeholder">双击或从右侧拖入图片</div>`}
        </div>`
    }
    case 'table': {
      const columns = (data.columns as string[]) ?? []
      const rows = (data.rows as string[][]) ?? []
      const headHtml = columns.length
        ? `<thead><tr>${columns.map((c) => `<th>${c}</th>`).join('')}</tr></thead>`
        : ''
      const bodyHtml = `<tbody>${rows
        .map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`)
        .join('')}</tbody>`
      return `<table ${head} class="dsl-table">${headHtml}${bodyHtml}</table>`
    }
    case 'timeline': {
      const phases = (data.phases as Record<string, unknown>[]) ?? []
      const items = phases
        .map(
          (p) => `
        <div class="dsl-timeline-item">
          <span class="dsl-timeline-num"></span>
          <div>
            <div class="dsl-timeline-name" contenteditable="true">${String(p.name ?? p.phase ?? '')}</div>
            <div class="dsl-timeline-milestones" contenteditable="true">${String(
              ((p.milestones as string[]) ?? []).join('、'),
            )}</div>
          </div>
        </div>`,
        )
        .join('')
      return `<div ${head} class="dsl-timeline">${items}</div>`
    }
    case 'chart':
    case 'matrix': {
      const label = comp.type === 'chart' ? '图表（Chart）' : '矩阵（Matrix）'
      const xAxis = String(data.x_axis ?? '')
      const yAxis = String(data.y_axis ?? '')
      return `
        <div ${head} class="dsl-placeholder" data-x_axis="${xAxis}" data-y_axis="${yAxis}">
          <div class="dsl-placeholder-icon">${comp.type === 'chart' ? '📊' : '🎯'}</div>
          <div class="dsl-placeholder-label">${label}</div>
          <div class="dsl-placeholder-hint">数据由属性面板 JSON 编辑，导出时渲染为图表</div>
        </div>`
    }
    default:
      return `<div ${head} class="dsl-text"><div contenteditable="true">${JSON.stringify(data)}</div></div>`
  }
}

export function pageToHtml(page: PresentationPage): string {
  return `<section class="editor-page" data-page-id="${page.id}">
    <header class="editor-page-header">
      <h2>${page.title}</h2>
      ${page.subtitle ? `<p>${page.subtitle}</p>` : ''}
      ${page.insight ? `<div class="editor-page-insight">${page.insight}</div>` : ''}
    </header>
    <div class="editor-page-body">
      ${page.components.map(componentToHtml).join('\n')}
    </div>
  </section>`
}

// ─── GrapesJS → DSL ─────────────────────────────────────────

function parseDslData(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw.replace(/&quot;/g, '"')) as Record<string, unknown>
  } catch {
    return {}
  }
}

/**
 * GrapesJS Component → PresentationComponent
 * 属性值从组件 model 的 attributes 读取（GrapesJS 会清理 DOM 上的
 * 无前缀自定义属性，但保留在 model 中）；文本类内容从 DOM 读取。
 */
export function componentToDsl(comp: GComponent, index: number): PresentationComponent {
  const attrs = (comp.getAttributes() ?? {}) as Record<string, string>
  const type = (attrs['data-dsl-type'] as PresentationComponent['type']) || 'text'
  const id = attrs['data-dsl-id'] || `edited-${index}`
  const original = parseDslData(attrs['data-dsl-data'] ?? '')
  const data: Record<string, unknown> = { ...original }
  const el = comp.getEl() as HTMLElement | null

  switch (type) {
    case 'text': {
      const title = el?.querySelector('.dsl-text-title')?.textContent?.trim() ?? ''
      const body = el?.querySelector('.dsl-text-body')?.textContent?.trim() ?? ''
      if (title) data.title = title
      data.text = body
      break
    }
    case 'metric': {
      data.value = attrs['data-value'] ?? attrs.value ?? ''
      data.label = attrs['data-label'] ?? attrs.label ?? ''
      break
    }
    case 'card': {
      data.title = attrs['data-title'] ?? attrs.title ?? original.title ?? ''
      data.description = el?.querySelector('.dsl-card-desc')?.textContent?.trim() ?? ''
      break
    }
    case 'quote': {
      data.quote = el?.querySelector('.dsl-quote-body')?.textContent?.trim() ?? ''
      break
    }
    case 'image': {
      const img = el?.querySelector('img')
      data.src = attrs['data-src'] ?? attrs.src ?? img?.getAttribute('src') ?? ''
      data.alt = attrs['data-alt'] ?? attrs.alt ?? img?.getAttribute('alt') ?? ''
      break
    }
    case 'table': {
      const columns = Array.from(el?.querySelectorAll('thead th') ?? []).map((th) => th.textContent?.trim() ?? '')
      const rows = Array.from(el?.querySelectorAll('tbody tr') ?? []).map((tr) =>
        Array.from(tr.querySelectorAll('td')).map((td) => td.textContent?.trim() ?? ''),
      )
      data.columns = columns
      data.rows = rows
      break
    }
    case 'timeline': {
      const phases = Array.from(el?.querySelectorAll('.dsl-timeline-item') ?? []).map((item) => ({
        name: item.querySelector('.dsl-timeline-name')?.textContent?.trim() ?? '',
        milestones: (item.querySelector('.dsl-timeline-milestones')?.textContent ?? '')
          .split('、')
          .map((s) => s.trim())
          .filter(Boolean),
      }))
      data.phases = phases
      break
    }
    case 'chart':
    case 'matrix': {
      const xa = attrs['data-x_axis'] ?? attrs.x_axis
      const ya = attrs['data-y_axis'] ?? attrs.y_axis
      const kind = attrs['data-chart-kind'] ?? attrs.chart_kind
      if (xa) data.x_axis = xa
      if (ya) data.y_axis = ya
      if (kind) data.chart_type = kind
      break
    }
    default:
      break
  }

  return { id, type, data, emphasis: 'normal' }
}

const DSL_TYPES = new Set([
  'text', 'metric', 'card', 'quote', 'image', 'table', 'timeline', 'chart', 'matrix',
])

/**
 * DOM 收集（data-* 属性 GrapesJS 保留，不清理）：
 * 遍历画布 DOM 的 [data-dsl-type] 节点，并通过 editor 的组件注册表
 * 找到对应组件 model 读取 attributes（双保险：DOM 优先）。
 */
export function grapesToPage(editor: Editor, pageId: string, fallback: PresentationPage): PresentationPage {
  const doc = editor.Canvas.getDocument()
  if (!doc) return fallback
  const nodes = Array.from(doc.querySelectorAll<HTMLElement>('[data-dsl-type]'))
  const components = nodes
    .map((el, index) => componentFromEl(editor, el, index))
    .filter((c) => DSL_TYPES.has(c.type)) // 形状/分割线等基础元素不进入 DSL

  // 页面标题允许编辑
  const header = doc.querySelector('.editor-page-header h2')
  const title = header?.textContent?.trim() || fallback.title

  return { ...fallback, title, components }
}

/** DOM 节点 → DSL 组件（优先取同名组件的 model attributes，回退 DOM 属性） */
function componentFromEl(editor: Editor, el: HTMLElement, index: number): PresentationComponent {
  // 尝试找对应组件 model
  const comps: GComponent[] = []
  const walk = (c: GComponent) => {
    const a = (c.getAttributes?.() ?? {}) as Record<string, string>
    if (a['data-dsl-id'] === el.getAttribute('data-dsl-id')) comps.push(c)
    const children = c.components?.()
    if (children) children.forEach((child: GComponent) => walk(child))
  }
  const wrapper = editor.getWrapper()
  if (wrapper) walk(wrapper)
  if (comps.length === 1) {
    return componentToDsl(comps[0], index)
  }
  return componentFromDom(el, index)
}

/** DOM 属性回退收集（data-* 前缀，GrapesJS 保留） */
function componentFromDom(el: HTMLElement, index: number): PresentationComponent {
  const type = (el.getAttribute('data-dsl-type') as PresentationComponent['type']) || 'text'
  const id = el.getAttribute('data-dsl-id') || `edited-${index}`
  const data: Record<string, unknown> = parseDslData(el.getAttribute('data-dsl-data') ?? '')
  switch (type) {
    case 'metric': {
      data.value = el.getAttribute('data-value') ?? ''
      data.label = el.getAttribute('data-label') ?? ''
      break
    }
    case 'card': {
      data.title = el.getAttribute('data-title') ?? ''
      data.description = el.querySelector('.dsl-card-desc')?.textContent?.trim() ?? ''
      break
    }
    case 'text': {
      const t = el.querySelector('.dsl-text-title')?.textContent?.trim()
      if (t) data.title = t
      data.text = el.querySelector('.dsl-text-body')?.textContent?.trim() ?? ''
      break
    }
    default:
      break
  }
  return { id, type, data, emphasis: 'normal' }
}

export function grapesToDsl(
  editor: Editor,
  original: PresentationDSL,
  currentIndex: number,
): PresentationDSL {
  const pages = original.pages.map((p, i) =>
    i === currentIndex ? grapesToPage(editor, p.id, p) : p,
  )
  return { ...original, pages }
}
