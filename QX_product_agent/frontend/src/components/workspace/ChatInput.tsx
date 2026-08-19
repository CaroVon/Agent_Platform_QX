/**
 * ChatInput —— 对话式输入区
 *
 * 由 prompt-kit 的 PromptInput 移植适配：
 *  - 保留 Context 模式 / 自增高 Textarea / Enter 发送 Shift+Enter 换行
 *  - 适配：React 18（无 useActionState）、项目纸感 Design Token（rounded-xl/bg-card）
 *  - 新增：发送按钮、加载态、禁用态、suggestion chips 插槽
 *
 * 源码参考：https://github.com/ibelick/prompt-kit（MIT）
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { Loader2, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

type ChatInputContextType = {
  isLoading: boolean
  value: string
  setValue: (value: string) => void
  maxHeight: number | string
  onSubmit?: () => void
  disabled?: boolean
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
}

const ChatInputContext = createContext<ChatInputContextType>({
  isLoading: false,
  value: '',
  setValue: () => {},
  maxHeight: 200,
  onSubmit: undefined,
  disabled: false,
  textareaRef: React.createRef<HTMLTextAreaElement>(),
})

export function useChatInput() {
  return useContext(ChatInputContext)
}

export type ChatInputProps = {
  isLoading?: boolean
  value?: string
  onValueChange?: (value: string) => void
  maxHeight?: number | string
  onSubmit?: () => void
  children: React.ReactNode
  className?: string
  disabled?: boolean
} & React.ComponentProps<'div'>

export function ChatInput({
  className,
  isLoading = false,
  maxHeight = 200,
  value,
  onValueChange,
  onSubmit,
  children,
  disabled = false,
  onClick,
  ...props
}: ChatInputProps) {
  const [internalValue, setInternalValue] = useState(value || '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleChange = useCallback(
    (newValue: string) => {
      setInternalValue(newValue)
      onValueChange?.(newValue)
    },
    [onValueChange],
  )

  const handleClick: React.MouseEventHandler<HTMLDivElement> = (e) => {
    if (!disabled) textareaRef.current?.focus()
    onClick?.(e)
  }

  return (
    <ChatInputContext.Provider
      value={{
        isLoading,
        value: value ?? internalValue,
        setValue: onValueChange ?? handleChange,
        maxHeight,
        onSubmit,
        disabled,
        textareaRef,
      }}
    >
      <div
        onClick={handleClick}
        className={cn(
          'cursor-text rounded-2xl border border-border/80 bg-card p-2 shadow-sm transition-colors focus-within:border-[#24415E]/40',
          disabled && 'cursor-not-allowed opacity-60',
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </ChatInputContext.Provider>
  )
}

export type ChatInputTextareaProps = {
  disableAutosize?: boolean
  placeholder?: string
  rows?: number
} & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange' | 'value'>

export function ChatInputTextarea({
  className,
  onKeyDown,
  disableAutosize = false,
  placeholder = '描述你的想法…（Enter 发送，Shift+Enter 换行）',
  rows = 1,
  ...props
}: ChatInputTextareaProps) {
  const { value, setValue, maxHeight, onSubmit, disabled, textareaRef } =
    useChatInput()

  const adjustHeight = useCallback(
    (el: HTMLTextAreaElement | null) => {
      if (!el || disableAutosize) return
      el.style.height = 'auto'
      const target =
        typeof maxHeight === 'number'
          ? Math.min(el.scrollHeight, maxHeight)
          : Math.min(el.scrollHeight, Number(String(maxHeight).replace('px', '')) || 200)
      el.style.height = `${target}px`
    },
    [disableAutosize, maxHeight],
  )

  // React 18: RefObject.current 只读，用回调 ref 设置（与 prompt-kit 的 React 19 写法兼容）
  const handleRef = useCallback(
    (el: HTMLTextAreaElement | null) => {
      ;(textareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el
      adjustHeight(el)
    },
    [adjustHeight, textareaRef],
  )

  useLayoutEffect(() => {
    if (!textareaRef.current || disableAutosize) return
    adjustHeight(textareaRef.current)
  }, [value, maxHeight, disableAutosize, adjustHeight])

  return (
    <textarea
      ref={handleRef}
      value={value}
      rows={rows}
      placeholder={placeholder}
      onChange={(e) => {
        adjustHeight(e.target)
        setValue(e.target.value)
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
          e.preventDefault()
          if (!disabled && value.trim()) onSubmit?.()
        }
        onKeyDown?.(e)
      }}
      disabled={disabled}
      className={cn(
        'text-foreground min-h-[44px] w-full resize-none border-none bg-transparent px-2 py-2.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60',
        className,
      )}
      {...props}
    />
  )
}

export function ChatInputActions({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-center justify-end gap-2 px-1 pb-0.5', className)} {...props}>
      {children}
    </div>
  )
}

/** 发送按钮（含加载态） */
export function ChatInputSendButton({
  className,
  label = '发送',
}: {
  className?: string
  label?: string
}) {
  const { isLoading, value, onSubmit, disabled } = useChatInput()
  const canSend = !disabled && !isLoading && !!value.trim()
  return (
    <button
      type="button"
      disabled={!canSend}
      onClick={onSubmit}
      title="发送（Enter）"
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#24415E] px-3.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40',
        className,
      )}
    >
      {isLoading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Send className="h-3.5 w-3.5" />
      )}
      {label}
    </button>
  )
}
