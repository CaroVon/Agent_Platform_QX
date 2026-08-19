/**
 * KeywordsEditor —— 产品关键词组编辑弹窗
 *
 * 五个固定分组（设计/功能/外观/人群/场景）：
 *   - 每个分组展示关键词 chips，可单个删除
 *   - 输入框回车 / 点击添加新关键词
 *   - 保存整体替换（PUT /product/{id}/keywords，同步写入资产包）
 */

import { useEffect, useMemo, useState } from 'react'
import { Loader2, Plus, Tags, X } from 'lucide-react'
import { productApi } from '@/lib/api'
import { KEYWORD_GROUP_LABELS, type StudioKeywords, type StudioProduct } from '@/types/studio'

const GROUP_COLORS: Record<string, string> = {
  design: 'bg-sky-500/10 text-sky-700 border-sky-500/20',
  function: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
  appearance: 'bg-violet-500/10 text-violet-700 border-violet-500/20',
  audience: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
  scenario: 'bg-rose-500/10 text-rose-700 border-rose-500/20',
}

export function KeywordsEditor({
  product,
  onClose,
  onSaved,
}: {
  product: StudioProduct
  onClose: () => void
  onSaved: () => void
}) {
  const [groups, setGroups] = useState<StudioKeywords>(() => {
    const base: StudioKeywords = {}
    for (const key of Object.keys(KEYWORD_GROUP_LABELS)) base[key] = []
    const existing = product.keywords ?? {}
    for (const [key, words] of Object.entries(existing)) {
      if (Array.isArray(words)) base[key] = [...words]
    }
    return base
  })
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const totalCount = useMemo(
    () => Object.values(groups).reduce((sum, words) => sum + words.length, 0),
    [groups],
  )

  const addKeyword = (groupKey: string) => {
    const word = (draft[groupKey] ?? '').trim()
    if (!word) return
    setGroups((prev) => ({
      ...prev,
      [groupKey]: prev[groupKey]?.includes(word) ? prev[groupKey] : [...(prev[groupKey] ?? []), word],
    }))
    setDraft((prev) => ({ ...prev, [groupKey]: '' }))
  }

  const removeKeyword = (groupKey: string, word: string) => {
    setGroups((prev) => ({
      ...prev,
      [groupKey]: (prev[groupKey] ?? []).filter((w) => w !== word),
    }))
  }

  const handleSave = async () => {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      await productApi.updateKeywords(product.product_id, groups)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="flex max-h-[82vh] w-full max-w-lg flex-col rounded-2xl border bg-card shadow-xl animate-step-in">
        {/* ─── 头部 ─────────────────────────────────────── */}
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-4">
          <div className="flex items-center gap-2">
            <Tags className="h-4 w-4 text-[#24415E]" />
            <div>
              <div className="text-sm font-semibold">Key Words · 关键词组</div>
              <div className="mt-0.5 max-w-[320px] truncate text-[11px] text-muted-foreground">
                {product.idea}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* ─── 分组编辑区 ───────────────────────────────── */}
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            关键词由 AI 在任务完成后自动总结，可在此自由增删改；保存后作为产品资产的一部分进入资产库。
          </p>
          {Object.entries(KEYWORD_GROUP_LABELS).map(([key, label]) => (
            <div key={key}>
              <div className="mb-1.5 text-[11px] font-medium text-foreground/80">
                {label}
                <span className="ml-1 text-[10px] text-muted-foreground/70">
                  {groups[key]?.length ?? 0} 个
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {(groups[key] ?? []).map((word) => (
                  <span
                    key={word}
                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] ${GROUP_COLORS[key] ?? 'bg-secondary text-muted-foreground border-border'}`}
                  >
                    {word}
                    <button
                      type="button"
                      title="删除该关键词"
                      onClick={() => removeKeyword(key, word)}
                      className="rounded-full p-0.5 opacity-60 transition-opacity hover:opacity-100"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                {groups[key]?.length === 0 && (
                  <span className="text-[11px] text-muted-foreground/50">暂无关键词</span>
                )}
              </div>
              <div className="mt-1.5 flex gap-1.5">
                <input
                  type="text"
                  value={draft[key] ?? ''}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') addKeyword(key)
                  }}
                  placeholder={`添加「${label}」关键词…`}
                  maxLength={30}
                  className="h-8 min-w-0 flex-1 rounded-lg border bg-background px-2.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <button
                  type="button"
                  onClick={() => addKeyword(key)}
                  disabled={!(draft[key] ?? '').trim()}
                  className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#24415E]/25 px-2.5 text-xs font-medium text-[#24415E] transition-colors hover:bg-[#24415E]/5 disabled:opacity-40"
                >
                  <Plus className="h-3.5 w-3.5" /> 添加
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* ─── 底部 ─────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-3 border-t border-border/60 px-5 py-3.5">
          <span className="text-[11px] text-muted-foreground">共 {totalCount} 个关键词</span>
          {error && <span className="min-w-0 flex-1 truncate text-right text-[11px] text-destructive">{error}</span>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#24415E] px-5 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {saving ? '保存中…' : '保存关键词'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
