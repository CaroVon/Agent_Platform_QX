/**
 * DesignStudioPage —— Design Studio v2
 *
 * 任务级图片资产库（替代旧的文本冗余展示）：
 *   - 某任务的全部生图按「设计思路（文字）+ 图片」结构化存储
 *   - 文字可编辑并重新生图；组件化产品支持 组件文字+组件图 … 组合总图
 *   - 图片可单张下载 / 全部打包下载
 */

import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import { DesignStudioLibrary } from '@/components/design/DesignStudioLibrary'
import { SourceIndex } from '@/components/product/SourceIndex'
import type { StudioProduct } from '@/types/studio'

export function DesignStudioPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · 设计"
        title="Design Studio"
        description="任务级图片资产库 —— 每张生图都附带可编辑的设计思路，改文字即可重新生图；组件化产品按「组件文字+组件图 + 组合总图」组织。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无设计资产"
        emptyDescription="运行 Product Workspace 流水线后，生成的图片与设计思路会自动归档到这里；也可以直接创建组合设计开始生图。"
        renderDetail={(product: StudioProduct) => (
          <>
            <SourceIndex sources={product.design?.sources} />
            <DesignStudioLibrary product={product} />
          </>
        )}
      />
    </div>
  )
}
