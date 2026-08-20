/**
 * ModernIllustrations —— 现代科技商务 SVG 装饰插图库
 *
 * 设计原则：
 *  - 抽象几何（蓝图/数据/网络/波形），可独立使用或作为Background叠加
 *  - 主色用 currentColor（CSS 变量驱动），可随主题切换深/浅
 *  - 每个组件都有 aspect 比例，便于灵活布局
 *  - 装饰性，不喧宾夺主
 */

import { cn } from '@/lib/utils'

/* ─── 1. 抽象蓝图（grid + 几何线） ──────────────────── */
export function AbstractBlueprint({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern id="bp-grid" width="20" height="20" patternUnits="userSpacenUse">
          <path
            d="M 20 0 L 0 0 0 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.4"
            opacity="0.35"
          />
        </pattern>
        <linearGradient id="bp-fade" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.6" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <rect width="400" height="300" fill="url(#bp-grid)" opacity="0.6" />
      <g stroke="url(#bp-fade)" strokeWidth="1" fill="none" opacity="0.7">
        <rect x="60" y="60" width="280" height="180" rx="2" />
        <rect x="80" y="80" width="240" height="140" rx="2" opacity="0.6" />
        <line x1="60" y1="120" x2="340" y2="120" opacity="0.4" />
        <line x1="60" y1="180" x2="340" y2="180" opacity="0.4" />
        <circle cx="120" cy="150" r="20" />
        <circle cx="200" cy="150" r="32" opacity="0.7" />
        <circle cx="280" cy="150" r="20" />
        <line x1="120" y1="150" x2="200" y2="150" />
        <line x1="200" y1="150" x2="280" y2="150" />
      </g>
      {/* 角落测量标记 */}
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.4">
        <path d="M60 50 L60 60 L70 60" />
        <path d="M340 50 L340 60 L330 60" />
        <path d="M60 250 L60 240 L70 240" />
        <path d="M340 250 L340 240 L330 240" />
      </g>
    </svg>
  )
}

/* ─── 2. 数据流（节点+箭头） ───────────────────────── */
export function DataFlow({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <linearGradient id="df-line" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.2" />
          <stop offset="50%" stopColor="currentColor" stopOpacity="0.8" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      <g fill="none" stroke="url(#df-line)" strokeWidth="1.4">
        <path d="M40 80 Q140 60 240 100 T 360 130" />
        <path d="M40 150 Q160 180 260 160 T 360 200" />
        <path d="M40 220 Q120 250 220 220 T 360 240" />
      </g>
      <g fill="currentColor" opacity="0.85">
        <circle cx="40" cy="80" r="4" />
        <circle cx="240" cy="100" r="5" />
        <circle cx="360" cy="130" r="6" />
        <circle cx="40" cy="150" r="4" />
        <circle cx="160" cy="180" r="5" />
        <circle cx="260" cy="160" r="6" />
        <circle cx="360" cy="200" r="7" />
        <circle cx="40" cy="220" r="4" />
        <circle cx="120" cy="250" r="5" />
        <circle cx="220" cy="220" r="6" />
        <circle cx="360" cy="240" r="8" />
      </g>
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.3">
        <rect x="345" y="115" width="30" height="30" rx="2" />
        <rect x="345" y="185" width="30" height="30" rx="2" />
        <rect x="345" y="225" width="30" height="30" rx="2" />
      </g>
    </svg>
  )
}

/* ─── 3. 波形线（频谱/声波） ───────────────────────── */
export function WaveLines({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      >
        <path
          d="M0 100 Q50 60 100 100 T200 100 T300 100 T400 100"
          opacity="0.4"
        />
        <path
          d="M0 100 Q40 80 80 100 T160 100 T240 100 T320 100 T400 100"
          opacity="0.5"
        />
        <path
          d="M0 100 Q30 90 60 100 T120 100 T180 100 T240 100 T300 100 T360 100 T400 100"
          opacity="0.6"
        />
        <path
          d="M0 100 Q25 95 50 100 T100 100 T150 100 T200 100 T250 100 T300 100 T350 100 T400 100"
          opacity="0.8"
        />
        <path
          d="M0 100 Q20 97 40 100 T80 100 T120 100 T160 100 T200 100 T240 100 T280 100 T320 100 T360 100 T400 100"
          opacity="0.7"
        />
      </g>
    </svg>
  )
}

/* ─── 4. 轨道系统 ─────────────────────────────────── */
export function rbitSystem({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 400"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.5">
        <circle cx="200" cy="200" r="60" />
        <circle cx="200" cy="200" r="100" />
        <circle cx="200" cy="200" r="140" opacity="0.7" />
        <circle cx="200" cy="200" r="170" opacity="0.5" />
        <ellipse
          cx="200"
          cy="200"
          rx="170"
          ry="40"
          transform="rotate(-20 200 200)"
          opacity="0.4"
        />
      </g>
      <circle cx="200" cy="200" r="14" fill="currentColor" opacity="0.9" />
      <circle cx="200" cy="200" r="22" fill="none" stroke="currentColor" strokeWidth="1" />
      <g fill="currentColor">
        <circle cx="300" cy="200" r="5" />
        <circle cx="100" cy="200" r="4" opacity="0.7" />
        <circle cx="200" cy="60" r="6" />
        <circle cx="200" cy="340" r="3" opacity="0.6" />
      </g>
      {/* 卫星轨迹线 */}
      <g stroke="currentColor" strokeWidth="0.6" fill="none" opacity="0.4">
        <line x1="300" y1="200" x2="320" y2="180" />
        <line x1="100" y1="200" x2="80" y2="220" />
      </g>
    </svg>
  )
}

/* ─── 5. 城市网格（楼群轮廓） ─────────────────────── */
export function CityGrid({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1">
        <path d="M0 180 L0 140 L20 140 L20 110 L40 110 L40 140 L60 140 L60 80 L80 80 L80 60 L100 60 L100 100 L120 100 L120 70 L140 70 L140 120 L160 120 L160 50 L180 50 L180 90 L200 90 L200 40 L220 40 L220 100 L240 100 L240 60 L260 60 L260 110 L280 110 L280 80 L300 80 L300 130 L320 130 L320 90 L340 90 L340 50 L360 50 L360 100 L380 100 L380 70 L400 70 L400 180 Z" />
      </g>
      {/* 窗户细节 */}
      <g fill="currentColor" opacity="0.4">
        <rect x="64" y="92" width="2" height="3" />
        <rect x="68" y="92" width="2" height="3" />
        <rect x="64" y="100" width="2" height="3" />
        <rect x="124" y="80" width="2" height="3" />
        <rect x="124" y="90" width="2" height="3" />
        <rect x="164" y="60" width="2" height="3" />
        <rect x="168" y="60" width="2" height="3" />
        <rect x="164" y="70" width="2" height="3" />
        <rect x="204" y="52" width="2" height="3" />
        <rect x="204" y="62" width="2" height="3" />
        <rect x="204" y="72" width="2" height="3" />
        <rect x="244" y="72" width="2" height="3" />
        <rect x="244" y="82" width="2" height="3" />
        <rect x="284" y="92" width="2" height="3" />
        <rect x="324" y="100" width="2" height="3" />
      </g>
    </svg>
  )
}

/* ─── 6. 六边形蜂巢 ──────────────────────────────── */
export function HexPattern({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern
          id="hex-pat"
          x="0"
          y="0"
          width="30"
          height="26"
          patternUnits="userSpacenUse"
        >
          <polygon
            points="15,2 28,9 28,22 15,29 2,22 2,9"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.6"
            opacity="0.5"
          />
        </pattern>
      </defs>
      <rect width="400" height="300" fill="url(#hex-pat)" />
      {/* 高亮几个 */}
      <g fill="currentColor" opacity="0.8">
        <polygon points="120,80 133,87 133,101 120,108 107,101 107,87" />
        <polygon points="240,160 253,167 253,181 240,188 227,181 227,167" />
        <polygon points="320,100 333,107 333,121 320,128 307,121 307,107" opacity="0.5" />
      </g>
    </svg>
  )
}

/* ─── 7. 抽象柱状图 ───────────────────────────────── */
export function BarChart({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g fill="currentColor">
        <rect x="20" y="140" width="20" height="40" opacity="0.4" />
        <rect x="50" y="110" width="20" height="70" opacity="0.5" />
        <rect x="80" y="80" width="20" height="100" opacity="0.6" />
        <rect x="110" y="100" width="20" height="80" opacity="0.55" />
        <rect x="140" y="60" width="20" height="120" opacity="0.7" />
        <rect x="170" y="90" width="20" height="90" opacity="0.6" />
        <rect x="200" y="50" width="20" height="130" opacity="0.8" />
        <rect x="230" y="70" width="20" height="110" opacity="0.65" />
        <rect x="260" y="40" width="20" height="140" opacity="0.85" />
        <rect x="290" y="20" width="20" height="160" opacity="0.95" />
        <rect x="320" y="50" width="20" height="130" opacity="0.75" />
        <rect x="350" y="30" width="20" height="150" opacity="0.9" />
      </g>
    </svg>
  )
}

/* ─── 8. 电路板 ───────────────────────────────────── */
export function CircuitBoard({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.7"
      >
        <path d="M40 60 L120 60 L120 100 L200 100" />
        <path d="M40 140 L80 140 L80 180 L160 180 L160 220 L240 220" />
        <path d="M260 60 L320 60 L320 120 L360 120" />
        <path d="M200 100 L200 60 L260 60" />
        <path d="M240 220 L240 260 L320 260" />
        <path d="M360 120 L360 200 L300 200" />
      </g>
      <g fill="currentColor">
        <circle cx="40" cy="60" r="3" />
        <circle cx="200" cy="100" r="4" />
        <circle cx="40" cy="140" r="3" />
        <circle cx="240" cy="220" r="4" />
        <circle cx="320" cy="60" r="3" />
        <circle cx="360" cy="120" r="4" />
        <circle cx="320" cy="260" r="3" />
      </g>
      <g fill="none" stroke="currentColor" strokeWidth="1" opacity="0.5">
        <rect x="150" y="86" width="14" height="14" />
        <rect x="70" y="166" width="14" height="14" />
        <rect x="306" y="46" width="14" height="14" />
        <rect x="226" y="206" width="14" height="14" />
      </g>
    </svg>
  )
}

/* ─── 9. 同心弧（信号波） ─────────────────────────── */
export function ConcentricArcs({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1">
        <path d="M40 240 A 180 180 0 0 1 360 240" opacity="0.2" />
        <path d="M80 240 A 140 140 0 0 1 320 240" opacity="0.3" />
        <path d="M120 240 A 100 100 0 0 1 280 240" opacity="0.45" />
        <path d="M160 240 A 60 60 0 0 1 240 240" opacity="0.65" />
        <path d="M180 240 A 40 40 0 0 1 220 240" opacity="0.85" />
      </g>
      <g stroke="currentColor" strokeWidth="1" opacity="0.6">
        <line x1="40" y1="240" x2="40" y2="250" />
        <line x1="80" y1="240" x2="80" y2="246" />
        <line x1="120" y1="240" x2="120" y2="242" />
        <line x1="160" y1="240" x2="160" y2="244" />
        <line x1="200" y1="240" x2="200" y2="240" />
        <line x1="240" y1="240" x2="240" y2="244" />
        <line x1="280" y1="240" x2="280" y2="242" />
        <line x1="320" y1="240" x2="320" y2="246" />
        <line x1="360" y1="240" x2="360" y2="250" />
      </g>
      <circle cx="200" cy="240" r="5" fill="currentColor" opacity="0.9" />
    </svg>
  )
}

/* ─── 10. 粒子场 ─────────────────────────────────── */
export function ParticleField({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="currentColor">
        <circle cx="40" cy="40" r="2" opacity="0.6" />
        <circle cx="120" cy="80" r="1.5" opacity="0.4" />
        <circle cx="200" cy="40" r="2.5" opacity="0.8" />
        <circle cx="300" cy="60" r="1.5" opacity="0.5" />
        <circle cx="360" cy="100" r="2" opacity="0.7" />
        <circle cx="60" cy="160" r="1.5" opacity="0.4" />
        <circle cx="160" cy="200" r="2" opacity="0.6" />
        <circle cx="240" cy="160" r="2.5" opacity="0.9" />
        <circle cx="320" cy="200" r="1.5" opacity="0.5" />
        <circle cx="80" cy="260" r="2" opacity="0.7" />
        <circle cx="180" cy="280" r="1.5" opacity="0.5" />
        <circle cx="280" cy="260" r="2" opacity="0.65" />
        <circle cx="360" cy="280" r="2" opacity="0.8" />
      </g>
      <g stroke="currentColor" strokeWidth="0.4" opacity="0.2">
        <line x1="40" y1="40" x2="120" y2="80" />
        <line x1="120" y1="80" x2="200" y2="40" />
        <line x1="200" y1="40" x2="240" y2="160" />
        <line x1="160" y1="200" x2="240" y2="160" />
        <line x1="240" y1="160" x2="280" y2="260" />
        <line x1="280" y1="260" x2="360" y2="280" />
        <line x1="60" y1="160" x2="160" y2="200" />
      </g>
    </svg>
  )
}

/* ─── 11. 分层波纹（地平线/声波叠加） ─────────────── */
export function LayeredWaves({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.2">
        <path d="M0 150 Q100 130 200 150 T 400 150" opacity="0.5" />
        <path d="M0 160 Q100 145 200 160 T 400 160" opacity="0.4" />
        <path d="M0 170 Q100 160 200 170 T 400 170" opacity="0.3" />
        <path d="M0 180 Q100 175 200 180 T 400 180" opacity="0.2" />
      </g>
      <g fill="currentColor">
        <circle cx="80" cy="20" r="2" opacity="0.6" />
        <circle cx="160" cy="40" r="1.5" opacity="0.5" />
        <circle cx="280" cy="20" r="2" opacity="0.7" />
        <circle cx="340" cy="50" r="1.5" opacity="0.5" />
      </g>
    </svg>
  )
}

/* ─── 12. 网络节点（核心+外围） ──────────────────── */
export function NetworkNodes({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.45"
      >
        <line x1="200" y1="150" x2="60" y2="60" />
        <line x1="200" y1="150" x2="340" y2="60" />
        <line x1="200" y1="150" x2="60" y2="240" />
        <line x1="200" y1="150" x2="340" y2="240" />
        <line x1="200" y1="150" x2="200" y2="40" />
        <line x1="200" y1="150" x2="200" y2="260" />
        <line x1="60" y1="60" x2="200" y2="40" />
        <line x1="200" y1="40" x2="340" y2="60" />
        <line x1="60" y1="240" x2="200" y2="260" />
        <line x1="200" y1="260" x2="340" y2="240" />
      </g>
      <g fill="currentColor">
        <circle cx="200" cy="150" r="10" opacity="0.9" />
        <circle cx="200" cy="150" r="18" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
        <circle cx="60" cy="60" r="5" opacity="0.7" />
        <circle cx="340" cy="60" r="6" opacity="0.8" />
        <circle cx="60" cy="240" r="6" opacity="0.8" />
        <circle cx="340" cy="240" r="5" opacity="0.7" />
        <circle cx="200" cy="40" r="5" opacity="0.8" />
        <circle cx="200" cy="260" r="6" opacity="0.85" />
      </g>
    </svg>
  )
}

/* ─── 13. 等距堆叠（3D 抽象） ────────────────────── */
export function IsometricStack({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <linearGradient id="iso-1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.4" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <g stroke="currentColor" strokeWidth="1" fill="url(#iso-1)">
        {/* 顶层 */}
        <polygon points="200,80 280,120 200,160 120,120" opacity="0.6" />
        <polygon points="200,100 270,135 200,170 130,135" opacity="0.5" />
        <polygon points="200,120 260,150 200,180 140,150" opacity="0.4" />
        <polygon points="200,140 250,165 200,190 150,165" opacity="0.3" />
      </g>
      <g stroke="currentColor" strokeWidth="0.8" fill="none" opacity="0.5">
        <line x1="200" y1="80" x2="200" y2="180" />
        <line x1="120" y1="120" x2="120" y2="220" />
        <line x1="280" y1="120" x2="280" y2="220" />
        <line x1="200" y1="180" x2="200" y2="240" />
        <polygon points="200,180 280,220 200,260 120,220" opacity="0.4" />
      </g>
    </svg>
  )
}

/* ─── 14. 抽象建筑（天际线+蓝图） ────────────────── */
export function AbstractBuilding({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern id="b-grid" width="40" height="40" patternUnits="userSpacenUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.3" opacity="0.4" />
        </pattern>
      </defs>
      <rect width="400" height="300" fill="url(#b-grid)" />
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.7">
        <rect x="80" y="60" width="60" height="180" />
        <rect x="160" y="40" width="80" height="200" />
        <rect x="260" y="100" width="60" height="140" />
        <rect x="340" y="80" width="40" height="160" />
      </g>
      {/* 内部窗格 */}
      <g stroke="currentColor" strokeWidth="0.5" fill="none" opacity="0.4">
        <line x1="80" y1="100" x2="140" y2="100" />
        <line x1="80" y1="140" x2="140" y2="140" />
        <line x1="80" y1="180" x2="140" y2="180" />
        <line x1="80" y1="220" x2="140" y2="220" />
        <line x1="110" y1="60" x2="110" y2="240" />

        <line x1="160" y1="80" x2="240" y2="80" />
        <line x1="160" y1="120" x2="240" y2="120" />
        <line x1="160" y1="160" x2="240" y2="160" />
        <line x1="160" y1="200" x2="240" y2="200" />
        <line x1="200" y1="40" x2="200" y2="240" />

        <line x1="260" y1="140" x2="320" y2="140" />
        <line x1="260" y1="180" x2="320" y2="180" />
        <line x1="290" y1="100" x2="290" y2="240" />
      </g>
      {/* 高亮窗户 */}
      <g fill="currentColor" opacity="0.7">
        <rect x="83" y="103" width="4" height="6" />
        <rect x="93" y="143" width="4" height="6" />
        <rect x="113" y="183" width="4" height="6" />
        <rect x="163" y="83" width="6" height="6" />
        <rect x="203" y="163" width="6" height="6" />
        <rect x="223" y="203" width="6" height="6" />
        <rect x="263" y="143" width="4" height="6" />
        <rect x="293" y="183" width="4" height="6" />
      </g>
    </svg>
  )
}

/* ─── 15. 球体网格（地球抽象） ───────────────────── */
export function GlobeMesh({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 400"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" opacity="0.5">
        <circle cx="200" cy="200" r="140" strokeWidth="1" />
        <ellipse cx="200" cy="200" rx="140" ry="50" strokeWidth="0.8" />
        <ellipse cx="200" cy="200" rx="140" ry="100" strokeWidth="0.8" />
        <ellipse cx="200" cy="200" rx="50" ry="140" strokeWidth="0.8" />
        <ellipse cx="200" cy="200" rx="100" ry="140" strokeWidth="0.8" />
        <line x1="60" y1="200" x2="340" y2="200" strokeWidth="0.8" />
        <line x1="200" y1="60" x2="200" y2="340" strokeWidth="0.8" />
      </g>
      {/* 经纬线节点 */}
      <g fill="currentColor" opacity="0.7">
        <circle cx="60" cy="200" r="2" />
        <circle cx="340" cy="200" r="2" />
        <circle cx="200" cy="60" r="2" />
        <circle cx="200" cy="340" r="2" />
        <circle cx="118" cy="118" r="2" opacity="0.5" />
        <circle cx="282" cy="282" r="2" opacity="0.5" />
      </g>
    </svg>
  )
}

/* ─── 16. 散点矩阵（数据散点） ───────────────────── */
export function ScatterMatrix({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="currentColor">
        <circle cx="40" cy="80" r="3" opacity="0.5" />
        <circle cx="80" cy="120" r="4" opacity="0.7" />
        <circle cx="120" cy="100" r="2.5" opacity="0.4" />
        <circle cx="160" cy="160" r="5" opacity="0.85" />
        <circle cx="200" cy="140" r="3" opacity="0.5" />
        <circle cx="240" cy="180" r="4" opacity="0.7" />
        <circle cx="280" cy="160" r="3.5" opacity="0.6" />
        <circle cx="320" cy="200" r="4" opacity="0.7" />
        <circle cx="360" cy="180" r="2.5" opacity="0.45" />

        <circle cx="60" cy="180" r="2" opacity="0.4" />
        <circle cx="100" cy="200" r="3" opacity="0.55" />
        <circle cx="180" cy="220" r="3.5" opacity="0.65" />
        <circle cx="260" cy="240" r="4" opacity="0.7" />
        <circle cx="340" cy="220" r="3" opacity="0.55" />

        <circle cx="120" cy="240" r="2.5" opacity="0.5" />
        <circle cx="200" cy="260" r="3" opacity="0.55" />
        <circle cx="280" cy="280" r="2" opacity="0.4" />
      </g>
      {/* 趋势线 */}
      <path
        d="M40 80 Q200 140 360 180"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        opacity="0.6"
      />
    </svg>
  )
}

/* ─── 17. 几何拼贴（圆+方+三角） ─────────────────── */
export function GeometricCollage({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g stroke="currentColor" fill="none" strokeWidth="1" opacity="0.6">
        <circle cx="80" cy="80" r="40" />
        <rect x="180" y="40" width="80" height="80" />
        <polygon points="320,40 360,120 280,120" />
        <rect x="40" y="160" width="80" height="80" transform="rotate(15 80 200)" />
        <circle cx="240" cy="200" r="50" opacity="0.7" />
        <polygon points="360,260 380,200 320,200" opacity="0.5" />
      </g>
      <g fill="currentColor" opacity="0.4">
        <circle cx="80" cy="80" r="4" />
        <circle cx="240" cy="200" r="4" />
      </g>
    </svg>
  )
}

/* ─── 18. 抽象仪表盘（指针+刻度） ─────────────────── */
export function GaugeMeter({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 120"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6">
        <path d="M20 100 A 80 80 0 0 1 180 100" />
        <path d="M30 100 A 70 70 0 0 1 170 100" opacity="0.4" />
        {/* 刻度 */}
        {Array.from({ length: 11 }).map((_, i) => {
          const angle = -180 + (i * 180) / 10
          const rad = (angle * Math.PI) / 180
          const x1 = 100 + 70 * Math.cos(rad)
          const y1 = 100 + 70 * Math.sin(rad)
          const x2 = 100 + (i % 2 === 0 ? 60 : 65) * Math.cos(rad)
          const y2 = 100 + (i % 2 === 0 ? 60 : 65) * Math.sin(rad)
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} opacity="0.5" />
          )
        })}
      </g>
      {/* 指针 */}
      <line
        x1="100"
        y1="100"
        x2="148"
        y2="56"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="100" cy="100" r="5" fill="currentColor" />
    </svg>
  )
}

/* ─── 19. 抽象饼图 ───────────────────────────────── */
export function DonutChart({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="22">
        <circle cx="100" cy="100" r="60" opacity="0.9" strokeDasharray="100 280" strokeDashoffset="0" />
        <circle
          cx="100"
          cy="100"
          r="60"
          opacity="0.6"
          strokeDasharray="80 280"
          strokeDashoffset="-100"
        />
        <circle
          cx="100"
          cy="100"
          r="60"
          opacity="0.4"
          strokeDasharray="60 280"
          strokeDashoffset="-180"
        />
        <circle
          cx="100"
          cy="100"
          r="60"
          opacity="0.25"
          strokeDasharray="40 280"
          strokeDashoffset="-240"
        />
      </g>
      <circle cx="100" cy="100" r="36" fill="hsl(var(--background))" />
    </svg>
  )
}

/* ─── 20. 抽象梯田（层次堆叠） ───────────────────── */
export function TerracesLayered({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <defs>
        <linearGradient id="terrace-fade" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.7" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <g fill="url(#terrace-fade)" stroke="currentColor" strokeWidth="1">
        <polygon points="0,40 400,40 400,60 0,80" opacity="0.85" />
        <polygon points="0,90 400,70 400,95 400,110 0,130" opacity="0.7" />
        <polygon points="0,140 400,120 400,160 0,180" opacity="0.55" />
        <polygon points="0,200 400,170 400,200" opacity="0.4" />
      </g>
    </svg>
  )
}

/* ─── 21. 抽象相机快门 / 镜头 ────────────────────── */
export function LensAperture({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.7">
        <circle cx="100" cy="100" r="80" />
        <circle cx="100" cy="100" r="60" opacity="0.6" />
        <circle cx="100" cy="100" r="40" opacity="0.5" />
        <circle cx="100" cy="100" r="20" />
      </g>
      <g stroke="currentColor" strokeWidth="1" opacity="0.5">
        {Array.from({ length: 6 }).map((_, i) => {
          const angle = (i * 60 * Math.PI) / 180
          return (
            <line
              key={i}
              x1={100 + 60 * Math.cos(angle)}
              y1={100 + 60 * Math.sin(angle)}
              x2={100 + 20 * Math.cos(angle)}
              y2={100 + 20 * Math.sin(angle)}
            />
          )
        })}
      </g>
      <circle cx="100" cy="100" r="5" fill="currentColor" />
    </svg>
  )
}

/* ─── 22. 抽象窗口网格（多视窗） ─────────────────── */
export function WindowGrid({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.55">
        <rect x="20" y="20" width="120" height="80" />
        <rect x="160" y="20" width="100" height="80" />
        <rect x="280" y="20" width="100" height="120" />
        <rect x="20" y="120" width="120" height="100" />
        <rect x="160" y="120" width="100" height="80" />
        <rect x="20" y="240" width="240" height="40" />
        <rect x="280" y="160" width="100" height="120" />
      </g>
      {/* 选中高亮 */}
      <g stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.9">
        <rect x="160" y="20" width="100" height="80" />
      </g>
      {/* 内容示意 */}
      <g fill="currentColor" opacity="0.6">
        <line x1="30" y1="35" x2="100" y2="35" stroke="currentColor" strokeWidth="2" />
        <line x1="30" y1="50" x2="80" y2="50" stroke="currentColor" strokeWidth="1.5" />
        <line x1="30" y1="65" x2="120" y2="65" stroke="currentColor" strokeWidth="1.5" />

        <line x1="170" y1="35" x2="240" y2="35" stroke="currentColor" strokeWidth="2" />
        <line x1="170" y1="55" x2="220" y2="55" stroke="currentColor" strokeWidth="1.5" />

        <line x1="30" y1="140" x2="130" y2="140" stroke="currentColor" strokeWidth="2" />
        <line x1="30" y1="160" x2="110" y2="160" stroke="currentColor" strokeWidth="1.5" />
        <line x1="30" y1="180" x2="100" y2="180" stroke="currentColor" strokeWidth="1.5" />
        <line x1="30" y1="200" x2="120" y2="200" stroke="currentColor" strokeWidth="1.5" />
      </g>
      <g fill="currentColor" opacity="0.5">
        <rect x="290" y="180" width="40" height="40" rx="2" />
        <rect x="340" y="180" width="30" height="40" rx="2" opacity="0.7" />
        <rect x="290" y="230" width="40" height="30" rx="2" opacity="0.5" />
        <rect x="340" y="230" width="30" height="30" rx="2" opacity="0.3" />
      </g>
    </svg>
  )
}

/* ─── 23. KPI 数字卡（抽象仪表盘元素） ───────────── */
export function KpiBars({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 400 200"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="none"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6">
        <line x1="40" y1="180" x2="380" y2="180" />
        <line x1="40" y1="40" x2="40" y2="180" />
      </g>
      <g fill="currentColor">
        <rect x="60" y="120" width="40" height="60" opacity="0.4" />
        <rect x="120" y="80" width="40" height="100" opacity="0.55" />
        <rect x="180" y="100" width="40" height="80" opacity="0.5" />
        <rect x="240" y="40" width="40" height="140" opacity="0.85" />
        <rect x="300" y="60" width="40" height="120" opacity="0.7" />
      </g>
      <path
        d="M80 120 L140 80 L200 100 L260 40 L320 60"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        opacity="0.9"
      />
      <g fill="currentColor">
        <circle cx="80" cy="120" r="3" />
        <circle cx="140" cy="80" r="3" />
        <circle cx="200" cy="100" r="3" />
        <circle cx="260" cy="40" r="3" />
        <circle cx="320" cy="60" r="3" />
      </g>
    </svg>
  )
}

/* ─── 24. 抽象文档/页面层叠 ──────────────────────── */
export function DocumentStack({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 300 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.6">
        <rect x="60" y="40" width="160" height="200" rx="2" opacity="0.4" />
        <rect x="70" y="50" width="160" height="200" rx="2" opacity="0.6" />
        <rect x="80" y="60" width="160" height="200" rx="2" />
      </g>
      <g fill="currentColor" opacity="0.6">
        <line x1="100" y1="90" x2="220" y2="90" stroke="currentColor" strokeWidth="3" />
        <line x1="100" y1="110" x2="200" y2="110" stroke="currentColor" strokeWidth="1.5" />
        <line x1="100" y1="130" x2="210" y2="130" stroke="currentColor" strokeWidth="1.5" />
        <line x1="100" y1="150" x2="190" y2="150" stroke="currentColor" strokeWidth="1.5" />
        <line x1="100" y1="170" x2="200" y2="170" stroke="currentColor" strokeWidth="1.5" />
        <line x1="100" y1="200" x2="160" y2="200" stroke="currentColor" strokeWidth="2" />
        <line x1="100" y1="220" x2="200" y2="220" stroke="currentColor" strokeWidth="1.5" />
        <line x1="100" y1="240" x2="180" y2="240" stroke="currentColor" strokeWidth="1.5" />
      </g>
    </svg>
  )
}

/* ─── 25. 雷达扫描（旋转扫描线） ─────────────────── */
export function adarScan({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 300 300"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <g fill="none" stroke="currentColor" opacity="0.5">
        <circle cx="150" cy="150" r="120" strokeWidth="0.8" />
        <circle cx="150" cy="150" r="90" strokeWidth="0.8" />
        <circle cx="150" cy="150" r="60" strokeWidth="0.8" />
        <circle cx="150" cy="150" r="30" strokeWidth="0.8" />
        <line x1="150" y1="30" x2="150" y2="270" strokeWidth="0.6" />
        <line x1="30" y1="150" x2="270" y2="150" strokeWidth="0.6" />
      </g>
      <g fill="currentColor" opacity="0.85">
        <circle cx="100" cy="100" r="4" />
        <circle cx="200" cy="120" r="3" />
        <circle cx="180" cy="180" r="3" />
        <circle cx="120" cy="200" r="3" />
      </g>
      <circle cx="150" cy="150" r="5" fill="currentColor" opacity="0.9" />
    </svg>
  )
}

/* ─── 复合插图：产品全景（业务场景抽象） ─────────── */
export function ProductLandscape({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 800 400"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern id="land-grid" width="40" height="40" patternUnits="userSpacenUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.3" opacity="0.3" />
        </pattern>
        <linearGradient id="land-fade" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.15" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width="800" height="400" fill="url(#land-grid)" />

      {/* 山形数据曲线 */}
      <g fill="none" stroke="currentColor" opacity="0.7">
        <path d="M0 280 L100 220 L200 240 L300 160 L400 200 L500 100 L600 180 L700 120 L800 200" strokeWidth="1.4" />
        <path d="M0 320 L100 280 L200 300 L300 240 L400 260 L500 200 L600 240 L700 200 L800 240" strokeWidth="1" opacity="0.5" />
        <path d="M0 360 L100 340 L200 350 L300 320 L400 340 L500 300 L600 320 L700 280 L800 320" strokeWidth="0.8" opacity="0.35" />
      </g>

      {/* 数据节点 */}
      <g fill="currentColor">
        <circle cx="100" cy="220" r="4" opacity="0.8" />
        <circle cx="300" cy="160" r="5" opacity="0.9" />
        <circle cx="500" cy="100" r="6" />
        <circle cx="700" cy="120" r="5" opacity="0.9" />
      </g>

      {/* 顶部数据点标签 */}
      <g stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5">
        <line x1="500" y1="100" x2="500" y2="60" />
        <rect x="470" y="36" width="60" height="20" rx="2" />
        <circle cx="500" cy="46" r="2" fill="currentColor" />
        <line x1="476" y1="46" x2="494" y2="46" stroke="currentColor" strokeWidth="1.5" />
      </g>

      {/* 渐变覆盖 */}
      <rect width="800" height="400" fill="url(#land-fade)" />

      {/* 测量标尺 */}
      <g stroke="currentColor" strokeWidth="0.6" opacity="0.3">
        <line x1="40" y1="40" x2="40" y2="360" />
        <line x1="40" y1="40" x2="48" y2="40" />
        <line x1="40" y1="120" x2="48" y2="120" />
        <line x1="40" y1="200" x2="48" y2="200" />
        <line x1="40" y1="280" x2="48" y2="280" />
        <line x1="40" y1="360" x2="48" y2="360" />
      </g>
    </svg>
  )
}

/* ─── BackgroundPattern：通用Background纹理 ──────────────── */
export function BackgroundPattern({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern
          id="bg-dots"
          width="32"
          height="32"
          patternUnits="userSpacenUse"
        >
          <circle cx="2" cy="2" r="1" fill="currentColor" opacity="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#bg-dots)" />
    </svg>
  )
}

/* ─── BackgroundGrid：网格Background ────────────────────── */
export function BackgroundGrid({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-full w-full', className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      {...props}
    >
      <defs>
        <pattern
          id="bg-grid"
          width="48"
          height="48"
          patternUnits="userSpacenUse"
        >
          <path
            d="M 48 0 L 0 0 0 48"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            opacity="0.5"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#bg-grid)" />
    </svg>
  )
}
