import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          hover: 'hsl(var(--primary-hover))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
        },
        surface: {
          DEFAULT: 'hsl(var(--surface))',
          raised: 'hsl(var(--surface-raised))',
          overlay: 'hsl(var(--surface-overlay))',
        },
      },
      borderRadius: {
        sm: '0.375rem',
        md: '0.625rem',
        lg: '0.875rem',
        xl: '1.125rem',
        '2xl': '1.5rem',
        DEFAULT: '0.625rem',
      },
      fontFamily: {
        sans: [
          'Noto Sans SC',
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        body: ['Noto Sans SC', 'Inter', 'system-ui', 'sans-serif'],
        serif: ['Noto Serif SC', 'Source Han Serif SC', 'Songti SC', 'serif'],
        display: ['Noto Serif SC', 'Songti SC', 'serif'],
        mono: [
          'JetBrains Mono',
          'IBM Plex Mono',
          'Fira Code',
          'SF Mono',
          'Cascadia Code',
          'Consolas',
          'monospace',
        ],
      },
      boxShadow: {
        'elev-xs': '0 1px 2px rgba(0,0,0,0.20)',
        'elev-sm': '0 2px 4px rgba(0,0,0,0.25), 0 1px 2px rgba(0,0,0,0.15)',
        'elev-md': '0 6px 12px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15)',
        'elev-lg': '0 14px 24px rgba(0,0,0,0.30), 0 4px 8px rgba(0,0,0,0.15)',
        'elev-xl': '0 24px 36px rgba(0,0,0,0.35), 0 10px 14px rgba(0,0,0,0.10)',
        'elev-glow':
          '0 0 0 1px hsl(217 91% 60% / 0.40), 0 0 20px hsl(217 91% 60% / 0.25)',
        'focus-ring': '0 0 0 3px hsl(217 91% 60% / 0.25)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-fast': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96) translateY(8px)' },
          to: { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(24px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'page-enter': {
          from: { opacity: '0', transform: 'translateY(16px) scale(0.99)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '0.5', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.15)' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in-fast': 'fade-in-fast 0.25s ease-out both',
        'scale-in': 'scale-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-up': 'slide-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-down': 'slide-down 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
        'page-enter': 'page-enter 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        'shimmer': 'shimmer 2s linear infinite',
        'pulse-dot': 'pulse-dot 1.8s ease-in-out infinite',
        'spin-slow': 'spin-slow 12s linear infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}

export default config