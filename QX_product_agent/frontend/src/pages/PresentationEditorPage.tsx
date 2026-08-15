/**
 * PresentationEditorPage —— HTML 演示编辑器（GrapesJS）
 *
 * 编辑对象 = Presentation DSL（canonical）：编辑 → 保存回写 DSL →
 * 导出走现有管线（HTML/PDF/PPTX 一致）。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { Editor } from 'grapesjs'
import {
  ArrowLeft, Check, Loader2, Save,
} from 'lucide-react'
import { initGrapes } from '@/components/editor/studio/initGrapes'
import { componentToHtml, grapesToDsl, grapesToPage, pageToHtml } from '@/components/editor/studio/dslBridge'
import { ExportMenu } from '@/components/presentation/ExportMenu'
import { ImageSearch } from '@/components/ImageSearch'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import type { PresentationDSL, PresentationPage } from '@/types/presentation'
import { cn } from '@/lib/utils'

export function PresentationEditorPage() {
  const { productId } = useParams<{ productId: string }>()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<Editor | null>(null)
  const pagesRef = useRef<PresentationPage[]>([])
  const [product, setProduct] = useState<StudioProduct | null>(null)
  const [pageIndex, setPageIndex] = useState(0)
  const [projectId, setProjectId] = useState('')
  const [tab, setTab] = useState<'assets' | 'styles'>('assets')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const pages = product?.presentation && Array.isArray((product.presentation as PresentationDSL).pages)
    ? (product.presentation as PresentationDSL).pages
    : []

  const dsl = product?.presentation as PresentationDSL | null

  // ─── 加载产品 + 初始化编辑器 ─────────────────────────────
  useEffect(() => {
    if (!productId || !containerRef.current) return
    let cancelled = false
    const load = async () => {
      try {
        const p = await productApi.get(productId)
        if (cancelled) return
        setProduct(p)
        const pres = p.presentation
        if (pres && Array.isArray((pres as PresentationDSL).pages) && (pres as PresentationDSL).pages.length > 0) {
          pagesRef.current = (pres as PresentationDSL).pages
          const editor = initGrapes(containerRef.current!, pagesRef.current[0])
          editorRef.current = editor
          // 素材拖入画布（右侧素材库 → iframe）；画布文档异步就绪，轮询挂载
          const attachDrop = (attempts = 0) => {
            const canvasDoc = editor.Canvas.getDocument()
            if (!canvasDoc) {
              if (attempts < 25) setTimeout(() => attachDrop(attempts + 1), 200)
              return
            }
            canvasDoc.addEventListener('dragover', (e) => e.preventDefault())
            canvasDoc.addEventListener('drop', (e) => {
              e.preventDefault()
              const url = e.dataTransfer?.getData('text/plain') ?? ''
              if (url) insertImage(url)
            })
          }
          attachDrop()
        } else {
          setError('该产品无新版演示资产，请先运行流水线生成')
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '加载失败')
      }
    }
    load()
    return () => {
      cancelled = true
      editorRef.current?.destroy()
      editorRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId])

  const insertImage = useCallback((url: string) => {
    const editor = editorRef.current
    if (!editor) return
    const selected = editor.getSelected()
    const attrs = ((selected?.get('attributes') as Record<string, unknown>) ?? {}) as Record<string, string>
    if (selected && attrs['data-dsl-type'] === 'image') {
      // addAttributes 为合并语义，不会清掉 data-dsl-* 元数据
      selected.addAttributes({ 'data-src': url })
    } else {
      editor.addComponents(
        componentToHtml({
          id: `img-${Date.now()}`,
          type: 'image',
          data: { src: url, alt: '素材图片' },
          emphasis: 'normal',
        }),
      )
    }
  }, [])

  // ─── 切页（先收集当前页到 ref） ─────────────────────────
  const switchPage = useCallback(
    (next: number) => {
      const editor = editorRef.current
      if (!editor || !pagesRef.current.length) return
      // 当前页 → 收集回 ref
      const current = pagesRef.current[pageIndex]
      if (current) {
        pagesRef.current[pageIndex] = grapesToPage(editor, current.id, current)
      }
      const clamped = ((next % pagesRef.current.length) + pagesRef.current.length) % pagesRef.current.length
      setPageIndex(clamped)
      setSaved(false)
    },
    [pageIndex],
  )

  useEffect(() => {
    const editor = editorRef.current
    if (!editor || !pagesRef.current.length) return
    const page = pagesRef.current[pageIndex]
    editor.setComponents(pageToHtml(page))
  }, [pageIndex])

  const handleSave = async () => {
    if (!productId || !product || !dsl || saving) return
    setSaving(true)
    setError('')
    try {
      const editor = editorRef.current
      let updated = dsl
      if (editor) {
        // 以 pagesRef 为基准（含切页时收集的其他页编辑），仅当前页从画布重新收集
        updated = grapesToDsl(editor, { ...dsl, pages: pagesRef.current }, pageIndex)
      }
      await productApi.updatePresentation(productId, updated)
      setSaved(true)
      setProduct({ ...product, presentation: updated })
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (error && !product) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-destructive">
        {error}
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* ─── 顶栏 ─────────────────────────────────────────── */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-5">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/presentation')}
            className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> 返回
          </button>
          <span className="text-sm font-medium">{product?.idea ?? '加载中…'}</span>
          <span className="rounded-full bg-secondary px-2.5 py-0.5 text-[11px] text-muted-foreground">
            编辑第 {pageIndex + 1} / {pages.length} 页
          </span>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <Check className="h-3.5 w-3.5" /> 已保存
            </span>
          )}
          {error && <span className="text-xs text-destructive">{error}</span>}
          {productId && (
            <ExportMenu
              productId={productId}
              onError={setError}
              className="rounded-lg px-3.5 py-2"
            />
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-[#24415E] px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            保存
          </button>
        </div>
      </header>

      {/* ─── 主体：画布 + 右侧栏 ──────────────────────────── */}
      <div className="flex min-h-0 flex-1">
        {/* 画布 */}
        <div className="min-w-0 flex-1 overflow-auto bg-slate-100">
          <div ref={containerRef} className="h-full min-h-[720px] w-full" />
        </div>

        {/* 右侧栏 */}
        <aside className="flex w-80 shrink-0 flex-col border-l bg-card">
          {/* 页导航 */}
          <div className="border-b px-4 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              页面
            </div>
            <div className="flex flex-wrap gap-1.5">
              {pages.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => switchPage(i)}
                  className={cn(
                    'rounded-md px-2.5 py-1.5 text-[11px] transition-colors',
                    i === pageIndex
                      ? 'bg-[#24415E] text-white'
                      : 'bg-secondary text-muted-foreground hover:text-foreground',
                  )}
                >
                  {i + 1}. {p.title.slice(0, 8)}
                </button>
              ))}
            </div>
          </div>

          {/* 属性面板（常驻，选中组件时出现） */}
          <div className="editor-traits border-b px-4 py-2 empty:hidden" />

          {/* Tab 切换：素材 / 样式图层 */}
          <div className="flex border-b text-xs">
            {(['assets', 'styles'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={cn(
                  'flex-1 py-2.5 font-medium transition-colors',
                  tab === t ? 'border-b-2 border-[#24415E] text-foreground' : 'text-muted-foreground',
                )}
              >
                {t === 'assets' ? '素材库' : '样式与图层'}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
            {/* 两个 Tab 的容器都常驻挂载（GrapesJS 面板在 init 时 appendTo，必须存在），用 hidden 切换 */}
            <div className={cn('space-y-4', tab !== 'assets' && 'hidden')}>
              {/* 图片搜索（点击/拖拽插入） */}
              <ImageSearch projectId={projectId} selectable={{ onInsert: insertImage, productId }} />
            </div>
            <div className={cn('space-y-4', tab !== 'styles' && 'hidden')}>
              <div>
                <div className="mb-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  组件属性 / 样式
                </div>
                <div className="editor-styles" />
              </div>
              <div>
                <div className="mb-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  图层
                </div>
                <div className="editor-layers" />
              </div>
              <div>
                <div className="mb-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  基础元素
                </div>
                <div className="editor-blocks" />
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
