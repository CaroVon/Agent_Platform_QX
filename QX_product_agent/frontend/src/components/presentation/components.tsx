/**
 * Presentation Component Library —— 9 种组件的 React 渲染（P4）
 *
 * AI（Presentation Agent）只产出 Component{type, data} 的结构化数据；
 * 视觉（字体/间距/样式）由本层控制。
 */

import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart,
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  AlertTriangle, BarChart3, Image as ImageIcon, LayoutList,
  Quote as QuoteIcon, Table2, Timer, TrendingUp,
} from 'lucide-react'
import { EChart } from '@/components/presentation/EChart'
import type { PresentationComponent } from '@/types/presentation'

const CHART_COLORS = ['#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

// ─── 数据提取辅助 ──────────────────────────────────────────

function asText(data: Record<string, unknown>, key: string, fallback = ''): string {
  const value = data[key]
  return typeof value === 'string' ? value : fallback
}

interface ChartItem {
  label: string
  value: number
}

function asItems(data: Record<string, unknown>): ChartItem[] {
  const raw = data.items
  if (!Array.isArray(raw)) return []
  return raw
    .map((item) => {
      if (item && typeof item === 'object') {
        const label = asText(item as Record<string, unknown>, 'label', asText(item as Record<string, unknown>, 'name'))
        const value = Number((item as Record<string, unknown>).value)
        if (label && Number.isFinite(value)) return { label, value }
      }
      return null
    })
    .filter((x): x is ChartItem => x !== null)
}

function asRows(data: Record<string, unknown>): { columns: string[]; rows: string[][] } {
  const columns = Array.isArray(data.columns)
    ? data.columns.map(String)
    : []
  const rows = Array.isArray(data.rows)
    ? (data.rows as unknown[]).map((r) =>
        Array.isArray(r) ? r.map(String) : []
      )
    : []
  return { columns, rows }
}

// ─── 9 种组件 ─────────────────────────────────────────────

function Metric({ component }: { component: PresentationComponent }) {
  const value = asText(component.data, 'value')
  const label = asText(component.data, 'label')
  const em = component.emphasis === 'high'
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border bg-white/80 px-4 py-5 text-center shadow-sm">
      <div className={`font-bold tracking-tight ${em ? 'text-4xl text-[var(--p-primary)]' : 'text-3xl text-slate-800'}`}>
        {value}
      </div>
      {label && <div className="mt-1.5 text-xs text-slate-500">{label}</div>}
    </div>
  )
}

function TextBlock({ component }: { component: PresentationComponent }) {
  const title = asText(component.data, 'title')
  const text = asText(component.data, 'text', asText(component.data, 'content'))
  return (
    <div>
      {title && <div className="mb-1 text-sm font-semibold text-slate-700">{title}</div>}
      <div className="text-sm leading-relaxed text-slate-600">{text}</div>
    </div>
  )
}

function ChartBlock({ component }: { component: PresentationComponent }) {
  const chartType = asText(component.data, 'chart_type', 'bar')
  const items = asItems(component.data)
  if (!items.length) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed text-xs text-slate-400">
        <BarChart3 className="mr-1.5 h-3.5 w-3.5" /> 无图表数据
      </div>
    )
  }
  if (chartType === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={items} dataKey="value" nameKey="label" innerRadius={40} outerRadius={80} paddingAngle={2}>
            {items.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    )
  }
  if (chartType === 'line') {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={items}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={34} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2.5} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    )
  }
  if (chartType === 'radar') {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={items}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="label" tick={{ fontSize: 11 }} />
          <Radar dataKey="value" stroke="#4f46e5" fill="#6366f1" fillOpacity={0.4} />
        </RadarChart>
      </ResponsiveContainer>
    )
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={items}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} width={34} />
        <Tooltip />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {items.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function TableBlock({ component }: { component: PresentationComponent }) {
  const { columns, rows } = asRows(component.data)
  if (!rows.length) {
    return (
      <div className="flex h-24 items-center justify-center rounded-xl border border-dashed text-xs text-slate-400">
        <Table2 className="mr-1.5 h-3.5 w-3.5" /> 无表格数据
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-xl border bg-white/80 shadow-sm">
      <table className="w-full border-collapse text-xs">
        {columns.length > 0 && (
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c} className="bg-[var(--p-primary)] px-3 py-2 text-left font-medium text-white">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
              {row.map((cell, j) => (
                <td key={j} className="border-t border-slate-100 px-3 py-1.5 text-slate-600">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CardBlock({ component }: { component: PresentationComponent }) {
  const title = asText(component.data, 'title')
  const description = asText(component.data, 'description')
  const items = Array.isArray(component.data.items) ? component.data.items.map(String) : []
  return (
    <div className="flex h-full flex-col rounded-xl border bg-white/90 p-4 shadow-sm">
      {title && <div className="mb-1 text-sm font-semibold text-slate-800">{title}</div>}
      {description && <div className="mb-2 text-xs leading-relaxed text-slate-500">{description}</div>}
      {items.length > 0 && (
        <ul className="mt-auto space-y-1">
          {items.map((item) => (
            <li key={item} className="flex gap-1.5 text-xs text-slate-600">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-[var(--p-primary)]/70" />
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TimelineBlock({ component }: { component: PresentationComponent }) {
  const phases = Array.isArray(component.data.phases)
    ? (component.data.phases as Record<string, unknown>[])
    : []
  if (!phases.length) {
    return (
      <div className="flex h-24 items-center justify-center rounded-xl border border-dashed text-xs text-slate-400">
        <Timer className="mr-1.5 h-3.5 w-3.5" /> 无时间线数据
      </div>
    )
  }
  return (
    <div className="flex gap-3">
      {phases.map((phase, i) => (
        <div key={i} className="relative flex-1 rounded-xl border bg-white/90 p-3 shadow-sm">
          <div className="mb-1 flex items-center gap-1.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--p-primary)] text-[10px] font-bold text-white">
              {i + 1}
            </span>
            <span className="text-xs font-semibold text-slate-800">{asText(phase, 'name', asText(phase, 'phase'))}</span>
          </div>
          {asText(phase, 'period') && (
            <div className="mb-1 text-[10px] text-slate-400">{asText(phase, 'period')}</div>
          )}
          {Array.isArray(phase.milestones) && phase.milestones.length > 0 && (
            <ul className="space-y-0.5">
              {phase.milestones.map((m, j) => (
                <li key={j} className="flex gap-1 text-[11px] text-slate-600">
                  <span className="text-[var(--p-primary)]">✓</span> {String(m)}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

interface QuadrantPoint {
  name: string
  x: number
  y: number
  kind?: string
}

function MatrixBlock({ component }: { component: PresentationComponent }) {
  const chartType = asText(component.data, 'chart_type', 'quadrant')
  if (chartType === 'quadrant') {
    const points = (Array.isArray(component.data.points) ? component.data.points : []) as QuadrantPoint[]
    const xAxis = asText(component.data, 'x_axis', 'x')
    const yAxis = asText(component.data, 'y_axis', 'y')
    if (!points.length) {
      return (
        <div className="flex h-32 items-center justify-center rounded-xl border border-dashed text-xs text-slate-400">
          <LayoutList className="mr-1.5 h-3.5 w-3.5" /> 无象限数据
        </div>
      )
    }
    const isProduct = (p: QuadrantPoint) => p.kind === 'product' || p.kind === 'ours'

    // ECharts 象限图（美观度升级：双系列着色 + 中轴十字线 + 平滑散点 + 悬浮提示）
    const competitors = points.filter((p) => !isProduct(p)).map((p) => [p.x, p.y, p.name])
    const ours = points.filter(isProduct).map((p) => [p.x, p.y, p.name])
    const option = {
      grid: { top: 16, right: 20, bottom: 34, left: 36 },
      tooltip: {
        trigger: 'item',
        formatter: (p: { value: number[] }) => `${p.value[2]}<br/>${xAxis}: ${p.value[0]} · ${yAxis}: ${p.value[1]}`,
      },
      xAxis: {
        min: 0, max: 1, name: xAxis, nameLocation: 'middle', nameGap: 22,
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
        axisLabel: { fontSize: 10, color: '#94a3b8' },
      },
      yAxis: {
        min: 0, max: 1, name: yAxis,
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
        axisLabel: { fontSize: 10, color: '#94a3b8' },
      },
      series: [
        {
          type: 'scatter',
          name: '竞品',
          data: competitors,
          symbolSize: 12,
          itemStyle: { color: '#94a3b8', borderColor: '#64748b', borderWidth: 1 },
          label: { show: true, formatter: (p: { value: number[] }) => p.value[2], position: 'top', fontSize: 10, color: '#475569' },
          markLine: { silent: true, symbol: 'none', data: [{ xAxis: 0.5 }], lineStyle: { color: '#cbd5e1' } },
        },
        {
          type: 'scatter',
          name: '本产品',
          data: ours,
          symbolSize: 16,
          itemStyle: { color: '#4f46e5', borderColor: '#312e81', borderWidth: 1.5 },
          label: { show: true, formatter: (p: { value: number[] }) => p.value[2], position: 'top', fontSize: 11, fontWeight: 'bold', color: '#312e81' },
          markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0.5 }], lineStyle: { color: '#cbd5e1' } },
        },
      ],
    }
    return <EChart option={option} height={190} />
  }
  return <TableBlock component={{ ...component, type: 'table', data: { columns: component.data.columns, rows: component.data.rows } }} />
}

function QuoteBlock({ component }: { component: PresentationComponent }) {
  const quote = asText(component.data, 'quote', asText(component.data, 'text'))
  const author = asText(component.data, 'author')
  return (
    <div className="mx-auto max-w-xl rounded-xl border-l-4 border-[var(--p-primary)] bg-white/70 px-6 py-5 shadow-sm">
      <div className="flex gap-2 text-base font-medium leading-relaxed text-slate-700">
        <QuoteIcon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--p-primary)]" />
        {quote}
      </div>
      {author && <div className="mt-2 text-right text-xs text-slate-400">—— {author}</div>}
    </div>
  )
}

function ImageBlock({ component }: { component: PresentationComponent }) {
  const alt = asText(component.data, 'alt', asText(component.data, 'text', '概念图'))
  const src = asText(component.data, 'src')
  if (src) {
    return <img src={src} alt={alt} className="max-h-56 w-full rounded-xl object-cover shadow-sm" />
  }
  return (
    <div className="flex h-40 items-center justify-center rounded-xl border-2 border-dashed border-[var(--p-primary)]/30 bg-[var(--p-primary)]/5 text-xs text-slate-400">
      <ImageIcon className="mr-1.5 h-4 w-4" /> {alt}
    </div>
  )
}

export function ComponentRenderer({ component }: { component: PresentationComponent }) {
  switch (component.type) {
    case 'metric':
      return <Metric component={component} />
    case 'text':
      return <TextBlock component={component} />
    case 'chart':
      return <ChartBlock component={component} />
    case 'table':
      return <TableBlock component={component} />
    case 'card':
      return <CardBlock component={component} />
    case 'timeline':
      return <TimelineBlock component={component} />
    case 'matrix':
      return <MatrixBlock component={component} />
    case 'quote':
      return <QuoteBlock component={component} />
    case 'image':
      return <ImageBlock component={component} />
    default:
      return (
        <div className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-600">
          <AlertTriangle className="h-3.5 w-3.5" /> 未知组件类型
        </div>
      )
  }
}

// 供 layouts 使用的图标引用（保持 tree-shaking 清晰）
export { TrendingUp }
