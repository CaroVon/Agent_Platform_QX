/**
 * DesignStudioLibrary —— Design Studio v2 任务级图片资产库
 *
 * 结构（对应后端 design_studio 资产库索引）：
 *   1. 组合设计：组合总图（整体设计思路 + 图）+ 其下组件（组件文字 + 组件图）
 *   2. 图片资产库：全部「设计思路 + 图片」条目（流水线导入 / 用户创建）
 *
 * 交互：
 *   - 每张图附带的文字可直接编辑保存，再「重新生成」按新文字生图
 *   - 组件 / 组合分别生成、分别重新生成
 *   - 单张下载 / 全部打包下载（ZIP）
 *   - 智能拆解组件（LLM 建议 → 确认创建）、版本历史回滚、大图预览
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Boxes, Download, FileImage, History, Layers, Loader2, Plus,
  RefreshCw, Sparkles, Trash2, Wand2, X, ZoomIn,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/common/dialog'
import { designStudioApi, type ComponentSuggestion } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { DesignStudioItem, DesignStudioLibrary, DesignStudioVersion } from '@/types/studio'
import type { StudioProduct } from '@/types/studio'

const KIND_META: Record<DesignStudioItem['kind'], { label: string; cls: string }> = {
  composite: { label: '组合总图', cls: 'bg-indigo-500/10 text-indigo-600' },
  component: { label: '组件', cls: 'bg-sky-500/10 text-sky-600' },
  standalone: { label: '资产', cls: 'bg-slate-500/10 text-slate-600' },
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

function fmtTime(ts: string): string {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─────────────────────────────────────────────────────────────
// 图片预览（Lightbox）
// ─────────────────────────────────────────────────────────────

function PreviewModal({ url, title, onClose }: { url: string; title: string; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl border-0 bg-transparent p-0 shadow-none [&>button]:bg-black/50 [&>button]:text-white">
        <div className="overflow-hidden rounded-xl bg-card">
          <img src={url} alt={title} className="max-h-[78vh] w-full object-contain" />
          <div className="flex items-center justify-between border-t bg-card px-4 py-2.5">
            <span className="truncate pr-4 text-xs text-muted-foreground">{title}</span>
            <a
              href={url}
              download
              className="flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs hover:bg-accent"
            >
              <Download className="h-3.5 w-3.5" /> 下载原图
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ─────────────────────────────────────────────────────────────
// 版本历史
// ─────────────────────────────────────────────────────────────

function VersionDialog({
  item, productId, onRestore, onClose,
}: {
  item: DesignStudioItem
  productId: string
  onRestore: (index: number) => Promise<void>
  onClose: () => void
}) {
  const [restoring, setRestoring] = useState<number | null>(null)
  const [error, setError] = useState('')
  const versions: DesignStudioVersion[] = item.versions ?? []

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-base">版本历史 · {item.name}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[52vh] space-y-2.5 overflow-y-auto pr-1">
          {versions.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              暂无历史版本（每次重新生成都会保留上一版，最多 5 版）
            </p>
          )}
          {versions.map((v, i) => (
            <div key={`${v.ts}-${i}`} className="flex items-center gap-3 rounded-lg border bg-background p-2.5">
              <div className="h-14 w-20 shrink-0 overflow-hidden rounded-md border bg-secondary/40">
                {v.image ? (
                  <img src={v.image.url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground/50">
                    <FileImage className="h-4 w-4" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] text-muted-foreground">v{versions.length - i} · {fmtTime(v.ts)}</div>
                <div className="mt-0.5 line-clamp-2 text-xs text-foreground/80">{v.text || '（空文字）'}</div>
              </div>
              <Button
                size="sm"
                variant="outline"
                loading={restoring === i}
                onClick={async () => {
                  setRestoring(i)
                  setError('')
                  try {
                    await onRestore(i)
                    onClose()
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e))
                  } finally {
                    setRestoring(null)
                  }
                }}
              >
                恢复
              </Button>
            </div>
          ))}
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─────────────────────────────────────────────────────────────
// 设计思路编辑器（textarea 局部草稿，显式「保存文字」才提交）
// ─────────────────────────────────────────────────────────────

function TextEditor({
  value, onSave, placeholder,
}: {
  value: string
  onSave: (text: string) => Promise<void>
  placeholder?: string
}) {
  const [draft, setDraft] = useState(value)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    setDraft(value)
    setDirty(false)
  }, [value])

  return (
    <div className="space-y-1.5">
      <textarea
        value={draft}
        placeholder={placeholder ?? '填写该图的设计思路（保存后可按新文字重新生图）…'}
        onChange={(e) => {
          setDraft(e.target.value)
          setDirty(true)
        }}
        rows={4}
        className="w-full resize-y rounded-lg border border-input bg-background px-2.5 py-2 text-xs leading-relaxed text-foreground outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-primary/50 focus:ring-1 focus:ring-primary/30"
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground/60">设计思路 · 修改后保存，再点「生成/重新生成」按新文字生图</span>
        <Button
          size="sm"
          variant="outline"
          loading={busy}
          disabled={!dirty}
          onClick={async () => {
            setBusy(true)
            setError('')
            try {
              await onSave(draft)
              setDirty(false)
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e))
            } finally {
              setBusy(false)
            }
          }}
        >
          保存文字
        </Button>
      </div>
      {error && <p className="text-[11px] text-destructive">{error}</p>}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// 单张资产卡片（文字 + 图片 + 操作）
// ─────────────────────────────────────────────────────────────

function DesignAssetCard({
  productId, item, generating, error, onGenerate, onUpdateText, onDelete, onPreview, onVersions,
}: {
  productId: string
  item: DesignStudioItem
  generating: boolean
  error: string
  onGenerate: () => void
  onUpdateText: (text: string) => Promise<void>
  onDelete: () => Promise<void>
  onPreview: () => void
  onVersions: () => void
}) {
  const [text, setText] = useState(item.text)
  useEffect(() => setText(item.text), [item.text, item.id])

  const kind = KIND_META[item.kind]
  return (
    <div className="group flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md">
      {/* 图片区 */}
      <div
        className="relative aspect-video cursor-zoom-in overflow-hidden border-b bg-secondary/20"
        onClick={onPreview}
      >
        {item.image ? (
          <>
            <img src={item.image.url} alt={item.name} loading="lazy" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" />
            <span className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-black/40 text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100">
              <ZoomIn className="h-3.5 w-3.5" />
            </span>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 text-muted-foreground/50">
            <Wand2 className="h-6 w-6" />
            <span className="text-[11px]">尚未生图 · 填写文字后生成</span>
          </div>
        )}
        <span className={cn('absolute left-2 top-2 rounded-full px-2 py-0.5 text-[10px] font-medium backdrop-blur', kind.cls)}>
          {kind.label}
        </span>
      </div>

      {/* 文字区 */}
      <div className="flex min-w-0 flex-1 flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium" title={item.name}>{item.name}</span>
          {item.source === 'pipeline' && (
            <span className="shrink-0 rounded-full bg-secondary px-1.5 py-0.5 text-[9px] text-muted-foreground">流水线</span>
          )}
        </div>
        <TextEditor
          value={text}
          onSave={async (newText) => {
            setText(newText)
            await onUpdateText(newText)
          }}
        />
        {item.api_text && (
          <p className="rounded-md bg-amber-500/5 px-2 py-1 text-[10px] leading-relaxed text-amber-700">
            <span className="font-medium">模型文本输出：</span>{item.api_text}
          </p>
        )}
        {error && <p className="rounded-md bg-destructive/5 px-2 py-1 text-[11px] leading-relaxed text-destructive">{error}</p>}

        {/* 操作区 */}
        <div className="mt-auto flex flex-wrap items-center gap-1.5 border-t pt-2.5">
          <Button size="sm" loading={generating} onClick={onGenerate}>
            <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', generating && 'animate-spin')} />
            {item.image ? '重新生成' : '生成图片'}
          </Button>
          {item.image && (
            <>
              <a href={item.image.url} download className="inline-flex h-8 items-center rounded-md border px-2.5 text-xs hover:bg-accent">
                <Download className="mr-1.5 h-3.5 w-3.5" /> 下载
              </a>
              <Button size="sm" variant="ghost" title="版本历史" disabled={!item.versions?.length} onClick={onVersions}>
                <History className="mr-1 h-3.5 w-3.5" />{item.versions?.length || 0}
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" className="ml-auto text-muted-foreground hover:text-destructive" title="删除条目" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// 组合设计区（组合总图 + 组件行）
// ─────────────────────────────────────────────────────────────

function CompositeSection({
  productId, library, composite, busyIds, errors, onGenerate, onUpdateText, onDelete, onPreview, onVersions, onAddComponent,
}: {
  productId: string
  library: DesignStudioLibrary
  composite: DesignStudioItem
  busyIds: Set<string>
  errors: Record<string, string>
  onGenerate: (id: string) => void
  onUpdateText: (id: string, text: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onPreview: (url: string, title: string) => void
  onVersions: (item: DesignStudioItem) => void
  onAddComponent: (compositeId: string) => void
}) {
  const components = (composite.children ?? [])
    .map((cid) => library.items.find((it) => it.id === cid))
    .filter((it): it is DesignStudioItem => Boolean(it))

  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Layers className="h-4 w-4 text-indigo-600" />
        <h3 className="text-sm font-semibold">组合设计</h3>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
          {components.length} 个组件 · 1 张组合总图
        </span>
      </div>

      {/* 组合总图（大卡） */}
      <div className="mb-5 overflow-hidden rounded-xl border bg-background">
        <div className="grid gap-0 md:grid-cols-[minmax(0,380px)_1fr]">
          <div
            className="relative aspect-video cursor-zoom-in overflow-hidden bg-secondary/20"
            onClick={() => composite.image && onPreview(composite.image.url, composite.name)}
          >
            {composite.image ? (
              <img src={composite.image.url} alt={composite.name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-1.5 text-muted-foreground/50">
                <Wand2 className="h-7 w-7" />
                <span className="text-xs">组合总图未生成</span>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2.5 p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">{composite.name}</span>
              <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', KIND_META.composite.cls)}>组合总图</span>
            </div>
            <TextEditor
              value={composite.text}
              onSave={(text) => onUpdateText(composite.id, text)}
              placeholder="整体设计思路（重新生成组合图时会结合全部组件文字）…"
            />
            {errors[composite.id] && (
              <p className="rounded-md bg-destructive/5 px-2 py-1 text-[11px] text-destructive">{errors[composite.id]}</p>
            )}
            <div className="mt-auto flex flex-wrap items-center gap-2 border-t pt-3">
              <Button loading={busyIds.has(composite.id)} onClick={() => onGenerate(composite.id)}>
                <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', busyIds.has(composite.id) && 'animate-spin')} />
                {composite.image ? '重新生成组合图' : '生成组合图'}
              </Button>
              {composite.image && (
                <>
                  <a href={composite.image.url} download className="inline-flex h-9 items-center rounded-md border px-3 text-xs hover:bg-accent">
                    <Download className="mr-1.5 h-3.5 w-3.5" /> 下载
                  </a>
                  <Button size="sm" variant="ghost" disabled={!composite.versions?.length} onClick={() => onVersions(composite)}>
                    <History className="mr-1 h-3.5 w-3.5" />{composite.versions?.length || 0}
                  </Button>
                </>
              )}
              <Button size="sm" variant="ghost" className="ml-auto text-muted-foreground hover:text-destructive" onClick={() => onDelete(composite.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* 组件卡 */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {components.map((comp) => (
          <DesignAssetCard
            key={comp.id}
            productId={productId}
            item={comp}
            generating={busyIds.has(comp.id)}
            error={errors[comp.id] ?? ''}
            onGenerate={() => onGenerate(comp.id)}
            onUpdateText={(text) => onUpdateText(comp.id, text)}
            onDelete={() => onDelete(comp.id)}
            onPreview={() => comp.image && onPreview(comp.image.url, comp.name)}
            onVersions={() => onVersions(comp)}
          />
        ))}
        <button
          type="button"
          onClick={() => onAddComponent(composite.id)}
          className="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-primary"
        >
          <Plus className="h-5 w-5" />
          <span className="text-xs">添加组件（如：桌面 / 桌腿）</span>
        </button>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────
// 组件拆解 / 手动创建对话框（共用「组合设计」创建表单）
// ─────────────────────────────────────────────────────────────

function ComponentRowEditor({
  value, onChange, onRemove, removable,
}: {
  value: { name: string; text: string }
  onChange: (v: { name: string; text: string }) => void
  onRemove?: () => void
  removable?: boolean
}) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <input
          value={value.name}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          placeholder="组件名称（如：桌面）"
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm outline-none focus:border-primary/50"
        />
        {removable && (
          <button type="button" onClick={onRemove} className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <textarea
        value={value.text}
        onChange={(e) => onChange({ ...value, text: e.target.value })}
        placeholder="该组件的设计思路（材质 / 造型 / 颜色…）"
        rows={2}
        className="mt-2 w-full resize-y rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:border-primary/50"
      />
    </div>
  )
}

function CompositeCreateDialog({
  productId, initial, onCreated, onClose,
}: {
  productId: string
  initial?: ComponentSuggestion[]
  onCreated: (composite: DesignStudioItem) => void
  onClose: () => void
}) {
  const [name, setName] = useState('产品整体设计')
  const [overall, setOverall] = useState('')
  const [rows, setRows] = useState<{ name: string; text: string }[]>(
    initial?.length
      ? initial.map((s) => ({ name: s.name, text: s.text }))
      : [{ name: '', text: '' }],
  )
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const validRows = rows.filter((r) => r.name.trim())
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            {initial ? <Sparkles className="h-4 w-4 text-indigo-600" /> : <Wand2 className="h-4 w-4 text-indigo-600" />}
            {initial ? '智能拆解 · 创建组合设计' : '新建组合设计'}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            先按组件分别生图，再生成组合总图；组件 / 整体文字可随时修改并分别重新生图。
          </p>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="组合名称"
              className="h-9 w-full rounded-md border border-input bg-background px-2.5 text-sm outline-none focus:border-primary/50"
            />
            <input
              value={overall}
              onChange={(e) => setOverall(e.target.value)}
              placeholder="整体设计思路（可选）"
              className="h-9 w-full rounded-md border border-input bg-background px-2.5 text-sm outline-none focus:border-primary/50"
            />
          </div>
          <div className="max-h-[38vh] space-y-2 overflow-y-auto pr-1">
            {rows.map((r, i) => (
              <ComponentRowEditor
                key={i}
                value={r}
                removable={rows.length > 1}
                onRemove={() => setRows(rows.filter((_, idx) => idx !== i))}
                onChange={(v) => setRows(rows.map((row, idx) => (idx === i ? v : row)))}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => setRows([...rows, { name: '', text: '' }])}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed py-2 text-xs text-muted-foreground hover:border-primary/40 hover:text-primary"
          >
            <Plus className="h-3.5 w-3.5" /> 添加组件
          </button>
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button
            loading={creating}
            disabled={!name.trim() || validRows.length === 0}
            onClick={async () => {
              setCreating(true)
              setError('')
              try {
                const res = await designStudioApi.createComposite(productId, {
                  name: name.trim(),
                  text: overall.trim(),
                  components: validRows,
                })
                onCreated(res.composite)
                onClose()
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e))
              } finally {
                setCreating(false)
              }
            }}
          >
            <Sparkles className="mr-1.5 h-3.5 w-3.5" /> 创建组合设计
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─────────────────────────────────────────────────────────────
// 主组件
// ─────────────────────────────────────────────────────────────

export function DesignStudioLibrary({ product }: { product: StudioProduct }) {
  const productId = product.product_id
  const [library, setLibrary] = useState<DesignStudioLibrary | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set())
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ url: string; title: string } | null>(null)
  const [versionsFor, setVersionsFor] = useState<DesignStudioItem | null>(null)
  const [showSuggest, setShowSuggest] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [suggestions, setSuggestions] = useState<ComponentSuggestion[]>([])
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      setLibrary(await designStudioApi.get(productId))
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    load()
  }, [load])

  const flash = (msg: string) => {
    setNotice(msg)
    window.setTimeout(() => setNotice(''), 2600)
  }

  /** 局部更新条目（生成/保存/恢复后） */
  const patchItem = (item: DesignStudioItem) => {
    setLibrary((prev) => prev ? { ...prev, items: prev.items.map((it) => (it.id === item.id ? item : it)) } : prev)
  }

  const composites = useMemo(() => (library?.items ?? []).filter((it) => it.kind === 'composite'), [library])
  const standalone = useMemo(
    () => (library?.items ?? []).filter((it) => it.kind !== 'composite' && !it.parent),
    [library],
  )
  const imageCount = (library?.items ?? []).filter((it) => it.image).length

  const handleGenerate = async (itemId: string) => {
    setBusyIds((prev) => new Set(prev).add(itemId))
    setErrors((prev) => ({ ...prev, [itemId]: '' }))
    try {
      const res = await designStudioApi.generate(productId, itemId)
      patchItem(res.item)
      flash('图片生成完成 ✓')
    } catch (e) {
      setErrors((prev) => ({ ...prev, [itemId]: e instanceof Error ? e.message : String(e) }))
    } finally {
      setBusyIds((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
    }
  }

  const handleUpdateText = async (itemId: string, text: string) => {
    const res = await designStudioApi.updateItem(productId, itemId, { text })
    patchItem(res.item)
    flash('设计思路已保存')
  }

  const handleDelete = async (itemId: string) => {
    if (!window.confirm('确定删除该资产条目？（图片文件保留，仅从资产库移除）')) return
    await designStudioApi.deleteItem(productId, itemId)
    setLibrary((prev) => prev ? { ...prev, items: prev.items.filter((it) => it.id !== itemId) } : prev)
    flash('已删除')
  }

  const handleRestore = async (itemId: string, index: number) => {
    const res = await designStudioApi.restore(productId, itemId, index)
    patchItem(res.item)
    flash('已恢复该版本')
  }

  const openSuggest = async () => {
    setShowSuggest(true)
    setSuggestLoading(true)
    setSuggestions([])
    try {
      const res = await designStudioApi.suggestComponents(productId)
      setSuggestions(res.suggestions)
    } catch (e) {
      setErrors((prev) => ({ ...prev, __suggest: e instanceof Error ? e.message : String(e) }))
    } finally {
      setSuggestLoading(false)
    }
  }

  const handleZip = async () => {
    setZipBusy(true)
    try {
      const blob = await designStudioApi.downloadZip(productId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `design_studio_${product.idea.slice(0, 20) || productId.slice(0, 8)}.zip`
      a.click()
      URL.revokeObjectURL(url)
      flash('已打包下载全部图片 ✓')
    } catch (e) {
      flash(e instanceof Error ? e.message : '打包下载失败')
    } finally {
      setZipBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 加载资产库…
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* ── 头部：任务信息 + 全局操作 ── */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border bg-card p-4 shadow-sm">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold" title={product.idea}>{product.idea || '（未命名任务）'}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span>共 {library?.items.length ?? 0} 条资产</span>
            <span>{imageCount} 张图片</span>
            <span>{composites.length} 个组合设计</span>
            <span className="text-muted-foreground/60">文字可改 · 改后重新生图</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={openSuggest}>
            <Sparkles className="mr-1.5 h-3.5 w-3.5 text-indigo-600" /> 智能拆解组件
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowManual(true)}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> 新建组合设计
          </Button>
          <Button size="sm" loading={zipBusy} disabled={imageCount === 0} onClick={handleZip}>
            <Download className="mr-1.5 h-3.5 w-3.5" /> 下载全部（ZIP）
          </Button>
        </div>
      </div>

      {notice && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-700">{notice}</div>
      )}
      {loadError && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">{loadError}</div>
      )}
      {errors.__suggest && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">{errors.__suggest}</div>
      )}

      {/* ── 组合设计 ── */}
      {composites.map((composite) => (
        <CompositeSection
          key={composite.id}
          productId={productId}
          library={library!}
          composite={composite}
          busyIds={busyIds}
          errors={errors}
          onGenerate={handleGenerate}
          onUpdateText={handleUpdateText}
          onDelete={handleDelete}
          onPreview={(url, title) => setPreview({ url, title })}
          onVersions={setVersionsFor}
          onAddComponent={async (compositeId) => {
            const name = window.prompt('组件名称（如：桌面）')
            if (!name?.trim()) return
            const res = await designStudioApi.createItem(productId, { kind: 'component', name: name.trim(), parent: compositeId })
            setLibrary((prev) => prev ? { ...prev, items: [...prev.items, res.item] } : prev)
          }}
        />
      ))}

      {/* ── 图片资产库（独立条目） ── */}
      {(standalone.length > 0 || composites.length === 0) && (
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Boxes className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">图片资产库</h3>
            <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">{standalone.length} 条</span>
            {standalone.length > 0 && (
              <span className="ml-auto flex items-center gap-2 text-[10px] text-muted-foreground/60">
                <button type="button" onClick={load} className="hover:text-foreground">刷新</button>
                <button type="button" onClick={() => setShowManual(true)} className="flex items-center gap-0.5 hover:text-foreground">
                  <Plus className="h-3 w-3" /> 新建
                </button>
              </span>
            )}
          </div>

          {standalone.length === 0 && composites.length === 0 ? (
            <div className="flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed bg-background/50 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary">
                <Wand2 className="h-5 w-5 text-muted-foreground" />
              </div>
              <h4 className="mt-4 text-sm font-medium">该任务还没有设计资产</h4>
              <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-muted-foreground">
                流水线生成的全部图片（含设计思路）会自动归档到这里；
                也可「智能拆解组件」或手动创建组合设计，按组件分别生图后生成组合总图。
              </p>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline" onClick={openSuggest}>
                  <Sparkles className="mr-1.5 h-3.5 w-3.5 text-indigo-600" /> 智能拆解组件
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowManual(true)}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" /> 手动创建
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {standalone.map((item) => (
                <DesignAssetCard
                  key={item.id}
                  productId={productId}
                  item={item}
                  generating={busyIds.has(item.id)}
                  error={errors[item.id] ?? ''}
                  onGenerate={() => handleGenerate(item.id)}
                  onUpdateText={(text) => handleUpdateText(item.id, text)}
                  onDelete={() => handleDelete(item.id)}
                  onPreview={() => item.image && setPreview({ url: item.image.url, title: item.name })}
                  onVersions={() => setVersionsFor(item)}
                />
              ))}
              {standalone.length > 0 && (
                <div className="flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed text-muted-foreground/70">
                  <button type="button" onClick={() => setShowManual(true)} className="flex flex-col items-center gap-1.5 transition-colors hover:text-primary">
                    <Plus className="h-5 w-5" />
                    <span className="text-xs">新增资产条目</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── 弹层 ── */}
      {preview && <PreviewModal url={preview.url} title={preview.title} onClose={() => setPreview(null)} />}
      {versionsFor && (
        <VersionDialog
          item={versionsFor}
          productId={productId}
          onRestore={(index) => handleRestore(versionsFor.id, index)}
          onClose={() => setVersionsFor(null)}
        />
      )}
      {showSuggest && (
        <CompositeCreateDialog
          productId={productId}
          initial={suggestions}
          onCreated={(composite) => {
            setLibrary((prev) => prev ? { ...prev, items: [...prev.items, composite] } : prev)
            flash('组合设计已创建，可逐个生成组件图片')
          }}
          onClose={() => setShowSuggest(false)}
        />
      )}
      {showManual && (
        <CompositeCreateDialog
          productId={productId}
          onCreated={(composite) => {
            setLibrary((prev) => prev ? { ...prev, items: [...prev.items, composite] } : prev)
            flash('组合设计已创建')
          }}
          onClose={() => setShowManual(false)}
        />
      )}
    </div>
  )
}
