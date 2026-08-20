import { useState } from 'react'
import { ChevronDown, Palette, Wand2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PptOptions } from '@/lib/api'

export interface DesignStyleValue {
  themeId: string | null
  styleId: string | null
}

/**
 * 设计风格选择器（模板决定权前端化）：
 * - 设计主题 9 套（预览图 + 色板；空 = AI 自主决策）
 * - 风格方法论 13 套（ppt-master styles，影响演示叙事结构）
 */
export function DesignStylePicker({
  options,
  value,
  onChange,
}: {
  options: PptOptions | null
  value: DesignStyleValue
  onChange: (v: DesignStyleValue) => void
}) {
  const [open, setOpen] = useState(false)

  const selectedTheme = options?.themes.find((t) => t.id === value.themeId)
  const label = selectedTheme
    ? `主题：${selectedTheme.name}`
    : '设计风格：AI 自动匹配'

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-[13px] font-medium text-foreground">
          <Palette className="h-4 w-4 text-primary" />
          {label}
          {value.styleId && (
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground">
              风格 {value.styleId}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div className="space-y-5 border-t border-border px-4 py-4">
          {/* 设计主题：预览卡片网格 */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[12px] font-medium text-muted-foreground">
                设计主题（决定 PPT 配色与视觉风格）
              </span>
              <button
                type="button"
                onClick={() => onChange({ ...value, themeId: null })}
                className={cn(
                  'flex items-center gap-1 rounded px-2 py-1 text-[11.5px] transition-colors',
                  value.themeId === null
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-secondary',
                )}
              >
                <Wand2 className="h-3 w-3" />
                AI 自动匹配
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {(options?.themes ?? []).map((t) => {
                const active = value.themeId === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() =>
                      onChange({ ...value, themeId: active ? null : t.id })
                    }
                    className={cn(
                      'group overflow-hidden rounded-lg border text-left transition-all',
                      active
                        ? 'border-primary ring-2 ring-primary/30'
                        : 'border-border hover:border-primary/50',
                    )}
                  >
                    <div className="relative aspect-video bg-muted">
                      <img
                        src={t.preview}
                        alt={t.name}
                        loading="lazy"
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          ;(e.target as HTMLImageElement).style.display = 'none'
                        }}
                      />
                    </div>
                    <div className="space-y-1.5 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[12.5px] font-medium text-foreground">
                          {t.name}
                        </span>
                        <span className="flex shrink-0 -space-x-1">
                          {(['primary', 'accent', 'bg'] as const).map((k) => (
                            <span
                              key={k}
                              className="h-3 w-3 rounded-full border border-white/70"
                              style={{ background: t.palette?.[k] }}
                            />
                          ))}
                        </span>
                      </div>
                      <p className="line-clamp-1 text-[11px] text-muted-foreground">
                        {t.summary}
                      </p>
                    </div>
                  </button>
                )
              })}
              {!options && (
                <div className="col-span-3 py-6 text-center text-[12px] text-muted-foreground">
                  主题选项加载中…
                </div>
              )}
            </div>
          </div>

          {/* 风格方法论：下拉 */}
          <div>
            <span className="mb-2 block text-[12px] font-medium text-muted-foreground">
              风格方法论（决定演示叙事结构，可选）
            </span>
            <select
              value={value.styleId ?? ''}
              onChange={(e) =>
                onChange({ ...value, styleId: e.target.value || null })
              }
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-[13px] text-foreground outline-none focus:border-primary"
            >
              <option value="">不指定（AI 按内容选择）</option>
              {(options?.styles ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} — {s.summary}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
