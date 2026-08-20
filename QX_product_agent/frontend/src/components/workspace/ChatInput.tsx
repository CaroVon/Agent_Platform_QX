/**
 * ChatInput —— 对话输入区（v2：商务版）
 */

import {
  type ReactNode,
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { Loader2, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ─── Context ──────────────────────────────────────── */
interface ChatInputContextValue {
  value: string
  setValue: (v: string) => void
  maxHeight?: number | string
  onSubmit?: () => void
  disabled?: boolean
  isLoading?: boolean
  textareaRef: React.MutableRefObject<HTMLTextAreaElement | null>
}

const ChatInputContext = createContext<ChatInputContextValue | null>(null)

function useChatInput() {
  const ctx = useContext(ChatInputContext)
  if (!ctx) throw new Error('useChatInput must be used within ChatInput')
  return ctx
}

/* ─── oot ──────────────────────────────────────────── */
interface ChatInputProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  value?: string
  onValueChange?: (value: string) => void
  onSubmit?: () => void
  isLoading?: boolean
  disabled?: boolean
  maxHeight?: number | string
  children?: ReactNode
}

export function ChatInput({
  value: controlled,
  onValueChange,
  onSubmit,
  isLoading,
  disabled,
  maxHeight = 200,
  className,
  children,
  ...props
}: ChatInputProps) {
  const [internal, setInternal] = useState(controlled ?? '')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const handleChange = useCallback(
    (v: string) => {
      setInternal(v)
      onValueChange?.(v)
    },
    [onValueChange],
  )

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (
      e.target instanceof HTMLElement &&
      e.target.closest('button, a, textarea, input')
    )
      return
    textareaRef.current?.focus()
  }, [])

  return (
    <ChatInputContext.Provider
      value={{
        value: controlled ?? internal,
        setValue: onValueChange ?? handleChange,
        maxHeight,
        onSubmit,
        disabled,
        isLoading,
        textareaRef,
      }}
    >
      <div
        onClick={handleClick}
        className={cn(
          'rounded-md border border-border bg-card p-2 shadow-elev-xs transition-all focus-within:border-primary focus-within:shadow-focus-ring',
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

/* ─── Textarea ──────────────────────────────────────── */
export type ChatInputTextareaProps = {
  disableAutosize?: boolean
  placeholder?: string
  rows?: number
} & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange' | 'value'>

export const ChatInputTextarea = forwardRef<HTMLTextAreaElement, ChatInputTextareaProps>(
  ({ className, onKeyDown, disableAutosize = false, placeholder, rows = 1, ...props }, _ref) => {
    const { value, setValue, maxHeight, onSubmit, disabled, textareaRef } = useChatInput()

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

    const handleRef = useCallback(
      (el: HTMLTextAreaElement | null) => {
        textareaRef.current = el
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
          if (e.key === 'nter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            if (!disabled && value.trim()) onSubmit?.()
          }
          onKeyDown?.(e)
        }}
        disabled={disabled}
        className={cn(
          'min-h-[44px] w-full resize-none border-none bg-transparent px-2.5 py-2.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/70',
          className,
        )}
        {...props}
      />
    )
  },
)
ChatInputTextarea.displayName = 'ChatInputTextarea'

/* ─── Actions ───────────────────────────────────────── */
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

/* ─── SendButton ───────────────────────────────────── */
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
      title="发送（nter）"
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-foreground shadow-elev-xs transition-all hover:bg-primary-hover hover:shadow-elev-md active:translate-y-px disabled:opacity-40 disabled:shadow-none',
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
