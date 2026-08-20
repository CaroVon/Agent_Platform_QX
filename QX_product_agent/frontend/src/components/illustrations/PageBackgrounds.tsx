/**
 * PageBackgrounds —— 页面级装饰背景插图（v2：现代科技商务风格）
 *
 * 比 ModernIllustrations 更大型、更具叙事性，用于：
 *  - 页面 Hero 区域背景叠加
 *  - 空白状态氛围渲染
 *  - 错误页 / 空状态插图
 *
 * 风格：单色描线（currentColor）+ 局部柔光描点
 */

import { cn } from '@/lib/utils'

/* ─── 大型 Hero 背景：城市蓝图 + 数据流叠加 ─────────────── */
export function HeroCityBackground({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 1200 600"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern id="hero-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path
            d="M 40 0 L 0 0 0 40"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            opacity="0.3"
          />
        </pattern>
        <linearGradient id="hero-fade" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.15" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="hero-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.4" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 网格 */}
      <rect width="1200" height="600" fill="url(#hero-grid)" />

      {/* 天际线（远景） */}
      <g stroke="currentColor" strokeWidth="1.4" fill="none" opacity="0.55">
        <path d="M0 460 L40 460 L40 380 L80 380 L80 360 L120 360 L120 400 L160 400 L160 340 L200 340 L200 380 L240 380 L240 320 L280 320 L280 360 L320 360 L320 300 L360 300 L360 340 L400 340 L400 280 L440 280 L440 320 L480 320 L480 360 L520 360 L520 300 L560 300 L560 340 L600 340 L600 380 L640 380 L640 320 L680 320 L680 360 L720 360 L720 300 L760 300 L760 340 L800 340 L800 380 L840 380 L840 320 L880 320 L880 360 L920 360 L920 380 L960 380 L960 340 L1000 340 L1000 380 L1040 380 L1040 360 L1080 360 L1080 380 L1120 380 L1120 340 L1160 340 L1160 380 L1200 380 L1200 460 Z" />
      </g>

      {/* 楼宇窗户网格 */}
      <g fill="currentColor" opacity="0.55">
        {Array.from({ length: 30 }).map((_, i) => (
          <rect
            key={`w-${i}`}
            x={20 + i * 38 + (i % 3) * 4}
            y={350 + (i % 4) * 18}
            width="3"
            height="6"
          />
        ))}
        {Array.from({ length: 25 }).map((_, i) => (
          <rect
            key={`w2-${i}`}
            x={40 + i * 46 + (i % 2) * 6}
            y={310 + (i % 5) * 12}
            width="2"
            height="4"
            opacity="0.6"
          />
        ))}
      </g>

      {/* 数据曲线叠加 */}
      <g fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.6">
        <path d="M0 520 Q300 460 600 480 T1200 440" />
        <path d="M0 560 Q300 520 600 540 T1200 500" opacity="0.5" />
        <path d="M0 580 Q300 560 600 580 T1200 560" opacity="0.3" />
      </g>

      {/* 节点标定 */}
      <g fill="currentColor" opacity="0.8">
        <circle cx="180" cy="480" r="3.5" />
        <circle cx="480" cy="460" r="4" />
        <circle cx="780" cy="470" r="3.5" />
        <circle cx="1080" cy="450" r="4" />
      </g>

      {/* 顶部光晕 */}
      <ellipse cx="600" cy="0" rx="500" ry="220" fill="url(#hero-glow)" />

      {/* 渐变遮罩 */}
      <rect width="1200" height="600" fill="url(#hero-fade)" />
    </svg>
  )
}

/* ─── 抽象几何拼贴（用于装饰面板） ───────────────────── */
export function AbstractGeometricBackground({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 600 400"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern id="ag-grid" width="32" height="32" patternUnits="userSpaceOnUse">
          <path
            d="M 32 0 L 0 0 0 32"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.4"
            opacity="0.4"
          />
        </pattern>
      </defs>
      <rect width="600" height="400" fill="url(#ag-grid)" />
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.7">
        <circle cx="120" cy="100" r="60" />
        <circle cx="120" cy="100" r="40" opacity="0.6" />
        <rect x="280" y="60" width="160" height="120" rx="4" />
        <rect x="300" y="80" width="120" height="80" rx="4" opacity="0.6" />
        <polygon points="480,180 560,260 400,260" />
        <polygon points="490,200 540,250 440,250" opacity="0.5" />
        <line x1="0" y1="320" x2="600" y2="320" strokeWidth="0.6" opacity="0.5" />
        <line x1="0" y1="340" x2="600" y2="340" strokeWidth="0.6" opacity="0.3" />
        <line x1="0" y1="360" x2="600" y2="360" strokeWidth="0.6" opacity="0.2" />
      </g>
      <g fill="currentColor" opacity="0.6">
        <circle cx="120" cy="100" r="4" />
        <circle cx="320" cy="120" r="4" />
        <circle cx="480" cy="230" r="4" />
        <rect x="40" y="330" width="120" height="6" opacity="0.5" />
        <rect x="180" y="330" width="60" height="6" opacity="0.3" />
        <rect x="260" y="330" width="200" height="6" opacity="0.4" />
      </g>
    </svg>
  )
}

/* ─── 简洁数据波（用于装饰） ─────────────────────────── */
export function DataWaveBackground({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 600 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1">
        <path d="M0 100 Q60 70 120 100 T240 100 T360 100 T480 100 T600 100" opacity="0.4" />
        <path d="M0 110 Q60 90 120 110 T240 110 T360 110 T480 110 T600 110" opacity="0.55" />
        <path d="M0 120 Q60 110 120 120 T240 120 T360 120 T480 120 T600 120" opacity="0.7" />
        <path d="M0 130 Q60 125 120 130 T240 130 T360 130 T480 130 T600 130" opacity="0.85" />
      </g>
    </svg>
  )
}

/* ─── 节点网络（装饰条带） ───────────────────────────── */
export function NetworkStripBackground({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 600 120"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5">
        <line x1="20" y1="60" x2="120" y2="60" />
        <line x1="120" y1="60" x2="220" y2="40" />
        <line x1="120" y1="60" x2="220" y2="80" />
        <line x1="220" y1="40" x2="320" y2="60" />
        <line x1="220" y1="80" x2="320" y2="60" />
        <line x1="320" y1="60" x2="420" y2="50" />
        <line x1="320" y1="60" x2="420" y2="70" />
        <line x1="420" y1="50" x2="520" y2="60" />
        <line x1="420" y1="70" x2="520" y2="60" />
        <line x1="520" y1="60" x2="580" y2="60" />
      </g>
      <g fill="currentColor">
        <circle cx="20" cy="60" r="4" opacity="0.9" />
        <circle cx="120" cy="60" r="5" opacity="1" />
        <circle cx="220" cy="40" r="4" opacity="0.7" />
        <circle cx="220" cy="80" r="4" opacity="0.7" />
        <circle cx="320" cy="60" r="6" opacity="1" />
        <circle cx="420" cy="50" r="4" opacity="0.7" />
        <circle cx="420" cy="70" r="4" opacity="0.7" />
        <circle cx="520" cy="60" r="5" opacity="0.9" />
        <circle cx="580" cy="60" r="4" opacity="0.7" />
      </g>
    </svg>
  )
}

/* ─── 空状态插图 ─────────────────────────────────────── */
export function EmptyStateIllustration({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 160"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-32 w-40', className)}
      aria-hidden
      {...props}
    >
      <defs>
        <linearGradient id="emp-fade" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.4" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <ellipse cx="100" cy="140" rx="60" ry="6" fill="currentColor" opacity="0.15" />
      <rect
        x="55"
        y="40"
        width="90"
        height="90"
        fill="url(#emp-fade)"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity="0.7"
      />
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        opacity="0.65"
      >
        <line x1="55" y1="60" x2="145" y2="60" />
        <line x1="55" y1="80" x2="120" y2="80" />
        <line x1="55" y1="100" x2="100" y2="100" />
        <line x1="55" y1="120" x2="90" y2="120" />
      </g>
      <g fill="currentColor" opacity="0.85">
        <circle cx="100" cy="40" r="4" />
        <circle cx="100" cy="40" r="9" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      </g>
    </svg>
  )
}

/* ─── 渐变光晕（圆角背景融合） ─────────────────────────── */
export function AmbientGlow({
  className,
  color = 'primary',
  ...props
}: React.SVGProps<SVGSVGElement> & { color?: 'primary' | 'accent' | 'mixed' }) {
  const stops = {
    primary: { from: 'hsl(217 91% 60% / 0.5)', to: 'transparent' },
    accent: { from: 'hsl(199 89% 48% / 0.45)', to: 'transparent' },
    mixed: { from: 'hsl(217 91% 60% / 0.4)', to: 'hsl(199 89% 48% / 0)' },
  }[color]
  return (
    <svg
      viewBox="0 0 400 400"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      {...props}
    >
      <defs>
        <radialGradient id={`ag-${color}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={stops.from} />
          <stop offset="100%" stopColor={stops.to} />
        </radialGradient>
      </defs>
      <rect width="400" height="400" fill={`url(#ag-${color})`} />
    </svg>
  )
}