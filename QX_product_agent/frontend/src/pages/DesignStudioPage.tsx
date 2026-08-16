/**
 * DesignStudioPage —— 产品设计资产
 * 用户旅程 / 页面结构 / UI 组件规格（UXDesign 结构化展示）
 */

import { useEffect, useState } from 'react'
import { ArrowRight, ImageIcon, LayoutGrid, MousePointerClick, Route } from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { productApi } from '@/lib/api'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import type { StudioProduct } from '@/types/studio'

export function DesignStudioPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · 设计"
        title="Design Studio"
        description="用户旅程、信息架构与 UI 结构规格 —— 结构化设计资产，视觉实现由组件库承接。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无设计资产"
        emptyDescription="运行 Product Workspace 流水线后，UX 设计规格会自动归档到这里。"
        renderDetail={(product: StudioProduct) => {
          const design = product.design
          // ── 图片资产库（阶段 C：MiniMax 生图 / 本地上传共用） ──
          const [assets, setAssets] = useState<Array<{ name: string; url: string; size: number }>>([])
          useEffect(() => {
            let cancelled = false
            productApi.listAssets(product.product_id).then((data) => {
              if (!cancelled) setAssets(data.assets ?? [])
            }).catch(() => {})
            return () => { cancelled = true }
          }, [product.product_id])
          return (
            <>
              {assets.length > 0 && (
                <div className="mb-6 rounded-xl border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <ImageIcon className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">图片资产库（{assets.length}）</h3>
                  </div>
                  <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                    {assets.map((img) => (
                      <div key={img.name} className="group overflow-hidden rounded-lg border">
                        <img src={img.url} alt={img.name} loading="lazy"
                          className="aspect-square w-full object-cover" />
                        <div className="truncate border-t bg-background/60 px-2 py-1 text-[10px] text-muted-foreground">
                          {img.name}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {!design && (
                <p className="text-sm text-muted-foreground">该产品暂无设计资产。</p>
              )}
              {design && (<>
              {/* 用户旅程 */}
              {design.user_flow.length > 0 && (
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <Route className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">用户旅程</h3>
                  </div>
                  <ol className="flex flex-wrap items-center gap-2">
                    {design.user_flow.map((step, i) => (
                      <li key={step.step} className="flex items-center gap-2">
                        <div className="rounded-lg border bg-background px-3 py-2">
                          <div className="text-xs font-medium">{step.step}</div>
                          {step.description && (
                            <div className="mt-0.5 max-w-[180px] text-[10px] text-muted-foreground">
                              {step.description}
                            </div>
                          )}
                        </div>
                        {i < design.user_flow.length - 1 && (
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/50" />
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* 页面结构 */}
              {design.pages.length > 0 && (
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <LayoutGrid className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">页面结构</h3>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {design.pages.map((page) => (
                      <div key={page.name} className="rounded-lg border bg-background p-4">
                        <div className="text-sm font-medium">{page.name}</div>
                        {page.purpose && (
                          <div className="mt-1 text-xs text-muted-foreground">{page.purpose}</div>
                        )}
                        {page.key_elements.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {page.key_elements.map((el) => (
                              <span
                                key={el}
                                className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground"
                              >
                                {el}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 组件规格 */}
              {design.components.length > 0 && (
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <MousePointerClick className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">UI 组件规格</h3>
                  </div>
                  <ul className="divide-y">
                    {design.components.map((comp) => (
                      <li key={comp.name} className="flex items-center gap-3 py-2.5">
                        <span className="w-40 shrink-0 text-sm font-medium">{comp.name}</span>
                        <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {comp.kind || 'component'}
                        </span>
                        {comp.description && (
                          <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                            {comp.description}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              </>)}
            </>
          )
        }}
      />
    </div>
  )
}
