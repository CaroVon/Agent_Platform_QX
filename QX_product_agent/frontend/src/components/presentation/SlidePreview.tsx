/**
 * presentation/SlidePreview —— 幻灯片缩略图导航
 * 点击缩略图跳转到对应页（供 Presentation 模块快速浏览）
 */

import { cn } from '@/lib/utils'
import type { PresentationDSL } from '@/types/presentation'

export function SlidePreview({
  presentation,
  svgPreviews = [],
  currentIndex,
  onSelect,
}: {
  presentation?: PresentationDSL
  svgPreviews?: string[]
  currentIndex: number
  onSelect: (index: number) => void
}) {
  const pages = presentation?.pages ?? []
  const previewCount = svgPreviews.length
  if (previewCount === 0) {
    return (
      <div className="rounded-lg border border-dashed px-4 py-6 text-center text-xs text-muted-foreground">
        后端 PPT 缩略图尚未生成
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 gap-3 sm:grid-cols-5">
      {svgPreviews.map((src, i) => (
        <button
          key={src}
          type="button"
          onClick={() => onSelect(i)}
          title={`跳转到第 ${i + 1} 页${pages[i]?.title ? `：${pages[i].title}` : ''}`}
          className={cn(
            'group relative aspect-video overflow-hidden rounded-lg border bg-card transition-all duration-150',
            i === currentIndex
              ? 'border-[#24415E]/60 ring-2 ring-[#24415E]/20'
              : 'border-border opacity-70 hover:opacity-100',
          )}
        >
          <img
            src={src}
            alt={`第 ${i + 1} 页后端 PPT 缩略图`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
          <span className="absolute bottom-1.5 right-2 text-[10px] font-medium text-muted-foreground">
            {i + 1}
          </span>
        </button>
      ))}
    </div>
  )
}
