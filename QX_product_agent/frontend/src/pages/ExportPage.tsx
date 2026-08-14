/**
 * ExportPage —— 导出专用路由（无 UI 外壳）
 *
 * Playwright 打开 http://host/export/{productId} 并打印 PDF：
 * 与 Web 预览共用 PresentationViewer（单一渲染源，WYSIWYG）。
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Loader2, AlertCircle } from 'lucide-react'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { PresentationViewer } from '@/components/presentation/PresentationViewer'
import type { PresentationDSL } from '@/types/presentation'

export function ExportPage() {
  const { productId } = useParams<{ productId: string }>()
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [presentation, setPresentation] = useState<PresentationDSL | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!productId) {
      setState('error')
      setError('缺少 productId')
      return
    }
    let cancelled = false
    const load = async () => {
      try {
        const product: StudioProduct = await productApi.get(productId)
        if (cancelled) return
        const raw = product.presentation as unknown as Record<string, unknown> | null
        if (raw && Array.isArray(raw.pages)) {
          setPresentation(raw as unknown as PresentationDSL)
          setState('ready')
        } else {
          setState('error')
          setError('该产品使用旧版演示格式，请用新版流水线重新生成')
        }
      } catch (err) {
        if (!cancelled) {
          setState('error')
          setError(err instanceof Error ? err.message : '加载失败')
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [productId])

  if (state === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 正在准备导出…
      </div>
    )
  }
  if (state === 'error' || !presentation) {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-red-500">
        <AlertCircle className="h-5 w-5" /> {error}
      </div>
    )
  }
  return <PresentationViewer presentation={presentation} exportMode />
}
