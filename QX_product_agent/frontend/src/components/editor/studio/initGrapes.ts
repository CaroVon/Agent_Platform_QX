/**
 * editor/studio/initGrapes —— GrapesJS 编辑器初始化（16:9 演示页编辑）
 */

import grapesjs from 'grapesjs'
import type { Editor } from 'grapesjs'
import 'grapesjs/dist/css/grapes.min.css'
import { registerBlocks } from './blocks'
import { pageToHtml } from './dslBridge'
import type { PresentationPage } from '@/types/presentation'

const PAGE_STYLES = `
  body { margin: 0; font-family: "Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif; }
  .editor-page { width: 1280px; min-height: 720px; box-sizing: border-box; padding: 48px 56px;
    background: linear-gradient(160deg,#f8fafc 0%,#eef2ff 100%); }
  .editor-page-header { border-bottom: 2px solid #4f46e5; padding-bottom: 16px; margin-bottom: 28px; }
  .editor-page-header h2 { margin: 0; font-size: 26px; color: #0f172a; }
  .editor-page-header p { margin: 6px 0 0; color: #64748b; font-size: 14px; }
  .editor-page-insight { display: inline-block; margin-top: 12px; padding: 6px 12px;
    background: #4f46e510; color: #4f46e5; border-radius: 8px; font-size: 14px; }
  .editor-page-body { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
  .dsl-text { padding: 8px 0; }
  .dsl-text-title { font-size: 15px; font-weight: 600; color: #334155; margin-bottom: 6px; }
  .dsl-text-body { font-size: 14px; line-height: 1.7; color: #475569; min-height: 24px; outline: none; }
  .dsl-metric { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 20px 16px; text-align: center; }
  .dsl-metric-value { font-size: 30px; font-weight: 700; color: #4f46e5; }
  .dsl-metric-label { font-size: 12px; color: #64748b; margin-top: 6px; }
  .dsl-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px; }
  .dsl-card-title { font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 8px; }
  .dsl-card-desc { font-size: 13px; line-height: 1.7; color: #64748b; min-height: 20px; outline: none; }
  .dsl-quote { border-left: 4px solid #4f46e5; background: #ffffffcc; border-radius: 10px;
    padding: 16px 20px; }
  .dsl-quote-body { font-size: 16px; font-weight: 500; color: #334155; outline: none; }
  .dsl-image { display: flex; align-items: center; justify-content: center; min-height: 140px;
    border: 2px dashed #c7d2fe; border-radius: 14px; background: #eef2ff55; overflow: hidden; }
  .dsl-image img { max-width: 100%; max-height: 260px; display: block; }
  .dsl-image-placeholder { color: #6366f1; font-size: 13px; }
  .dsl-table { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; }
  .dsl-table th { background: #4f46e5; color: #fff; padding: 10px 12px; text-align: left; }
  .dsl-table td { border-bottom: 1px solid #e2e8f0; padding: 10px 12px; color: #334155; outline: none; }
  .dsl-table th { outline: none; }
  .dsl-timeline { display: flex; gap: 14px; }
  .dsl-timeline-item { flex: 1; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; }
  .dsl-timeline-name { font-size: 14px; font-weight: 600; color: #1e293b; outline: none; }
  .dsl-timeline-milestones { font-size: 12px; color: #64748b; margin-top: 6px; outline: none; }
  .dsl-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 160px; border: 2px dashed #c7d2fe; border-radius: 14px; background: #eef2ff33; }
  .dsl-placeholder-icon { font-size: 32px; }
  .dsl-placeholder-label { font-size: 14px; font-weight: 600; color: #4f46e5; margin-top: 8px; }
  .dsl-placeholder-hint { font-size: 11px; color: #94a3b8; margin-top: 4px; }
`

export function initGrapes(
  container: HTMLElement,
  page: PresentationPage,
): Editor {
  const editor = grapesjs.init({
    container,
    height: '100%',
    fromElement: false,
    storageManager: false as unknown as never,
    // 图层管理器挂载到自定义容器
    layerManager: {
      appendTo: '.editor-layers',
    },
    // 块面板挂载到自定义容器
    blockManager: {
      appendTo: '.editor-blocks',
    },
    // 样式管理器（宽高/圆角/透明度/滤镜）
    styleManager: {
      appendTo: '.editor-styles',
      sectors: [
        {
          name: '尺寸',
          open: true,
          properties: [
            'width', 'height', 'max-width', 'min-height',
            { property: 'border-radius', type: 'slider', defaults: '0', units: ['px', '%'] },
            'padding', 'margin',
          ],
        },
        {
          name: '效果',
          open: false,
          properties: [
            'opacity',
            { property: 'filter', type: 'select', defaults: 'none',
              options: [
                { id: 'none', label: '无滤镜' },
                { id: 'grayscale(100%)', label: '黑白' },
                { id: 'sepia(60%)', label: '复古' },
                { id: 'brightness(1.1)', label: '提亮' },
                { id: 'contrast(1.15)', label: '增强对比' },
              ] },
            'box-shadow', 'border', 'background-color',
          ],
        },
      ],
    },
    // 设备：16:9 演示页
    deviceManager: {
      devices: [
        { id: 'desktop', name: '演示页', width: '1280px' },
      ],
    },
    // 富文本工具栏（文本编辑，默认配置）
    // 关闭不需要的面板
    selectorManager: { appendTo: '.editor-styles' },
    traitManager: { appendTo: '.editor-traits' },
    canvas: {
      styles: [PAGE_STYLES],
    },
    assetManager: {
      assets: [],
      upload: false,
      embedAsBase64: false,
    },
    plugins: [],
  })

  // 注册自定义块与类型
  registerBlocks(editor)

  // 加载页面
  editor.setComponents(pageToHtml(page))
  editor.setDevice('desktop')
  // 调试挂载（生产无副作用）
  ;(window as unknown as Record<string, unknown>).__grapes = editor

  // 拖入外部图片 URL（右侧素材栏 → 画布）
  editor.on('component:create', () => {
    /* 预留 */
  })

  return editor
}
