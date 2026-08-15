/**
 * ExportMenu —— 演示导出多选项（HTML / PDF / PPT）
 *
 * 复用既有导出管线（export-html / export-pdf / export-pptx），
 * PPT = 可编辑 .pptx（PptxGenJS），与预览同一渲染源。
 */

import { useState } from 'react'
import { ChevronDown, FileDown, Globe, Loader2, Presentation } from 'lucide-react'
import { Button } from '@/components/common/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/common/popover'
import { productApi } from '@/lib/api'
import { cn } from '@/lib/utils'

type ExportKind = 'html' | 'pdf' | 'ppt'

const FORMATS: Array<{ id: ExportKind; label: string; hint: string; icon: typeof Globe }> = [
  { id: 'html', label: 'HTML', hint: '交互式演示快照', icon: Globe },
  { id: 'pdf', label: 'PDF', hint: '打印级版式', icon: FileDown },
  { id: 'ppt', label: 'PPT', hint: '可编辑 .pptx', icon: Presentation },
]

export function ExportMenu({
  productId,
  onError,
  className,
}: {
  productId: string
  onError?: (message: string) => void
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const [exporting, setExporting] = useState<ExportKind | null>(null)

  const run = async (kind: ExportKind) => {
    if (!productId || exporting) return
    setExporting(kind)
    try {
      const result =
        kind === 'html'
          ? await productApi.exportHtml(productId)
          : kind === 'pdf'
            ? await productApi.exportPdf(productId)
            : await productApi.exportPptx(productId)
      window.open(result.pdf_url, '_blank')
      setOpen(false)
    } catch (err) {
      onError?.(err instanceof Error ? err.message : '导出失败')
    } finally {
      setExporting(null)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={Boolean(exporting)}
          className={cn('gap-1.5', className)}
        >
          {exporting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <FileDown className="h-3.5 w-3.5" />
          )}
          导出
          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-52 p-1.5">
        {FORMATS.map((f) => (
          <button
            key={f.id}
            type="button"
            disabled={Boolean(exporting)}
            onClick={() => run(f.id)}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-accent disabled:opacity-50"
          >
            {exporting === f.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <f.icon className="h-3.5 w-3.5" />
            )}
            <span className="flex-1">
              <span className="block text-xs font-medium">{f.label}</span>
              <span className="block text-[10px] text-muted-foreground">{f.hint}</span>
            </span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
