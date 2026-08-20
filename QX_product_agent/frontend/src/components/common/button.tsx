import * as React from 'react'
import { cn } from '@/lib/utils'

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
    | 'default'
    | 'secondary'
    | 'outline'
    | 'ghost'
    | 'destructive'
    | 'link'
  size?: 'sm' | 'md' | 'lg' | 'icon'
  loading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'default',
      size = 'md',
      loading,
      children,
      disabled,
      type = 'button',
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        className={cn(
          'relative inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40',
          'rounded-lg', // 默认圆角 10px
          {
            // Default — IBM 蓝主按钮
            'bg-primary text-primary-foreground shadow-elev-sm hover:bg-primary-hover hover:shadow-elev-md hover:-translate-y-0.5':
              variant === 'default',
            // Secondary — 弱化填充
            'bg-secondary text-secondary-foreground hover:bg-surface-overlay hover:shadow-elev-sm':
              variant === 'secondary',
            // Outline — 描边
            'border border-border bg-transparent text-foreground hover:border-primary/60 hover:bg-primary/10 hover:text-primary':
              variant === 'outline',
            // Ghost — 无背景
            'text-muted-foreground hover:bg-primary/10 hover:text-foreground':
              variant === 'ghost',
            // Destructive
            'bg-destructive text-destructive-foreground shadow-elev-sm hover:bg-destructive/90 hover:shadow-elev-md hover:-translate-y-0.5':
              variant === 'destructive',
            // Link — 文本链接
            'text-primary underline-offset-4 hover:underline px-0 h-auto rounded-none':
              variant === 'link',
          },
          {
            'h-8 px-3 text-xs': size === 'sm',
            'h-10 px-4 text-sm': size === 'md',
            'h-11 px-5 text-[15px]': size === 'lg',
            'h-10 w-10': size === 'icon',
          },
          className,
        )}
        {...props}
      >
        {loading && (
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    )
  },
)
Button.displayName = 'Button'