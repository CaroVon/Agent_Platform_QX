/**
 * editor/studio/blocks —— 自定义块与组件类型注册
 *
 * 关键机制：isComponent —— 从 HTML 恢复组件类型，
 * 使加载的 DSL 组件（HTML 字符串）自动获得 traits（属性面板）。
 */

import type { Editor } from 'grapesjs'
import { componentToHtml } from './dslBridge'
import type { PresentationComponent } from '@/types/presentation'

interface BlockSpec {
  id: string
  label: string
  type: PresentationComponent['type']
  sample: Record<string, unknown>
  traits?: Array<Record<string, unknown>>
  category?: string
}

const BLOCK_SPECS: BlockSpec[] = [
  { id: 'dsl-text', label: '文本', type: 'text', sample: { title: '标题', text: '在这里输入文本…' } },
  {
    id: 'dsl-metric',
    label: '指标卡',
    type: 'metric',
    sample: { value: '1,000', label: '指标名称' },
    traits: [
      { type: 'text', name: 'data-value', label: '数值' },
      { type: 'text', name: 'data-label', label: '标签' },
    ],
  },
  {
    id: 'dsl-card',
    label: '卡片',
    type: 'card',
    sample: { title: '卡片标题', description: '卡片描述' },
    traits: [{ type: 'text', name: 'data-title', label: '标题' }],
  },
  {
    id: 'dsl-image',
    label: '图片',
    type: 'image',
    sample: { alt: '图片' },
    traits: [
      { type: 'text', name: 'data-src', label: '图片 URL' },
      { type: 'text', name: 'data-alt', label: '说明' },
    ],
  },
  {
    id: 'dsl-table',
    label: '表格',
    type: 'table',
    sample: {
      columns: ['列 1', '列 2'],
      rows: [
        ['A', 'B'],
        ['C', 'D'],
      ],
    },
  },
  { id: 'dsl-quote', label: '引用', type: 'quote', sample: { quote: '金句引用' } },
  {
    id: 'dsl-timeline',
    label: '时间线',
    type: 'timeline',
    sample: { phases: [{ name: '阶段一', milestones: ['里程碑 1', '里程碑 2'] }] },
  },
  {
    id: 'dsl-chart',
    label: '图表',
    type: 'chart',
    sample: { chart_type: 'bar', items: [{ label: 'A', value: 10 }] },
    traits: [
      {
        type: 'select',
        name: 'chart_kind',
        label: '图表类型',
        options: [
          { id: 'bar', name: '柱状图' },
          { id: 'line', name: '折线图' },
          { id: 'pie', name: '饼图' },
          { id: 'radar', name: '雷达图' },
        ],
      },
    ],
  },
  {
    id: 'dsl-matrix',
    label: '象限矩阵',
    type: 'matrix',
    sample: { chart_type: 'quadrant', x_axis: '价格', y_axis: '个性化', points: [] },
    traits: [
      { type: 'text', name: 'data-x_axis', label: 'X 轴' },
      { type: 'text', name: 'data-y_axis', label: 'Y 轴' },
    ],
  },
]

function dslTypeOf(el: HTMLElement): string {
  return el.getAttribute?.('data-dsl-type') ?? ''
}

type AttrModel = { getAttributes: () => Record<string, unknown> }

/** 属性变更时同步视图（trait 编辑 → 画布实时更新） */
function attrView(
  render: (model: AttrModel, el: HTMLElement) => void,
): Record<string, unknown> {
  return {
    events: {
      'change:attributes:value change:attributes:label change:attributes:title change:attributes:src change:attributes:alt change:attributes:x_axis change:attributes:y_axis change:attributes:chart_kind': 'syncAttrs',
      'change:attributes': 'syncAttrs',
    },
    onRender(this: { model: AttrModel; el: HTMLElement }) {
      render(this.model, this.el)
    },
    syncAttrs(this: { model: AttrModel; el: HTMLElement }) {
      render(this.model, this.el)
    },
  }
}

export function registerBlocks(editor: Editor): void {
  // ─── 组件类型注册（isComponent 恢复类型 + traits + 属性同步视图） ──
  const attrViews: Record<string, (m: { getAttributes: () => Record<string, unknown> }, el: HTMLElement) => void> = {
    metric: (model, el) => {
      const attrs = model.getAttributes() as Record<string, string>
      const v = el.querySelector('.dsl-metric-value')
      const l = el.querySelector('.dsl-metric-label')
      if (v) v.textContent = (attrs['data-value'] ?? attrs.value ?? '') as string
      if (l) l.textContent = (attrs['data-label'] ?? attrs.label ?? '') as string
    },
    card: (model, el) => {
      const attrs = model.getAttributes() as Record<string, string>
      const t = el.querySelector('.dsl-card-title')
      if (t) t.textContent = (attrs['data-title'] ?? attrs.title ?? '') as string
    },
    image: (model, el) => {
      const attrs = model.getAttributes() as Record<string, string>
      const img = el.querySelector('img')
      const src = (attrs['data-src'] ?? attrs.src ?? '') as string
      const alt = (attrs['data-alt'] ?? attrs.alt ?? '') as string
      if (img && src) img.setAttribute('src', src)
      if (img && alt !== undefined) img.setAttribute('alt', alt)
    },
    chart: (model, el) => {
      const attrs = model.getAttributes() as Record<string, string>
      const kind = (attrs['data-chart-kind'] ?? attrs.chart_kind ?? '') as string
      const label = el.querySelector('.dsl-placeholder-label')
      if (label && kind) {
        const map: Record<string, string> = { bar: '柱状图', line: '折线图', pie: '饼图', radar: '雷达图' }
        label.textContent = `图表（${map[kind] ?? kind}）`
      }
    },
    matrix: (model, el) => {
      const attrs = model.getAttributes() as Record<string, string>
      const hint = el.querySelector('.dsl-placeholder-hint')
      const xa = (attrs['data-x_axis'] ?? attrs.x_axis ?? '') as string
      const ya = (attrs['data-y_axis'] ?? attrs.y_axis ?? '') as string
      if (hint) hint.textContent = `X 轴：${xa || '—'} · Y 轴：${ya || '—'}`
    },
  }

  for (const spec of BLOCK_SPECS) {
    const renderer = attrViews[spec.type]
    const definition: Record<string, unknown> = {
      isComponent: (el: HTMLElement) => dslTypeOf(el) === spec.type,
      model: {
        defaults: {
          draggable: true,
          droppable: false,
          copyable: true,
          removable: true,
          traits: spec.traits ?? [],
        },
      },
      view: renderer ? attrView(renderer) : {},
    }
    // trait 变更 → model attributes 变更 → 同步画布视图（可靠路径）
    if (renderer) {
      definition.model = {
        defaults: {
          draggable: true,
          droppable: false,
          copyable: true,
          removable: true,
          traits: spec.traits ?? [],
        },
        init(this: { on: (ev: string, fn: () => void) => void; getEl: () => HTMLElement | null; getAttributes: () => Record<string, unknown> }) {
          const sync = () => {
            const el = this.getEl()
            if (el && renderer) renderer(this, el)
          }
          this.on('change:attributes', sync)
          // 延迟首次同步（DOM 就绪后）
          setTimeout(sync, 0)
        },
      }
    }
    editor.DomComponents.addType(spec.id, definition as never)
  }

  // ─── 块面板 ──────────────────────────────────────────────
  for (const spec of BLOCK_SPECS) {
    const sampleComp: PresentationComponent = {
      id: `new-${spec.type}-${Date.now()}`,
      type: spec.type,
      data: spec.sample,
    }
    editor.Blocks.add(spec.id, {
      label: spec.label,
      category: '演示组件',
      content: componentToHtml(sampleComp),
      attributes: { class: 'fa fa-cube' },
    })
  }

  // ─── 基础元素块 ──────────────────────────────────────────
  editor.Blocks.add('shape-divider', {
    label: '分割线',
    category: '基础元素',
    content:
      '<div data-dsl-type="divider" data-dsl-id="" style="height:1px;background:#cbd5e1;width:100%;margin:8px 0;"></div>',
  })
  editor.Blocks.add('shape-box', {
    label: '矩形',
    category: '基础元素',
    content:
      '<div data-dsl-type="shape" data-dsl-id="" style="width:120px;height:80px;background:#24415E1A;border:1px solid #24415E33;border-radius:12px;"></div>',
  })

  // 形状/分割线类型（可选中可删，无 DSL 语义）
  for (const kind of ['divider', 'shape']) {
    editor.DomComponents.addType(`base-${kind}`, {
      isComponent: (el: HTMLElement) => dslTypeOf(el) === kind,
      model: { defaults: { draggable: true, droppable: false, copyable: true, removable: true } },
    })
  }
}
