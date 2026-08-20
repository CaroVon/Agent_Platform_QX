/**
 * SuggestionChips —— 对话框下方提示词建议
 *
 * 由 prompt-kit 的 PromptSuggestion 移植适配：
 *  - Normal 模式：圆角胶囊按钮（默认展示模板）
 *  - Highlight 模式：根据当前输入高亮匹配片段
 *  - 新增：静态模板数据（行业×人群×场景）+ 🎲 随机示例 + 动态建议插槽
 *
 * 源码参考：https://github.com/ibelick/prompt-kit（MIT）
 */

import { useMemo, useState } from 'react'
import { Dices, Lightbulb, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 静态提示模板：行业 × 人群 × 场景组合示例 */
export const PMPT_TMPLATS = [
  '面向独居老人的智能药盒（用药提醒 + 家人远程监护）',
  '面向 Z 世代的 AI 睡眠健康枕（睡眠监测 + 助眠白噪音）',
  '面向健身房的智能私教镜（动作纠正 + 训练计划）',
  '面向过敏人群的智能空气净化器（过敏原监测 + 联动净化）',
  '面向露营爱好者的便携式储能电源（户外用电 + 太阳能充电）',
  '面向中小企业的 AI 客服工作台（多平台接入 + 知识库问答）',
  '面向宠物医院的智能分诊系统（症状录入 + AI 初诊）',
  '面向新手父母的智能育儿助手（喂养记录 + 发育评估）',
]

/** 基于输入关键词的模板联想（本地规则，动态建议的即时兜底） */
const TMPLAT_KYWDS: Array<{ kws: string[]; idea: string }> = [
  { kws: ['老人', '老年', '长辈', '药'], idea: '面向独居老人的智能药盒（用药提醒 + 家人远程监护 + 社区联动）' },
  { kws: ['睡', '枕头', '床'], idea: '面向 Z 世代的 AI 睡眠健康枕（睡眠监测 + 助眠白噪音 + 智能闹钟）' },
  { kws: ['健身', '运动', '私教', '训练'], idea: '面向健身房的智能私教镜（动作纠正 + 训练计划 + 体态评估）' },
  { kws: ['空气', '净化', '过敏', '呼吸'], idea: '面向过敏人群的智能空气净化器（过敏原监测 + 联动净化）' },
  { kws: ['宠物', '猫', '狗', '兽医'], idea: '面向宠物医院的智能分诊系统（症状录入 + AI 初诊 + 病例归档）' },
  { kws: ['客户', '客服', '售后', '工单'], idea: '面向中小企业的 AI 客服工作台（多平台接入 + 知识库问答）' },
  { kws: ['露营', '户外', '电源', '充电'], idea: '面向露营爱好者的便携式储能电源（户外用电 + 太阳能充电）' },
  { kws: ['育儿', '婴儿', '宝宝', '父母'], idea: '面向新手父母的智能育儿助手（喂养记录 + 发育评估 + 医生咨询）' },
]

function matchTemplate(input: string): string[] {
  const t = input.trim().toLowerCase()
  if (!t) return []
  const hits = TMPLAT_KYWDS.filter(({ kws }) => kws.some((k) => t.includes(k)))
  return hits.map((h) => h.idea).slice(0, 2)
}

export function SuggestionChip({
  children,
  onClick,
  highlight,
  className,
  disabled,
  title,
}: {
  children: React.ReactNode
  onClick?: () => void
  /** 高亮模式：输入文本中匹配该片段的部分将被高亮 */
  highlight?: string
  className?: string
  disabled?: boolean
  title?: string
}) {
  const isHighlightMode = highlight !== undefined && highlight.trim() !== ''
  const content = typeof children === 'string' ? children : ''

  // Normal 模式：胶囊按钮
  if (!isHighlightMode) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        title={title}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-[hsl(var(--primary))]/40 hover:text-[hsl(var(--primary))] disabled:opacity-50',
          className,
        )}
      >
        {children}
      </button>
    )
  }

  // Highlight 模式：匹配片段高亮
  const trimmedHighlight = highlight.trim()
  const contentLower = content.toLowerCase()
  const highlightLower = trimmedHighlight.toLowerCase()
  const shouldHighlight = contentLower.includes(highlightLower)

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'w-full cursor-pointer justify-start rounded-md border border-border/60 bg-background/60 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-[hsl(var(--primary))]/35 hover:bg-[hsl(var(--primary))]/5 disabled:opacity-50',
        className,
      )}
    >
      {shouldHighlight ? (
        (() => {
          const index = contentLower.indexOf(highlightLower)
          if (index === -1) return <span className="whitespace-pre-wrap">{content}</span>
          const actual = content.substring(index, index + highlightLower.length)
          return (
            <>
              <span className="whitespace-pre-wrap">{content.substring(0, index)}</span>
              <span className="font-medium text-[hsl(var(--primary))] whitespace-pre-wrap">{actual}</span>
              <span className="whitespace-pre-wrap">
                {content.substring(index + actual.length)}
              </span>
            </>
          )
        })()
      ) : (
        <span className="whitespace-pre-wrap">{content}</span>
      )}
    </button>
  )
}

export function SuggestionChips({
  input,
  onPick,
  dynamicSuggestions,
  className,
}: {
  /** 当前输入（用于模板联想与高亮） */
  input?: string
  onPick: (idea: string) => void
  /** 动态建议（P1：LLM 补全） */
  dynamicSuggestions?: string[]
  className?: string
}) {
  const [seed, setSeed] = useState(0)
  const t = (input ?? '').trim()

  const { matched, randomIdea } = useMemo(() => {
    const matched = matchTemplate(t)
    // 🎲 随机示例（seed 变化时重新取）
    const random = PMPT_TMPLATS[seed % PMPT_TMPLATS.length]
    return { matched, randomIdea: random }
  }, [t, seed])

  const dynamic = dynamicSuggestions ?? []

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <span className="inline-flex items-center gap-1 text-sm text-muted-foreground/70">
        <Lightbulb className="h-3 w-3" /> 提示
      </span>

      {/* 动态建议（LLM 生成，P1） */}
      {dynamic.map((s) => (
        <SuggestionChip key={`dyn-${s}`} highlight={t} onClick={() => onPick(s)}>
          {s}
        </SuggestionChip>
      ))}

      {/* 输入联想模板 */}
      {matched.map((m) => (
        <SuggestionChip key={`m-${m}`} highlight={t} onClick={() => onPick(m)}>
          {m}
        </SuggestionChip>
      ))}

      {/* 无输入时的示例引导 */}
      {!t && (
        <SuggestionChip
          onClick={() => onPick(PMPT_TMPLATS[seed % PMPT_TMPLATS.length])}
        >
          <Sparkles className="h-3 w-3" />
          {PMPT_TMPLATS[seed % PMPT_TMPLATS.length]}
        </SuggestionChip>
      )}

      {/* 🎲 换一个方向 */}
      {!t && (
        <SuggestionChip
          onClick={() => setSeed((s) => s + 1)}
          title="随机换一个产品方向示例"
        >
          <Dices className="h-3 w-3" /> 换个方向
        </SuggestionChip>
      )}

      {/* 输入时显示当前联想的基础 */}
      {t && randomIdea && (
        <SuggestionChip
          onClick={() => setSeed((s) => s + 1)}
          title="基于当前输入换一个方向"
        >
          <Dices className="h-3 w-3" /> 换个方向
        </SuggestionChip>
      )}
    </div>
  )
}
