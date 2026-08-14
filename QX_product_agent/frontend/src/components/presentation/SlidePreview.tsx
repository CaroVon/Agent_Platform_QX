/**
 * presentation/SlidePreview —— 幻灯片缩略图导航
 * 点击缩略图跳转到对应页（供 Presentation 模块快速浏览）
 */

import { cn } from '@/lib/utils'
import type { PresentationDSL, PresentationPage } from '@/types/presentation'
import { PageFrame } from '@/components/presentation/layouts'

export function SlidePreview({
  presentation,
  currentIndex,
  onSelect,
}: {
  presentation: PresentationDSL
  currentIndex: number
  onSelect: (index: number) => void
}) {
  const pages = presentation.pages ?? []
  if (pages.length === 0) return null

  return (
    <div className="grid grid-cols-4 gap-3 sm:grid-cols-5">
      {pages.map((page: PresentationPage, i: number) => (
        <button
          key={page.id}
          type="button"
          onClick={() => onSelect(i)}
          title={`跳转到第 ${i + 1} 页：${page.title}`}
          className={cn(
            'group relative aspect-video overflow-hidden rounded-lg border bg-card transition-all duration-150',
            i === currentIndex
              ? 'border-[#24415E]/60 ring-2 ring-[#24415E]/20'
              : 'border-border opacity-70 hover:opacity-100',
          )}
        >
          {/* 缩略画布：1280×720 设计稿按比例缩小 */}
          <div className="h-full w-full origin-top-left" style={{ transform: 'scale(0.14)', width: '1280px', height: '720px' }}>
            <div className="h-[720px] w-[1280px]">
              <PageFrame page={page} index={i} total={pages.length} exportMode />
            </div>
          </div>
          <span className="absolute bottom-1.5 right-2 text-[10px] font-medium text-muted-foreground">
            {i + 1}
          </span>
        </button>
      ))}
    </div>
  )
}
