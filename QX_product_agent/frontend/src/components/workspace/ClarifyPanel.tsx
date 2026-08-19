/**
 * ClarifyPanel —— 对话式产品输入面板
 *
 * 消息气泡列表 + ChatInput（对话输入区）+ SuggestionChips（提示词建议）
 * + 「生成产品」动作（brief 就绪后亮起）
 */

import { useRef } from 'react'
import { AlertCircle, Eraser, Rocket, Sparkles, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useClarifyChat } from '@/hooks/useClarifyChat'
import {
  ChatInput,
  ChatInputActions,
  ChatInputSendButton,
  ChatInputTextarea,
} from '@/components/workspace/ChatInput'
import { SuggestionChips } from '@/components/workspace/SuggestionChips'

export function ClarifyPanel({
  creating,
  onGenerate,
  dynamicSuggestions,
  onSuggestionDynamic,
}: {
  creating: boolean
  /** brief 就绪后回调（父组件调用 productApi.create） */
  onGenerate: (brief: string) => void
  /** 动态建议列表（P1：LLM 补全） */
  dynamicSuggestions?: string[]
  /** 输入变化回调（P1：触发动态建议拉取） */
  onSuggestionDynamic?: (input: string) => void
}) {
  const chat = useClarifyChat()
  const listRef = useRef<HTMLDivElement>(null)

  const handlePick = (idea: string) => {
    chat.setIdea(idea)
    if (chat.messages.length === 0) {
      // 空会话：chips 直接作为首条消息发出（快速起聊）
      chat.send(idea)
    } else {
      // 会话中：作为补充消息发送
      chat.send(idea)
    }
  }

  const handleSend = () => {
    const input = chat.idea.trim()
    if (!input || chat.isLoading) return
    chat.send(input)
    chat.setIdea('')
  }

  return (
    <div className="flex w-full flex-col">
      {/* ── 消息列表 ─────────────────────────────────────── */}
      <div
        ref={listRef}
        className="max-h-[420px] space-y-3 overflow-y-auto pr-1"
      >
        {chat.messages.length === 0 && (
          <div className="flex flex-col items-center py-6 text-center">
            <span className="animate-breathe mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border bg-card">
              <Sparkles className="h-5 w-5 text-[#24415E]" />
            </span>
            <h2 className="font-editorial text-xl font-semibold text-foreground">
              与 AI 产品团队对话，描述你的想法
            </h2>
            <p className="mt-2 max-w-md text-xs leading-relaxed text-muted-foreground">
              直接输入一句话，或从下方提示中选择一个方向。
              AI 会像产品经理一样追问目标用户、场景与约束，信息足够后即可一键生成全套产品资产。
            </p>
          </div>
        )}

        {chat.messages.map((m, i) => (
          <div
            key={i}
            className={cn(
              'flex gap-2.5',
              m.role === 'user' ? 'justify-end' : 'justify-start',
            )}
          >
            {m.role === 'assistant' && (
              <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#24415E]/10">
                <Sparkles className="h-3 w-3 text-[#24415E]" />
              </span>
            )}
            <div
              className={cn(
                'max-w-[78%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed',
                m.role === 'user'
                  ? 'bg-[#24415E] text-white'
                  : 'border border-border/70 bg-card text-foreground',
              )}
            >
              {m.content}
            </div>
            {m.role === 'user' && (
              <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-secondary">
                <User className="h-3 w-3 text-muted-foreground" />
              </span>
            )}
          </div>
        ))}

        {/* 流式回复 */}
        {chat.streaming && (
          <div className="flex gap-2.5">
            <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[#24415E]/10">
              <Sparkles className="h-3 w-3 text-[#24415E]" />
            </span>
            <div className="max-w-[78%] whitespace-pre-wrap rounded-2xl border border-border/70 bg-card px-4 py-2.5 text-[13px] leading-relaxed text-foreground">
              {chat.streaming}
              <span className="typing-dot ml-1 inline-block" />
            </div>
          </div>
        )}

        {chat.error && (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {chat.error}
          </div>
        )}
      </div>

      {/* ── 输入区（ChatInput = PromptInput 移植） ─────────── */}
      <div className="mt-4">
        <ChatInput
          value={chat.idea}
          onValueChange={(v) => {
            chat.setIdea(v)
            onSuggestionDynamic?.(v)
          }}
          onSubmit={handleSend}
          isLoading={chat.isLoading}
          disabled={creating}
        >
          <ChatInputTextarea
            placeholder="描述你的想法，如：想做一个帮老人按时吃药的产品…"
            disabled={creating}
          />
          <ChatInputActions>
            {chat.isLoading && (
              <button
                type="button"
                onClick={chat.stop}
                className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-secondary"
              >
                停止
              </button>
            )}
            {chat.hasSession && !chat.isLoading && (
              <button
                type="button"
                onClick={chat.reset}
                title="清空对话，重新开始"
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary"
              >
                <Eraser className="h-3.5 w-3.5" />
              </button>
            )}
            <ChatInputSendButton label={creating ? '生成中' : '发送'} />
          </ChatInputActions>
        </ChatInput>

        {/* ── 提示词建议 chips（PromptSuggestion 移植） ──── */}
        <SuggestionChips
          input={chat.idea}
          onPick={handlePick}
          dynamicSuggestions={dynamicSuggestions}
          className="mt-3"
        />
      </div>

      {/* ── 生成产品（brief 就绪后亮起） ─────────────────── */}
      <div className="mt-4 flex items-center justify-between border-t border-border/60 pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {chat.canGenerate
            ? '✅ 需求信息已足够，可以生成完整产品资产（研究 → PRD → 设计 → 演示）'
            : `💬 继续对话以完善需求（目标用户 / 场景 / 功能 / 约束）${
                chat.signal
                  ? ` — 已覆盖 ${Object.values(chat.signal.dimensions).filter(Boolean).length}/4`
                  : ''
              }`}
        </p>
        <button
          type="button"
          disabled={!chat.canGenerate || creating}
          onClick={() => onGenerate(chat.buildBrief())}
          className={cn(
            'inline-flex shrink-0 items-center gap-1.5 rounded-lg px-5 py-2.5 text-xs font-medium text-white transition-opacity',
            chat.canGenerate
              ? 'bg-[#24415E] hover:opacity-90'
              : 'cursor-not-allowed bg-[#24415E]/30',
          )}
        >
          <Rocket className="h-3.5 w-3.5" />
          {creating ? '生成中…' : '生成产品 →'}
        </button>
      </div>
    </div>
  )
}
