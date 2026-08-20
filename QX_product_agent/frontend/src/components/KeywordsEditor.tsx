/**
 * KeywordsEditor —— 关键词编辑弹窗
 *
 * 后端：PUT /api/v1/product/{product_id}/keywords
 * Body: { keywords: Record<group, string[]> }
 * Groups（固定）：design / function / appearance / audience / scenario
 */

import { useEffect, useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { Button } from '@/components/common/button'
import { Input } from '@/components/common/input'
import { cn } from '@/lib/utils'

export const KEYWORD_GROUPS = [
  { key: 'design', label: '设计', hint: '视觉 / 风格 / 材质' },
  { key: 'function', label: '功能', hint: '核心能力 / 卖点' },
  { key: 'appearance', label: '外观', hint: '形态 / 颜色 / 质感' },
  { key: 'audience', label: '人群', hint: '目标用户画像' },
  { key: 'scenario', label: '场景', hint: '使用情境' },
] as const

export type KeywordGroupKey = (typeof KEYWORD_GROUPS)[number]['key']

const COLOR_MAP: Record<string, string> = {
  design: 'border-primary/40 bg-primary/10 text-primary',
  function: 'border-accent/40 bg-accent/10 text-accent',
  appearance: 'border-warning/40 bg-warning/10 text-warning',
  audience: 'border-success/40 bg-success/10 text-success',
  scenario: 'border-muted-foreground/30 bg-muted text-muted-foreground',
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
  // 初始值：当前产品已有 keywords 优先，否则空数组
  const initial: Record<KeywordGroupKey, string[]> = KEYWORD_GROUPS.reduce(
    (acc, g) => {
      const list = (product.keywords?.[g.key] as string[] | undefined) ?? []
      acc[g.key] = [...list]
      return acc
    },
    {} as Record<KeywordGroupKey, string[]>,
  )

  const [draft, setDraft] = useState<Record<KeywordGroupKey, string[]>>(initial)
  const [inputs, setInputs] = useState<Record<KeywordGroupKey, string>>(
    KEYWORD_GROUPS.reduce(
      (acc, g) => ({ ...acc, [g.key]: '' }),
      {} as Record<KeywordGroupKey, string>,
    ),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const addKeyword = (group: KeywordGroupKey) => {
    const v = inputs[group].trim()
    if (!v) return
    setDraft((prev) => ({
      ...prev,
      [group]: [...prev[group], v],
    }))
    setInputs((prev) => ({ ...prev, [group]: '' }))
  }

  const removeKeyword = (group: KeywordGroupKey, idx: number) => {
    setDraft((prev) => ({
      ...prev,
      [group]: prev[group].filter((_, i) => i !== idx),
    }))
  }

  const handleSave = async () => {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      // 过滤空字符串
      const cleaned: Record<string, string[]> = {}
      for (const k of Object.keys(draft)) {
        cleaned[k] = draft[k as KeywordGroupKey].filter((s) => s.trim().length > 0)
      }
      await productApi.updateKeywords(product.product_id, cleaned)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ESC 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-border bg-card shadow-elev-xl">
        {/* 顶部条 */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card/95 px-6 py-4 backdrop-blur">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              关键词编辑
            </div>
            <h3 className="mt-0.5 font-display text-lg font-semibold text-foreground">
              {product.idea}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="space-y-5 px-6 py-5">
          {error && (
            <div className="border border-destructive/40 bg-destructive/10 px-4 py-2.5 font-mono text-[12px] text-destructive">
              <span className="font-semibold">[ERROR]</span> {error}
            </div>
          )}

          {KEYWORD_GROUPS.map((g) => (
            <div
              key={g.key}
              className="rounded-lg border border-border bg-background/40 p-4"
            >
              <div className="mb-3 flex items-baseline justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'rounded-sm border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em]',
                        COLOR_MAP[g.key],
                      )}
                    >
                      {g.key}
                    </span>
                    <span className="font-display text-sm font-semibold text-foreground">
                      {g.label}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{g.hint}</p>
                </div>
                <span className="font-mono text-[10px] uppercase text-muted-foreground">
                  {draft[g.key].length} 个
                </span>
              </div>

              {/* 关键词列表 */}
              <div className="mb-3 flex flex-wrap gap-1.5">
                {draft[g.key].length === 0 ? (
                  <span className="text-xs text-muted-foreground/60">暂无关键词</span>
                ) : (
                  draft[g.key].map((word, i) => (
                    <span
                      key={`${g.key}-${i}-${word}`}
                      className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-2.5 py-1 font-mono text-[12px] text-white"
                    >
                      {word}
                      <button
                        type="button"
                        onClick={() => removeKeyword(g.key, i)}
                        className="hover:opacity-70"
                        aria-label={`移除 ${word}`}
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  ))
                )}
              </div>

              {/* 添加输入 */}
              <div className="flex items-center gap-2">
                <Input
                  type="text"
                  value={inputs[g.key]}
                  onChange={(e) =>
                    setInputs((prev) => ({ ...prev, [g.key]: e.target.value }))
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addKeyword(g.key)
                    }
                  }}
                  placeholder={`添加${g.label}关键词…`}
                  className="h-9 flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => addKeyword(g.key)}
                  disabled={!inputs[g.key].trim()}
                >
                  添加
                </Button>
              </div>
            </div>
          ))}
        </div>

        {/* 底部操作 */}
        <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-border bg-card/95 px-6 py-4 backdrop-blur">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {saving ? '保存中…' : '保存到资产'}
          </Button>
        </div>
      </div>
    </div>
  )
}