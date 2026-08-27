/**
 * ProductWorkspacePage —— AI Product Creation Canvas
 *
 * 四段式创作画布：
 *   1. Hero — 双模式输入（对话式 / 快速）
 *   2. AI Team Progress — 节点时间线 + 工具执行
 *   3. Generated Assets — 已生成资产（研究/PRD/设计/演示）
 *   4. New Idea — 紧凑输入 + Knowledge Context（始终跨跨）
 *
 * 两个断点：
 *   - waiting_approval + source_gathering → 资料审核
 *   - waiting_approval + 其他节点 → 人工确认
 */

import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  AlertCircle,
  Globe,
  Loader2,
  Pause,
  Play,
  ShoppingCart,
  Square,
  Upload,
  Zap,
  MessageSquare,
} from 'lucide-react'
import { ProjectHeader } from '@/components/workspace/ProjectHeader'
import { IdeaInput } from '@/components/workspace/IdeaInput'
import { ClarifyPanel } from '@/components/workspace/ClarifyPanel'
import { AssetPanel } from '@/components/workspace/AssetPanel'
import { KnowledgePanel } from '@/components/workspace/KnowledgePanel'
import {
  DesignStylePicker,
  type DesignStyleValue,
} from '@/components/workspace/DesignStylePicker'
import { AgentTimeline } from '@/components/ai/AgentTimeline'
import { ToolExecution } from '@/components/ai/ToolExecution'
import { StreamingMessage } from '@/components/ai/StreamingMessage'
import { PptLivePanel } from '@/components/ai/PptLivePanel'
import { productApi, type AmazonCollectionSummary, type PptOptions } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'
import { Button } from '@/components/common/button'
import { Input } from '@/components/common/input'
import { Badge } from '@/components/common/badge'
import {
  ProductLandscape,
  WindowGrid,
} from '@/components/illustrations/ModernIllustrations'
import { StatusLED } from '@/components/decor/RetroEffects'

/* ─── 通用 Section 容器（v2：IBM蓝商务版） ──────────── */
function Section({
  step,
  title,
  description,
  children,
  className,
}: {
  step: string
  title: string
  description?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        'overflow-hidden rounded-lg border border-border bg-card shadow-elev-sm',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3 border-b border-border px-7 py-4">
        <div>
          <div className="mb-0.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <span className="text-primary">第 {step} 阶段</span>
          </div>
          <h2 className="font-display text-[18px] font-semibold tracking-tight text-foreground">
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-[12px] text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
      <div className="px-7 py-6">{children}</div>
    </section>
  )
}

/* ─── Hero（无产品时显示） ────────────────────────── */
function HeroEmpty({
  inputMode,
  setInputMode,
  idea,
  setIdea,
  creating,
  handleGenerate,
  handleClarifyGenerate,
  dynamicSuggestions,
  handleSuggestionInput,
  pptOptions,
  designStyle,
  setDesignStyle,
}: {
  inputMode: 'chat' | 'quick'
  setInputMode: (m: 'chat' | 'quick') => void
  idea: string
  setIdea: (v: string) => void
  creating: boolean
  handleGenerate: () => void
  handleClarifyGenerate: (brief: string) => void
  dynamicSuggestions: string[]
  handleSuggestionInput: (v: string) => void
  pptOptions: PptOptions | null
  designStyle: DesignStyleValue
  setDesignStyle: (v: DesignStyleValue) => void
}) {
  return (
    <div className="space-y-8">
      {/* 顶部 Hero：标题 + 装饰图 */}
      <div className="relative overflow-hidden rounded-xl border border-border bg-card shadow-elev-md">
        <div className="pointer-events-none absolute inset-0 opacity-[0.07]">
          <ProductLandscape className="h-full w-full text-primary" />
        </div>
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent opacity-60" />

        <div className="relative grid gap-8 px-8 py-10 lg:grid-cols-[1.5fr_1fr] lg:px-12 lg:py-14">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[12px] font-medium text-primary">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary" />
              QX Product Studio · v2.0
            </div>
            <h1 className="mb-4 font-display text-[34px] font-semibold leading-[1.1] tracking-tight text-foreground lg:text-[44px]">
              从一句话到<br />
              <span className="text-primary">完整产品全案</span>
            </h1>
            <p className="mb-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
              输入产品想法，AI 团队统一采集网络与亚马逊真实数据，自动完成市场调研 → 竞品矩阵（MOD）→
              用户画像 → PRD → 路线图 → 演示文稿（竞品矩阵章节同进程制作，风格一致）。
              节点资产即时交付、PPT 制作全程可视化、断点干预、16:9 原生 PPT 导出。
            </p>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-muted-foreground">
              <div className="flex items-center gap-2">
                <StatusLED status="online" size="sm" />
                <span>统一采集 · 11 步流水线</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusLED status="processing" size="sm" />
                <span>双源数据（Tavily + Rainforest）</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusLED status="busy" size="sm" />
                <span>节点资产即时交付</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusLED status="warning" size="sm" />
                <span>16:9 PPT · MOD 章节同进程</span>
              </div>
            </div>
          </div>

          {/* 右侧装饰图组 */}
          <div className="relative hidden lg:block">
            <div className="relative h-full min-h-[280px] overflow-hidden rounded-lg border border-border bg-background/40 shadow-elev-sm">
              <div className="absolute inset-0 text-primary opacity-30">
                <WindowGrid className="h-full w-full" />
              </div>
              <div className="absolute right-4 top-4 flex items-center gap-2 rounded-md border border-border bg-card/80 px-2.5 py-1 text-[11px] text-foreground shadow-elev-xs backdrop-blur">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-success" />
                <span>Live Pipeline</span>
              </div>
              <div className="absolute bottom-4 left-4 right-4 grid grid-cols-3 gap-2">
                {[
                  { label: '市场分析', status: 'live' },
                  { label: '竞品矩阵', status: 'live' },
                  { label: '路线图', status: 'live' },
                ].map((s) => (
                  <div
                    key={s.label}
                    className="rounded-md border border-border bg-card/80 p-2 text-center shadow-elev-xs backdrop-blur"
                  >
                    <div className="font-mono text-[10px] uppercase text-muted-foreground">
                      {s.label}
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] font-medium text-success">
                      {s.status}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 输入区：chat / quick 双 Tab（与上方 Hero 同宽） */}
      <div className="w-full">
        <div className="mb-4 inline-flex rounded-lg border border-border bg-card p-1 shadow-elev-xs">
          {(
            [
              { key: 'chat' as const, label: '对话式输入', Icon: MessageSquare, hint: 'AI 追问补充' },
              { key: 'quick' as const, label: '快速输入', Icon: Zap, hint: '一句话直接生成' },
            ]
          ).map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setInputMode(m.key)}
              className={cn(
                'flex items-center gap-2 rounded-md px-4 py-2 text-[13px] font-medium transition-all',
                inputMode === m.key
                  ? 'bg-primary text-primary-foreground shadow-elev-sm'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
              )}
            >
              <m.Icon className="h-3.5 w-3.5" />
              {m.label}
            </button>
          ))}
        </div>

        <div className="rounded-lg border border-border bg-card p-6 shadow-elev-sm">
          {inputMode === 'chat' ? (
            <ClarifyPanel
              creating={creating}
              onGenerate={handleClarifyGenerate}
              dynamicSuggestions={dynamicSuggestions}
              onSuggestionDynamic={handleSuggestionInput}
            />
          ) : (
            <IdeaInput
              value={idea}
              onChange={setIdea}
              onSubmit={handleGenerate}
              creating={creating}
            />
          )}
        </div>

        {/* 设计风格（模板决定权）：主题 9 套预览 + 风格方法论 */}
        <div className="mt-3">
          <DesignStylePicker
            options={pptOptions}
            value={designStyle}
            onChange={setDesignStyle}
          />
        </div>
      </div>
    </div>
  )
}

/* ─── 资料审核（source_gathering gate） ───────────── */
function SourcesGate({
  product,
  sources,
  amazon,
  sourcesLoading,
  uploadingSource,
  onUpload,
  onApprove,
  onReject,
  onError,
}: {
  product: StudioProduct
  sources: Array<{
    title: string
    url: string
    content?: string
    weight?: number
    weight_label?: string
    weight_detail?: string
    selected?: boolean
    local?: boolean
  }>
  amazon: AmazonCollectionSummary | null
  sourcesLoading: boolean
  uploadingSource: boolean
  onUpload: (file: File) => Promise<void>
  onApprove: (selectedUrls: string[]) => Promise<void>
  onReject: () => Promise<void>
  onError: (msg: string) => void
}) {
  return (
    <Section
      step="01"
      title="资料审核"
      description="统一采集完成：Tavily 网络资料（可勾选）+ Rainforest 亚马逊真实数据（只读参考）。确认后继续。"
    >
      {/* ── 亚马逊采集摘要（只读，不参与勾选） ── */}
      {amazon && !amazon.error && (
        <div className="mb-5 rounded-lg border border-[#24415E]/20 bg-[#24415E]/[0.03] p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <ShoppingCart className="h-4 w-4 text-[#24415E]" />
            <span className="text-sm font-semibold">亚马逊真实数据已采集</span>
            <span className="font-mono text-[11px] text-muted-foreground">
              {amazon.keyword} · {amazon.n_products} ASIN · credits≈{amazon.credits}
              {amazon.fetched_at ? ` · ${amazon.fetched_at.slice(0, 10)}` : ''}
            </span>
            {amazon.source === 'mock' && (
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                ⚠️ mock 数据 · 非真实采集
              </span>
            )}
            <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              只读参考 · 不可筛选
            </span>
          </div>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              {
                label: '价格带',
                value: `$${amazon.price_range?.min ?? '—'} – $${amazon.price_range?.max ?? '—'}`,
              },
              { label: '均价', value: `$${amazon.price_range?.avg ?? '—'}` },
              { label: '平均评分', value: String(amazon.rating_avg ?? '—') },
              { label: '评论样本', value: String(amazon.reviews_count ?? 0) },
            ].map((k) => (
              <div key={k.label} className="rounded-md border border-border bg-card px-3 py-2">
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {k.label}
                </div>
                <div className="mt-0.5 text-[14px] font-semibold text-[#24415E]">{k.value}</div>
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12px]">
              <thead>
                <tr className="border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="py-1.5 pr-3">ASIN</th>
                  <th className="py-1.5 pr-3">竞品（Top 销量）</th>
                  <th className="py-1.5 pr-3 text-right">价格</th>
                  <th className="py-1.5 pr-3 text-right">评分</th>
                  <th className="py-1.5 pr-3 text-right">评论</th>
                  <th className="py-1.5 pr-3 text-right">月销≈</th>
                  <th className="py-1.5">分区</th>
                </tr>
              </thead>
              <tbody>
                {(amazon.top_asins ?? []).map((t) => (
                  <tr key={t.asin} className="border-b border-border/50">
                    <td className="py-1.5 pr-3 font-mono text-[11px] text-primary">{t.asin}</td>
                    <td className="max-w-[260px] truncate py-1.5 pr-3">
                      {t.brand ? <span className="font-medium">{t.brand} · </span> : null}
                      {t.title}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono">${t.current_price ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{t.rating ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{t.review_count ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{t.est_monthly_sales ?? '—'}</td>
                    <td className="py-1.5 text-muted-foreground">{t.zone}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[10px] text-muted-foreground/70">
            *Rainforest 实时采集；该数据将直接进入市场研究、竞品矩阵（MOD）与 PPT 的竞品矩阵章节，无需重复抓取。
          </p>
        </div>
      )}
      {amazon?.error && (
        <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/5 px-4 py-2.5 text-[12px] text-amber-700">
          亚马逊采集未完成（{amazon.error}）——将继续使用网络资料；竞品矩阵节点会自行重试采集。
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">已检索资料</span>
          <Badge variant="default">{sources.length} 条</Badge>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-1.5 border border-primary/40 bg-primary/10 px-3.5 py-2 text-[12px] font-medium text-primary transition-colors hover:bg-primary/20">
          <Upload className="h-3.5 w-3.5" />
          {uploadingSource ? '上传中…' : '上传本地资料'}
          <input
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            disabled={uploadingSource}
            onChange={async (e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (!file) return
              try {
                await onUpload(file)
              } catch (err) {
                onError(err instanceof Error ? err.message : '上传失败')
              }
            }}
          />
        </label>
      </div>

      {sourcesLoading ? (
        <div className="flex items-center justify-center gap-2 py-10 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>加载资料</span>
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      ) : (
        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {sources.map((src, i) => {
            const checked = src.selected !== false
            return (
              <label
                key={`${src.url}-${i}`}
                className="flex cursor-pointer items-start gap-3 border border-border bg-background/60 p-3 transition-colors hover:border-primary/40"
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                  checked={checked}
                  onChange={(e) => {
                    sources[i] = { ...src, selected: e.target.checked }
                    // 通过 onChange 回调：父组件需要 setSources，这里用 read-modify-write 模式
                    onUpload(new File([], '')).catch(() => {})
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] text-primary/70">
                      [{String(i + 1).padStart(3, '0')}]
                    </span>
                    <span className="truncate text-[13px] font-medium text-foreground">
                      {src.title}
                    </span>
                    {src.local && (
                      <span className="border border-accent/50 bg-accent/10 px-1.5 py-px font-mono text-[9px] uppercase tracking-[0.16em] text-accent">
                        LOCAL
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground/80">
                    {src.url}
                  </div>
                  {src.content && (
                    <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground/70">
                      {src.content}
                    </div>
                  )}
                </div>
                <Badge
                  variant={
                    (src.weight ?? 0.5) >= 0.8
                      ? 'success'
                      : (src.weight ?? 0.5) >= 0.6
                        ? 'info'
                        : (src.weight ?? 0.5) >= 0.45
                          ? 'warning'
                          : 'secondary'
                  }
                >
                  W·{src.weight_label ?? 'MID'}
                </Badge>
              </label>
            )
          })}
          {sources.length === 0 && !sourcesLoading && (
            <div className="border border-dashed border-border py-8 text-center font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              暂无资料 · 上传本地资料后继续
            </div>
          )}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          已选{' '}
          <span className="text-primary">
            {sources.filter((s) => s.selected !== false).length}
          </span>{' '}
          / {sources.length}
        </p>
        <div className="flex gap-2">
          <Button variant="destructive" size="sm" onClick={onReject}>
            放弃并终止
          </Button>
          <Button
            size="sm"
            disabled={sources.filter((s) => s.selected !== false).length === 0}
            onClick={() =>
              onApprove(
                sources.filter((s) => s.selected !== false).map((s) => s.url),
              )
            }
          >
            确认资料，继续生成 →
          </Button>
        </div>
      </div>
    </Section>
  )
}

/* ─── 人工批准门（其他节点；presentation 时展示大纲确认） ── */
function ApprovalGate({
  pausedNode,
  outline,
  onApprove,
  onReject,
}: {
  pausedNode: string
  /** P0.4：presentation 门时的页面大纲（title/insight/type） */
  outline?: Array<{ title?: string; insight?: string; type?: string }>
  onApprove: () => Promise<void>
  onReject: () => Promise<void>
}) {
  const isOutlineGate = pausedNode === 'presentation'
  return (
    <Section
      step="01"
      title={isOutlineGate ? '演示大纲确认' : '人工确认节点'}
      description={
        isOutlineGate
          ? '演示页清单已生成（含 MOD 竞品矩阵章节）。批准后进入评审与逐页创作（约 15-20 分钟），请先确认结构符合预期。'
          : `流水线已暂停于「${pausedNode}」节点，请审阅后决定继续或终止。`
      }
    >
      {isOutlineGate && outline && outline.length > 0 && (
        <div className="mb-4 max-h-72 overflow-y-auto rounded-lg border border-border">
          {outline.map((p, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 border-b border-border/50 px-4 py-2.5 last:border-0 ${
                (p.type || '').startsWith('mod_') ? 'bg-[#24415E]/[0.04]' : ''
              }`}
            >
              <span className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                P{String(i + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-medium">{p.title || '（未命名页）'}</span>
                  <span className="shrink-0 rounded bg-secondary px-1.5 py-px font-mono text-[9px] uppercase text-muted-foreground">
                    {p.type}
                  </span>
                  {(p.type || '').startsWith('mod_') && (
                    <span className="shrink-0 rounded bg-[#24415E]/10 px-1.5 py-px text-[9px] text-[#24415E]">
                      真实数据
                    </span>
                  )}
                </div>
                {p.insight && (
                  <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{p.insight}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-warning">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-semibold">等待人工批准</span>
        </div>
        <div className="flex gap-2">
          <Button variant="destructive" size="sm" onClick={onReject}>
            拒绝并终止
          </Button>
          <Button size="sm" onClick={onApprove}>
            {isOutlineGate ? `批准大纲，开始制作（${outline?.length ?? '?'} 页）` : '批准并继续'}
          </Button>
        </div>
      </div>
    </Section>
  )
}

/* ─── 任务控制面板 ──────────────────────────────────── */
function TaskControl({
  product,
  taskAction,
  onPause,
  onResume,
  onCancel,
}: {
  product: StudioProduct
  taskAction: 'pause' | 'resume' | 'cancel' | null
  onPause: () => void
  onResume: () => void
  onCancel: () => void
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-elev-sm">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        任务控制
      </div>
      <div className="flex flex-wrap gap-2">
        {product.status === 'paused' ? (
          <Button size="sm" onClick={onResume} disabled={taskAction !== null}>
            <Play className="h-3.5 w-3.5" />
            {taskAction === 'resume' ? '恢复中…' : '继续任务'}
          </Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={onPause} disabled={taskAction !== null}>
            <Pause className="h-3.5 w-3.5" />
            {taskAction === 'pause' ? '暂停中…' : '暂停任务'}
          </Button>
        )}
        <Button variant="destructive" size="sm" onClick={onCancel} disabled={taskAction !== null}>
          <Square className="h-3.5 w-3.5" />
          {taskAction === 'cancel' ? '结束中…' : '结束任务'}
        </Button>
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-muted-foreground/70">
        暂停会保留当前资产；结束任务后不会继续生成。
      </p>
    </div>
  )
}

export function ProductWorkspacePage() {
  const location = useLocation()
  const templateIdea = (location.state as { templateIdea?: string } | null)?.templateIdea

  // ── 输入模式 ──
  const [inputMode, setInputMode] = useState<'chat' | 'quick'>('quick')

  // ── 基础状态 ──
  const [idea, setIdea] = useState(templateIdea ?? '')
  const [dynamicSuggestions, setDynamicSuggestions] = useState<string[]>([])
  const [creating, setCreating] = useState(false)
  // 模板选择权（设计主题/风格方法论；null = AI 自主决策）
  const [pptOptions, setPptOptions] = useState<PptOptions | null>(null)
  const [designStyle, setDesignStyle] = useState<DesignStyleValue>({
    themeId: null,
    styleId: null,
  })

  useEffect(() => {
    let alive = true
    productApi
      .pptOptions()
      .then((opts) => {
        if (alive) setPptOptions(opts)
      })
      .catch(() => {
        /* 选项加载失败不阻塞创建（AI 自动匹配兜底） */
      })
    return () => {
      alive = false
    }
  }, [])
  const [product, setProduct] = useState<StudioProduct | null>(null)
  const [recent, setRecent] = useState<Array<{ product_id: string; idea: string; status: string }>>([])
  const [loadError, setLoadError] = useState('')
  const [eventLogs, setEventLogs] = useState<Array<{ ts: string; node: string; status: string; detail?: string }>>([])

  // ── 资料审核（source_gathering 门） ──
  const [sources, setSources] = useState<Array<{
    title: string
    url: string
    content?: string
    weight?: number
    weight_label?: string
    weight_detail?: string
    selected?: boolean
    local?: boolean
  }>>([])
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const [uploadingSource, setUploadingSource] = useState(false)
  const [amazonSummary, setAmazonSummary] = useState<AmazonCollectionSummary | null>(null)

  // ── 任务控制 ──
  const [taskAction, setTaskAction] = useState<'pause' | 'resume' | 'cancel' | null>(null)
  const pollTimer = useRef<number | null>(null)
  const suggestTimer = useRef<number | null>(null)

  const isActive = product !== null && (product.status === 'queued' || product.status === 'running')
  const pausedNode =
    product?.status === 'waiting_approval'
      ? (product.error_message?.replace('等待人工确认节点: ', '') ?? '')
      : ''

  // ── P0.3：SSE 进度事件订阅（秒级推送触发即时拉取；失败退化为纯轮询） ──
  useEffect(() => {
    if (!product?.product_id || !isActive) return
    let es: EventSource | null = null
    try {
      const base = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')
      es = new EventSource(`${base}/api/v1/product/${product.product_id}/events`)
      const pid = product.product_id
      es.addEventListener('progress', () => {
        productApi.get(pid).then(setProduct).catch(() => {})
        productApi.logs(pid).then((r) => setEventLogs(r.logs)).catch(() => {})
      })
      es.onerror = () => es?.close()
    } catch {
      /* EventSource 不可用时纯轮询 */
    }
    return () => es?.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, isActive])

  // ──────────────── 数据加载 ────────────────

  const loadRecent = async () => {
    try {
      setRecent(await productApi.list(0, 10))
    } catch {
      /* 非关键路径 */
    }
  }

  const loadProduct = async (id: string) => {
    try {
      setLoadError('')
      const p = await productApi.get(id)
      setProduct(p)
      try {
        localStorage.setItem('qx-current-project', p.idea)
      } catch {
        /* 忽略 */
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    loadRecent()
  }, [])

  // 资料审核：进入 waiting_approval 且暂停于 source_gathering 时拉取
  useEffect(() => {
    if (product?.status !== 'waiting_approval' || pausedNode !== 'source_gathering') return
    let cancelled = false
    setSourcesLoading(true)
    productApi
      .getSources(product.product_id)
      .then((d) => {
        if (!cancelled) {
          setSources(d.sources ?? [])
          setAmazonSummary(d.amazon ?? null)
        }
      })
      .catch(() => {
        /* 拉取失败保持空 */
      })
      .finally(() => {
        if (!cancelled) setSourcesLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, product?.status, pausedNode])

  // 轮询运行中状态
  useEffect(() => {
    if (!product || !isActive) return
    pollTimer.current = window.setInterval(async () => {
      try {
        const fresh = await productApi.get(product.product_id)
        const prevStatus = product.status
        setProduct(fresh)
        productApi
          .logs(product.product_id)
          .then((r) => setEventLogs(r.logs))
          .catch(() => {})
        if (fresh.status === 'completed' || fresh.status === 'failed') {
          if (pollTimer.current) window.clearInterval(pollTimer.current)
          loadRecent()
          if (prevStatus !== fresh.status && 'Notification' in window) {
            try {
                if (Notification.permission === 'granted') {
                  new Notification(
                    fresh.status === 'completed' ? '产品资产已生成' : '产品生成失败',
                    {
                      body:
                        fresh.status === 'completed'
                          ? `「${fresh.idea}」的研究/PRD/设计/演示资产已就绪`
                          : `「${fresh.idea}」：${fresh.error_message || '请查看详情'}`,
                    },
                  )
                } else if (Notification.permission === 'default') {
                  Notification.requestPermission()
                }
              } catch {
                /* 通知不可用时静默 */
              }
          }
        }
      } catch {
        /* 单次失败继续轮询 */
      }
    }, 3000)
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, isActive])

  // ──────────────── 操作回调 ────────────────

  const handleGenerate = async () => {
    const trimmed = idea.trim()
    if (!trimmed || creating) return
    setCreating(true)
    setLoadError('')
    try {
      const created = await productApi.create(trimmed, {
        theme_id: designStyle.themeId,
        style_id: designStyle.styleId,
      })
      await loadProduct(created.product_id)
      loadRecent()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  // 对话式：brief 直接进入流水线
  const handleClarifyGenerate = async (brief: string) => {
    if (!brief.trim() || creating) return
    setCreating(true)
    setLoadError('')
    try {
      const created = await productApi.create(brief, {
        theme_id: designStyle.themeId,
        style_id: designStyle.styleId,
      })
      await loadProduct(created.product_id)
      loadRecent()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  // P1：输入停顿 800ms 后请求 LLM 动态补全建议
  const handleSuggestionInput = (input: string) => {
    if (suggestTimer.current) window.clearTimeout(suggestTimer.current)
    if (!input.trim() || input.trim().length < 2) {
      setDynamicSuggestions([])
      return
    }
    suggestTimer.current = window.setTimeout(async () => {
      try {
        const r = await productApi.suggest(input.trim())
        setDynamicSuggestions(r.suggestions ?? [])
      } catch {
        setDynamicSuggestions([])
      }
    }, 800)
  }

  const handleTaskAction = async (action: 'pause' | 'resume' | 'cancel') => {
    if (!product || taskAction) return
    if (action === 'cancel' && !window.confirm('确定结束该任务吗？结束后不会继续生成。')) return
    setTaskAction(action)
    setLoadError('')
    try {
      if (action === 'pause') await productApi.pause(product.product_id)
      if (action === 'resume') await productApi.resume(product.product_id)
      if (action === 'cancel') await productApi.cancel(product.product_id)
      await loadProduct(product.product_id)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '任务操作失败')
    } finally {
      setTaskAction(null)
    }
  }

  // 资料上传（SourceGathering gate）
  const handleSourceUpload = async (file: File) => {
    if (!product) return
    setUploadingSource(true)
    try {
      const r = await productApi.uploadSource(product.product_id, file)
      setSources((prev) => [...prev, r.source as typeof prev[number]])
    } finally {
      setUploadingSource(false)
    }
  }

  // ──────────────── 渲染 ────────────────

  return (
    <div className="space-y-10">
      {/* Hero：有产品 → ProjectHeader；无产品 → 输入区 */}
      {product ? (
        <ProjectHeader product={product} />
      ) : (
        <HeroEmpty
          inputMode={inputMode}
          setInputMode={setInputMode}
          idea={idea}
          setIdea={setIdea}
          creating={creating}
          handleGenerate={handleGenerate}
          handleClarifyGenerate={handleClarifyGenerate}
          dynamicSuggestions={dynamicSuggestions}
          handleSuggestionInput={handleSuggestionInput}
          pptOptions={pptOptions}
          designStyle={designStyle}
          setDesignStyle={setDesignStyle}
        />
      )}

      {/* 错误条 */}
      {loadError && (
        <div className="flex items-center gap-2 border border-destructive/40 bg-destructive/10 px-5 py-3 font-mono text-[12px] text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="font-semibold">[ERROR]</span>
          <span>{loadError}</span>
        </div>
      )}

      {/* 资料审核（SourceGathering gate） */}
      {product?.status === 'waiting_approval' && pausedNode === 'source_gathering' && (
        <SourcesGate
          product={product}
          sources={sources}
          amazon={amazonSummary}
          sourcesLoading={sourcesLoading}
          uploadingSource={uploadingSource}
          onUpload={handleSourceUpload}
          onError={setLoadError}
          onApprove={async (selectedUrls) => {
            try {
              await productApi.approveNode(product.product_id, 'source_gathering', selectedUrls)
              await loadProduct(product.product_id)
            } catch (err) {
              setLoadError(err instanceof Error ? err.message : '操作失败')
            }
          }}
          onReject={async () => {
            try {
              await productApi.rejectNode(product.product_id, 'source_gathering')
              await loadProduct(product.product_id)
            } catch (err) {
              setLoadError(err instanceof Error ? err.message : '操作失败')
            }
          }}
        />
      )}

      {/* 其他节点等待人工批准 */}
      {product?.status === 'waiting_approval' && pausedNode !== 'source_gathering' && (
        <ApprovalGate
          pausedNode={pausedNode}
          outline={
            pausedNode === 'presentation' && product?.presentation
              ? (product.presentation as { pages?: Array<{ title?: string; insight?: string; type?: string }> }).pages
              : undefined
          }
          onApprove={async () => {
            try {
              await productApi.approveNode(product.product_id, pausedNode)
              await loadProduct(product.product_id)
            } catch (err) {
              setLoadError(err instanceof Error ? err.message : '批准失败')
            }
          }}
          onReject={async () => {
            try {
              await productApi.rejectNode(product.product_id, pausedNode)
              await loadProduct(product.product_id)
            } catch (err) {
              setLoadError(err instanceof Error ? err.message : '拒绝失败')
            }
          }}
        />
      )}

      {/* 最近产品（无当前产品时引导） */}
      {!product && recent.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            最近产品：
          </span>
          {recent.map((item) => (
            <button
              key={item.product_id}
              type="button"
              onClick={() => loadProduct(item.product_id)}
              className="border border-border bg-card px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary"
            >
              <span className="text-primary">▸</span> {item.idea} · {item.status}
            </button>
          ))}
        </div>
      )}

      {/* ─── AI Team Progress（双栏工作台：左时间线 / 右 PPT 可视化+控制） ─── */}
      {product && (
        <Section step="02" title="AI Team Progress" description="统一采集 → 研究 → 竞品 → 策略 → 设计 → 演示（含 MOD 章节）→ 同进程 PPT 制作 → 交付">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <div className="min-w-0">
              <AgentTimeline
                nodeStatus={product.node_status ?? {}}
                nodeModels={product.node_models ?? {}}
                productStatus={product.status}
                logs={eventLogs}
              />
            </div>
            <div className="space-y-4 lg:sticky lg:top-6 lg:self-start">
              <PptLivePanel
                productId={product.product_id}
                active={product.node_status?.ppt_design === 'running'}
              />
              <TaskControl
                product={product}
                taskAction={taskAction}
                onPause={() => handleTaskAction('pause')}
                onResume={() => handleTaskAction('resume')}
                onCancel={() => handleTaskAction('cancel')}
              />
              <div>
                <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  工具与检查
                </div>
                <ToolExecution nodeStatus={product.node_status ?? {}} />
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* 流式消息 */}
      {product && (
        <StreamingMessage
          active={isActive}
          latestEvent={eventLogs.length > 0 ? eventLogs[eventLogs.length - 1] : undefined}
        />
      )}

      {/* 失败提示 */}
      {product?.status === 'failed' && (
        <div className="border border-destructive/40 bg-destructive/10 px-6 py-4 font-mono text-[12px] text-destructive">
          <p className="font-semibold">
            <span className="animate-pulse-dot">[ERROR]</span> 流水线失败 ·{' '}
            {product.error_message ?? '未知错误'}
          </p>
          {product.errors && Object.keys(product.errors).length > 0 && (
            <ul className="mt-2 space-y-1 text-[11px]">
              {Object.entries(product.errors).map(([node, err]) => (
                <li key={node}>
                  <span className="text-destructive-foreground/80">▸ {node}</span>: {err}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* ─── Generated Assets（渐进交付：节点完成即出现） ─── */}
      {product && (
        <Section
          step="03"
          title="Generated Product Assets"
          description="研究 / 竞品矩阵（MOD）/ PRD / 设计 / 演示 — 节点完成即交付，可先行预览下载"
        >
          <AssetPanel
            product={product}
            onRefresh={() => product && loadProduct(product.product_id)}
          />
        </Section>
      )}

      {/* ─── New Idea（紧凑输入） ──────────── */}
      {product && (
        <Section
          step="04"
          title="New Idea"
          description="启动下一个产品想法"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-primary">
              ▸ INPUT
            </span>
            <Input
              type="text"
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
              placeholder="输入下一个产品想法…"
              className="h-10 flex-1"
            />
            <Button onClick={handleGenerate} disabled={creating || !idea.trim()}>
              {creating ? '启动中…' : '启动生成'}
            </Button>
          </div>
        </Section>
      )}

      {/* ─── Knowledge Context（始终显示） ──────────── */}
      <Section
        step={product ? '05' : '03'}
        title="Knowledge Context"
        description="三层知识库：任务知识 / 领域经验 / 全局资产"
      >
        <KnowledgePanel />
      </Section>
    </div>
  )
}