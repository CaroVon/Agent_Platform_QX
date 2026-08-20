/**
 * ClarifyPanel —— 对话式产品输入面板（v2：商务版）
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
  onGenerate: (brief: string) => void
  dynamicSuggestions?: string[]
  onSuggestionDynamic?: (input: string) => void
}) {
  const chat = useClarifyChat()
  const listRef = useRef<HTMLDivElement>(null)

  const handlePick = (idea: string) => {
    chat.setIdea(idea)
    if (chat.messages.length === 0) chat.send(idea)
    else chat.send(idea)
  }

  const handleSend = () => {
    const input = chat.idea.trim()
    if (!input || chat.isLoading) return
    chat.send(input)
    chat.setIdea('')
  }

  return (
    <div className="flex w-full flex-col">
      {/* 消息列表 */}
      <div ref={listRef} className="max-h-[420px] space-y-4 overflow-y-auto pr-1">
        {chat.messages.length === 0 && (
          <div className="flex flex-col items-center py-6 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 shadow-elev-glow">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <h2 className="font-display text-xl font-semibold tracking-tight text-foreground">
              与 AI 产品团队对话
            </h2>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
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
              <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
              </div>
            )}
            <div
              className={cn(
                'max-w-[78%] whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm leading-relaxed shadow-elev-xs',
                m.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'border border-border bg-card text-foreground',
              )}
            >
              {m.content}
            </div>
            {m.role === 'user' && (
              <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/20">
                <User className="h-3.5 w-3.5 text-accent" />
              </div>
            )}
          </div>
        ))}

        {chat.streaming && (
          <div className="flex gap-2.5">
            <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
            </div>
            <div className="max-w-[78%] whitespace-pre-wrap rounded-lg border border-border bg-card px-4 py-2.5 text-sm leading-relaxed text-foreground shadow-elev-xs">
              {chat.streaming}
              <span className="typing-dot ml-1 inline-block" />
            </div>
          </div>
        )}

        {chat.error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span className="font-medium"></span>
            <span className="text-destructive/80">{chat.error}</span>
          </div>
        )}
      </div>

      {/* 输入区 */}
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
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                停止
              </button>
            )}
            {chat.hasSession && !chat.isLoading && (
              <button
                type="button"
                onClick={chat.reset}
                title="清空对话，重新开始"
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <Eraser className="h-3.5 w-3.5" />
              </button>
            )}
            <ChatInputSendButton label={creating ? '生成中' : '发送'} />
          </ChatInputActions>
        </ChatInput>

        <SuggestionChips
          input={chat.idea}
          onPick={handlePick}
          dynamicSuggestions={dynamicSuggestions}
          className="mt-3"
        />
      </div>

      {/* 生成按钮 */}
      <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-sm text-muted-foreground">
          {chat.canGenerate
            ? '✓ 需求信息已足够，可以生成完整产品资产（研究 → PD → 设计 → 演示）'
            : `继续对话以完善需求（目标用户 / 场景 / 功能 / 约束）${
                chat.signal
                  ? ` · 已覆盖 ${Object.values(chat.signal.dimensions).filter(Boolean).length}/4`
                  : ''
              }`}
        </p>
        <button
          type="button"
          disabled={!chat.canGenerate || creating}
          onClick={() => onGenerate(chat.buildBrief())}
          className={cn(
            'inline-flex shrink-0 items-center gap-2 rounded-md px-5 py-2.5 text-sm font-medium transition-all active:translate-y-px',
            chat.canGenerate
              ? 'bg-primary text-primary-foreground shadow-elev-sm hover:bg-primary-hover hover:shadow-elev-md'
              : 'cursor-not-allowed bg-secondary text-muted-foreground',
          )}
        >
          <Rocket className="h-3.5 w-3.5" />
          {creating ? '生成中…' : '生成产品'}
        </button>
      </div>
    </div>
  )
}
