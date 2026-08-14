/**
 * ============================================================
 * CanvasSlideEditor —— React-Konva 幻灯片编辑器 (v0.4 完善版)
 *
 * 新增:
 * - Transformer 选中框 + 拖拽缩放
 * - 双击文字编辑（Html 悬浮层）
 * - 表格单元格双击编辑 + 行列控制面板
 * - Circle / Line 图形渲染
 * - 颜色拾取器 / 排版按钮 / 图层排序 / Undo-Redo
 * - Ctrl+C/V 复制粘贴 + Delete 删除
 * ============================================================
 */

import {
  useRef,
  useCallback,
  useState,
  useEffect,
  useMemo,
  Fragment,
} from 'react'
import {
  Stage,
  Layer,
  Rect,
  Text,
  Image as KonvaImage,
  Group,
  Transformer,
  Circle,
  Line,
} from 'react-konva'
import { Html } from 'react-konva-utils'
import Konva from 'konva'
import useImage from 'use-image'
import {
  ChevronUp,
  ChevronDown,
  Plus,
  Trash2,
  Image as ImageIcon,
  Type,
  CircleDot,
  Minus,
  Table2,
  Square,
  Undo2,
  Redo2,
  ArrowUpToLine,
  ArrowDownToLine,
  ChevronsUp,
  ChevronsDown,
  RefreshCw,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Copy,
  ClipboardPaste,
  Crop,
  Check,
  X,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { cn } from '@/lib/utils'
import { projectsApi } from '@/lib/api'
import { CANVAS_WIDTH, CANVAS_HEIGHT, createBlankSlide } from '@/lib/dataTransform'
import type { KonvaSlide } from '@/lib/dataTransform'
import { useCanvasStore } from '@/store/useCanvasStore'
import type { CanvasElement } from '@/store/useCanvasStore'

// ══════════════════════════════════════════════════════════════
// Props
// ══════════════════════════════════════════════════════════════

interface CanvasSlideEditorProps {
  slides: KonvaSlide[]
  activeIndex: number
  onActiveIndexChange: (index: number) => void
  onSlidesChange: (slides: KonvaSlide[]) => void
  canvasRef: React.MutableRefObject<KonvaCanvasInstance | null>
  readOnly?: boolean
  showToolbar?: boolean
  projectId?: string
}

export interface KonvaCanvasInstance {
  stageRef: React.RefObject<any>
  capturePage: (
    elements: CanvasElement[],
    width?: number,
    height?: number,
    pixelRatio?: number,
  ) => Promise<string>
  editorApi?: {
    addText: (text: string, opts?: Record<string, unknown>) => void
    addImage: (url: string, opts?: Record<string, unknown>) => void
  }
}

// ══════════════════════════════════════════════════════════════
// 可重用图片组件
// ══════════════════════════════════════════════════════════════

const RenderImage = ({
  src,
  id,
  x,
  y,
  width,
  height,
  draggable,
  onDragEnd,
  onTransformEnd,
  onClick,
  onTap,
  clipX,
  clipY,
  clipWidth,
  clipHeight,
}: {
  src: string
  id?: string
  x: number; y: number; width: number; height: number
  draggable?: boolean
  onDragEnd?: (e: any) => void
  onTransformEnd?: (e: any) => void
  onClick?: (e: any) => void
  onTap?: (e: any) => void
  clipX?: number; clipY?: number; clipWidth?: number; clipHeight?: number
}) => {
  const [image] = useImage(src, 'anonymous')
  if (!image) return null

  // 核心：计算等比缩放 (Contain 模式)，防止 Konva 默认拉伸
  const imgScale = Math.min(width / image.width, height / image.height)
  const drawW = image.width * imgScale
  const drawH = image.height * imgScale

  // 居中放置在 bounding box 内
  const drawX = x + (width - drawW) / 2
  const drawY = y + (height - drawH) / 2

  return (
    <KonvaImage
      image={image}
      id={id}
      name="element"
      x={drawX} y={drawY} width={drawW} height={drawH}
      draggable={draggable}
      onDragEnd={onDragEnd}
      onTransformEnd={onTransformEnd}
      onClick={onClick}
      onTap={onTap}
      clipFunc={
        clipWidth && clipWidth > 0
          ? (ctx: any) => {
              ctx.beginPath()
              // clipX/Y 存储的是相对于 bounding box (x,y) 的坐标，
              // 但 KonvaImage 实际渲染在居中位置 (drawX,drawY)，
              // 需要将裁剪区域转换到 KonvaImage 的局部坐标系
              const offsetX = drawX - x
              const offsetY = drawY - y
              ctx.rect(
                (clipX ?? 0) - offsetX,
                (clipY ?? 0) - offsetY,
                clipWidth,
                clipHeight ?? drawH,
              )
              ctx.closePath()
            }
          : undefined
      }
    />
  )
}

// ══════════════════════════════════════════════════════════════
// 图片占位框组件（虚线框 + 提示文字，双击插入图片）
// ══════════════════════════════════════════════════════════════

const RenderPlaceholder = ({
  el,
  draggable,
  onDragEnd,
  onTransformEnd,
  onClick,
  onTap,
  onDblClick,
}: {
  el: CanvasElement
  draggable?: boolean
  onDragEnd?: (e: any) => void
  onTransformEnd?: (e: any) => void
  onClick?: (e: any) => void
  onTap?: (e: any) => void
  onDblClick?: () => void
}) => {
  return (
    <Group
      id={el.id}
      name="element"
      x={el.x} y={el.y}
      draggable={draggable}
      onDragEnd={onDragEnd}
      onTransformEnd={onTransformEnd}
      onClick={onClick}
      onTap={onTap}
      onDblClick={onDblClick}
    >
      <Rect
        width={el.width} height={el.height}
        fill="#f8fafc"
        stroke="#94a3b8"
        strokeWidth={2}
        dash={[10, 6]}
        cornerRadius={6}
      />
      <Text
        width={el.width} height={el.height}
        text={el.text || '🖼  双击插入图片'}
        fontSize={16}
        fill="#94a3b8"
        align="center"
        verticalAlign="middle"
        lineHeight={1.4}
      />
    </Group>
  )
}

// ══════════════════════════════════════════════════════════════
// 可重用表格组件（含双击编辑单元格支持）
// ══════════════════════════════════════════════════════════════

const TBL_FONT = 14
const TBL_PAD = 5

const RenderTable = ({
  el,
  draggable,
  onDragEnd,
  onTransformEnd,
  onClick,
  editingCell,
  onCellDblClick,
  onCellBlur,
}: {
  el: CanvasElement
  draggable?: boolean
  onDragEnd?: (e: any) => void
  onTransformEnd?: (e: any) => void
  onClick?: (e: any) => void
  editingCell: { r: number; c: number } | null
  onCellDblClick: (r: number, c: number) => void
  onCellBlur: (text: string) => void
}) => {
  const data = el.tableData || [['']]
  const rowCount = data.length
  const colCount = data[0]?.length || 1
  const cellW = el.width / colCount
  const cellH = el.height / rowCount

  // 表格样式（带默认兜底）
  const headerFill = el.headerFill || '#2d7cf6'
  const headerColor = el.headerColor || '#ffffff'
  const rowAltFill = el.rowAltFill || '#f8fafc'
  const borderColor = el.tableBorderColor || '#e2e8f0'

  return (
    <Group
      id={el.id}
      name="element"
      x={el.x} y={el.y}
      draggable={draggable}
      onDragEnd={onDragEnd}
      onTransformEnd={onTransformEnd}
      onClick={onClick}
    >
      {data.map((row, rIdx) =>
        row.map((cellText, cIdx) => {
          const isHeader = rIdx === 0
          const cellFill = isHeader
            ? headerFill
            : rIdx % 2 === 0
              ? rowAltFill
              : '#ffffff'
          const textFill = isHeader ? headerColor : '#334155'
          return (
            <Group key={`${rIdx}-${cIdx}`} x={cIdx * cellW} y={rIdx * cellH}>
              <Rect
                width={cellW} height={cellH}
                stroke={borderColor} strokeWidth={1} fill={cellFill}
              />
              {/* 编辑中的单元格显示 HTML input */}
              {editingCell?.r === rIdx && editingCell?.c === cIdx ? (
                <Html
                  groupProps={{ x: 0, y: 0 }}
                  divProps={{ style: { pointerEvents: 'auto' } }}
                >
                  <input
                    autoFocus
                    defaultValue={cellText}
                    style={{
                      width: cellW - 6, height: cellH - 4,
                      border: '2px solid #6366f1', background: '#fff',
                      textAlign: 'center', fontSize: TBL_FONT,
                      fontFamily: 'sans-serif', color: '#334155',
                      padding: 0, margin: 0, outline: 'none',
                    }}
                    onBlur={(e) => onCellBlur(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') onCellBlur(cellText)
                      if (e.key === 'Enter') onCellBlur(e.currentTarget.value)
                    }}
                  />
                </Html>
              ) : (
                <Text
                  text={cellText} width={cellW} height={cellH}
                  padding={TBL_PAD} fontSize={TBL_FONT} fill={textFill}
                  fontStyle={isHeader ? 'bold' : 'normal'}
                  align="center" verticalAlign="middle"
                  lineHeight={1.4}
                  onDblClick={() => onCellDblClick(rIdx, cIdx)}
                />
              )}
            </Group>
          )
        }),
      )}
    </Group>
  )
}

// ══════════════════════════════════════════════════════════════
// 表格行列控制面板（悬浮在选中表格上方）
// ══════════════════════════════════════════════════════════════

function TableControlPanel({
  el,
  activePage,
  syncStoreToInternal,
}: {
  el: CanvasElement
  activePage: number
  syncStoreToInternal: () => void
}) {
  const addRow = () => {
    if (!el.tableData) return
    const cols = el.tableData[0]?.length || 1
    const newRow = Array(cols).fill('')
    const newData = [...el.tableData, newRow]
    const newH = el.height + el.height / el.tableData.length
    useCanvasStore.getState().updateElement(activePage, el.id, {
      tableData: newData,
      height: newH,
    })
    syncStoreToInternal()
  }
  const addCol = () => {
    if (!el.tableData) return
    const newData = el.tableData.map((row) => [...row, ''])
    const newW = el.width + el.width / el.tableData[0].length
    useCanvasStore.getState().updateElement(activePage, el.id, {
      tableData: newData,
      width: newW,
    })
    syncStoreToInternal()
  }
  const delRow = () => {
    if (!el.tableData || el.tableData.length <= 1) return
    const newData = el.tableData.slice(0, -1)
    const newH = el.height - el.height / el.tableData.length
    useCanvasStore.getState().updateElement(activePage, el.id, {
      tableData: newData,
      height: newH,
    })
    syncStoreToInternal()
  }
  const delCol = () => {
    if (!el.tableData || el.tableData[0]?.length <= 1) return
    const newData = el.tableData.map((row) => row.slice(0, -1))
    const newW = el.width - el.width / el.tableData[0].length
    useCanvasStore.getState().updateElement(activePage, el.id, {
      tableData: newData,
      width: newW,
    })
    syncStoreToInternal()
  }

  const btnCls =
    'rounded bg-white border border-border px-1.5 py-0.5 text-[10px] hover:bg-muted cursor-pointer'

  return (
    <Html
      groupProps={{ x: el.x, y: el.y - 32 }}
      divProps={{ style: { pointerEvents: 'auto' } }}
    >
      <div className="flex gap-1 whitespace-nowrap">
        <button className={btnCls} onClick={addRow}>+行</button>
        <button className={btnCls} onClick={addCol}>+列</button>
        <button className={btnCls} onClick={delRow}>-行</button>
        <button className={btnCls} onClick={delCol}>-列</button>
      </div>
    </Html>
  )
}

// ══════════════════════════════════════════════════════════════
// 主组件
// ══════════════════════════════════════════════════════════════

export function CanvasSlideEditor({
  slides: externalSlides,
  activeIndex,
  onActiveIndexChange,
  onSlidesChange,
  canvasRef,
  readOnly = false,
  showToolbar = true,
  projectId,
}: CanvasSlideEditorProps) {
  // ─── Refs ──────────────────────────────────────────────────
  const stageRef = useRef<any>(null)
  const transformerRef = useRef<any>(null)
  const clipTransformerRef = useRef<any>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  // ─── 内部 slides ──────────────────────────────────────────
  const [slidesInternal, setSlidesInternal] = useState<KonvaSlide[]>(externalSlides)
  const isInternalChange = useRef(false)

  // ─── 表格编辑状态 ─────────────────────────────────────────
  const [tableEditCell, setTableEditCell] = useState<{ elId: string; r: number; c: number } | null>(null)

  // ─── 裁剪区域状态 ─────────────────────────────────────────
  const [clipRegion, setClipRegion] = useState({ x: 0, y: 0, width: 0, height: 0 })
  const clipRegionRef = useRef(clipRegion)
  clipRegionRef.current = clipRegion
  // 🆕 图片在裁剪模式下的 contain-fit 渲染边界（drawX, drawY, drawW, drawH）
  const [imageRenderBounds, setImageRenderBounds] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  // ─── 从 Zustand 读取状态 ──────────────────────────────────
  // 使用 activeIndex prop 而非 s.activePage，避免切换幻灯片时的渲染延迟
  const storeSlides = useCanvasStore((s) => s.slides)
  const storeElements = storeSlides[activeIndex] || []
  const selectedElementIds = useCanvasStore((s) => s.selectedElementIds)
  const editingElementId = useCanvasStore((s) => s.editingElementId)
  const activePage = useCanvasStore((s) => s.activePage)
  const clipModeElementId = useCanvasStore((s) => s.clipModeElementId)
  const copiedSlide = useCanvasStore((s) => s.copiedSlide)

  const displayElements =
    storeElements.length > 0 ? storeElements : slidesInternal[activeIndex]?.elements || []

  // ─── 同步外部 slides → 内部 ────────────────────────────────
  useEffect(() => {
    if (isInternalChange.current) {
      isInternalChange.current = false
      return
    }
    setSlidesInternal(externalSlides)
  }, [externalSlides])

  // ─── 同步内部 slides → 外部 + Zustand ─────────────────────
  const syncStoreToInternal = useCallback(() => {
    isInternalChange.current = true
    const storeSlides = useCanvasStore.getState().slides
    setSlidesInternal((prev) => {
      const next = [...prev]
      for (const [pageStr, elements] of Object.entries(storeSlides)) {
        const page = Number(pageStr)
        if (next[page]) next[page] = { ...next[page], elements }
      }
      return next
    })
  }, [])

  useEffect(() => {
    onSlidesChange(slidesInternal)
    const currentSlide = slidesInternal[activeIndex]
    if (currentSlide) {
      const storeSlides = useCanvasStore.getState().slides
      storeSlides[activeIndex] = currentSlide.elements
      useCanvasStore.getState().setSlides({ ...storeSlides })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slidesInternal])

  // ─── 切换页面时更新 Zustand activePage ────────────────────
  useEffect(() => {
    useCanvasStore.getState().setActivePage(activeIndex)
  }, [activeIndex])

  // ─── Transformer 刷新 ─────────────────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    const tr = transformerRef.current
    if (!stage || !tr) return
    const nodes = selectedElementIds
      .map((id) => stage.findOne(`#${id}`))
      .filter((n): n is Konva.Node => {
        if (!n) return false
        // 跳过装饰元素
        const el = displayElements.find((e) => e.id === n.id())
        return el ? el.name !== 'decor' : true
      })
    tr.nodes(nodes)
    tr.getLayer()?.batchDraw()
  }, [selectedElementIds, displayElements])

  // ─── 裁剪模式 Transformer 刷新 ─────────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    const tr = clipTransformerRef.current
    if (!stage || !tr || !clipModeElementId) {
      if (tr) tr.nodes([])
      return
    }
    const node = stage.findOne('#clip-region-rect')
    if (node) {
      tr.nodes([node])
      tr.getLayer()?.batchDraw()
    }
  }, [clipModeElementId, clipRegion])

  // ─── 选中 → 隐藏表格编辑浮层 ──────────────────────────────
  useEffect(() => {
    if (!selectedElementIds.includes(tableEditCell?.elId || '')) {
      setTableEditCell(null)
    }
  }, [selectedElementIds, tableEditCell])

  // ─── editorApi ────────────────────────────────────────────
  const editorApi = useMemo(
    () => ({
      addText: (text: string) => {
        useCanvasStore.getState().addElement(activeIndex, {
          type: 'text',
          x: 200, y: 300, width: 880, height: 60,
          text, fill: '#334155',
        })
        syncStoreToInternal()
      },
      addImage: (url: string) => {
        useCanvasStore.getState().addElement(activeIndex, {
          type: 'image',
          x: CANVAS_WIDTH * 0.15, y: CANVAS_HEIGHT * 0.1,
          width: CANVAS_WIDTH * 0.7, height: CANVAS_HEIGHT * 0.7,
          src: url,
        })
        syncStoreToInternal()
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeIndex, slidesInternal],
  )

  // ─── capturePage（原生 Konva 离屏渲染） ────────────────────
  useEffect(() => {
    canvasRef.current = {
      stageRef,
      capturePage: async (elements, width = CANVAS_WIDTH, height = CANVAS_HEIGHT, pixelRatio = 2) => {
        const imageLoadTasks: Promise<[string, HTMLImageElement] | null>[] = []
        for (const el of elements) {
          if (el.type === 'image' && el.src) {
            imageLoadTasks.push(
              new Promise((resolve) => {
                const img = new window.Image()
                img.crossOrigin = 'anonymous'
                img.onload = () => resolve([el.src!, img])
                img.onerror = () => {
                  console.warn('[capturePage] 图片加载失败，跳过:', el.src)
                  resolve(null) // 不 reject，跳过失败图片
                }
                img.src = el.src!
              }),
            )
          }
        }
        const settled = await Promise.all(imageLoadTasks)
        const loadedImages = new Map(
          settled.filter((r): r is [string, HTMLImageElement] => r !== null),
        )

        const container = document.createElement('div')
        container.style.cssText =
          'position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;overflow:hidden;'
        document.body.appendChild(container)

        try {
          const stage = new Konva.Stage({ container, width, height })
          const layer = new Konva.Layer()
          stage.add(layer)

          for (const el of elements) {
            switch (el.type) {
              case 'rect':
                layer.add(new Konva.Rect({ x: el.x, y: el.y, width: el.width, height: el.height, fill: el.fill || '#6366f1' }))
                break
              case 'text': {
                // 合并 fontWeight + fontStyle → Konva fontStyle（'bold' / 'italic' / 'bold italic'）
                const parts: string[] = []
                if (el.fontWeight === 'bold') parts.push('bold')
                if (el.fontStyle === 'italic') parts.push('italic')
                const konvaFontStyle = parts.join(' ') || 'normal'
                layer.add(new Konva.Text({ x: el.x, y: el.y, width: el.width, height: el.height, text: el.text || '', fill: el.fill || '#334155', fontSize: el.fontSize || 20, fontFamily: 'sans-serif', fontStyle: konvaFontStyle, textDecoration: el.textDecoration === 'underline' ? 'underline' : '', align: (el.align || 'left') as string, lineHeight: 1.4, wrap: 'word', ellipsis: true }))
                break
              }
              case 'circle':
                layer.add(new Konva.Circle({ x: el.x + (el.radius || el.width / 2), y: el.y + (el.radius || el.height / 2), radius: el.radius || Math.min(el.width, el.height) / 2, fill: el.fill || '#6366f1', stroke: el.stroke, strokeWidth: el.strokeWidth }))
                break
              case 'line':
                if (el.points) layer.add(new Konva.Line({ points: el.points, stroke: el.stroke || '#6366f1', strokeWidth: el.strokeWidth || 2 }))
                break
              case 'image': {
                const img = loadedImages.get(el.src || '')
                if (img) {
                  const imageNode = new Konva.Image({ x: el.x, y: el.y, width: el.width, height: el.height, image: img })
                  if (el.clipWidth && el.clipWidth > 0) {
                    (imageNode as any).clipFunc((ctx: any) => {
                      ctx.beginPath()
                      ctx.rect(el.clipX ?? 0, el.clipY ?? 0, el.clipWidth!, el.clipHeight ?? el.height)
                      ctx.closePath()
                    })
                  }
                  layer.add(imageNode)
                }
                break
              }
              case 'table': {
                if (el.tableData && el.tableData.length > 0) {
                  const group = new Konva.Group({ x: el.x, y: el.y })
                  const rc = el.tableData.length
                  const cc = el.tableData[0]?.length || 1
                  const cw = el.width / cc; const ch = el.height / rc
                  const headerFill = el.headerFill || '#2d7cf6'
                  const headerColor = el.headerColor || '#ffffff'
                  const rowAltFill = el.rowAltFill || '#f8fafc'
                  const borderColor = el.tableBorderColor || '#e2e8f0'
                  for (let r = 0; r < rc; r++)
                    for (let c = 0; c < cc; c++) {
                      const isHeader = r === 0
                      const cellFill = isHeader ? headerFill : r % 2 === 0 ? rowAltFill : '#ffffff'
                      const textFill = isHeader ? headerColor : '#334155'
                      group.add(new Konva.Rect({ x: c * cw, y: r * ch, width: cw, height: ch, stroke: borderColor, strokeWidth: 1, fill: cellFill }))
                      group.add(new Konva.Text({ x: c * cw + 5, y: r * ch, width: cw - 10, height: ch, text: el.tableData[r][c] || '', fill: textFill, fontSize: 14, fontStyle: isHeader ? 'bold' : 'normal', align: 'center', verticalAlign: 'middle', lineHeight: 1.4 }))
                    }
                  layer.add(group)
                }
                break
              }
              // placeholder（图片占位框）导出时跳过，保持 PDF 干净
              case 'placeholder':
                break
            }
          }

          layer.draw()
          const exportCanvas = stage.toCanvas({ pixelRatio })
          const dataUrl: string = await new Promise((resolve, reject) => {
            exportCanvas.toBlob(
              (blob) => {
                if (!blob) { reject(new Error('Canvas toBlob 返回空')); return }
                const reader = new FileReader()
                reader.onload = () => resolve(reader.result as string)
                reader.onerror = () => reject(new Error('FileReader 读取失败'))
                reader.readAsDataURL(blob)
              },
              'image/jpeg',
              0.92,
            )
          })
          stage.destroy()
          return dataUrl
        } finally {
          document.body.removeChild(container)
        }
      },
      editorApi,
    }
  }, [canvasRef, editorApi])

  // ─── 响应式缩放 ──────────────────────────────────────────
  useEffect(() => {
    const updateScale = () => {
      if (!wrapperRef.current) return
      const rect = wrapperRef.current.getBoundingClientRect()
      setScale(Math.min((rect.width - 32) / CANVAS_WIDTH, (rect.height - 32) / CANVAS_HEIGHT, 1))
    }
    updateScale()
    window.addEventListener('resize', updateScale)
    return () => window.removeEventListener('resize', updateScale)
  }, [])

  // ─── 工具栏操作 ──────────────────────────────────────────
  const addElementOp = useCallback(
    (spec: Omit<CanvasElement, 'id'>) => {
      useCanvasStore.getState().addElement(activeIndex, spec)
      syncStoreToInternal()
    },
    [activeIndex, syncStoreToInternal],
  )

  // ─── 拖拽图片到画布 ──────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      try {
        const raw = e.dataTransfer.getData('application/json')
        if (!raw) return
        const data = JSON.parse(raw) as { imageUrl?: string; title?: string }
        const imageUrl = data.imageUrl
        if (!imageUrl) return

        // 使用 Konva 原生 API 获取 stage 坐标系的精确指针位置
        // 注意：stage.getPointerPosition() 返回 CSS 像素坐标，
        // 当 canvas 缩放（scale < 1）时需除以 scale 转换为逻辑 (1280×720) 坐标
        const stage = stageRef.current
        if (!stage) return
        stage.setPointersPositions(e.nativeEvent as MouseEvent)
        const pos = stage.getPointerPosition()
        if (!pos) return
        const dropX = pos.x / scale
        const dropY = pos.y / scale

        // 以落点为中心放置图片（默认 280×158，16:9 近似）
        const imgW = 280
        const imgH = 158
        const x = Math.max(0, Math.min(CANVAS_WIDTH - imgW, dropX - imgW / 2))
        const y = Math.max(0, Math.min(CANVAS_HEIGHT - imgH, dropY - imgH / 2))

        addElementOp({ type: 'image', x, y, width: imgW, height: imgH, src: imageUrl })
      } catch {
        // 忽略非图片拖拽
      }
    },
    [scale, addElementOp],
  )

  const handleAddTextBox = () =>
    addElementOp({ type: 'text', x: CANVAS_WIDTH / 2 - 100, y: CANVAS_HEIGHT / 2 - 30, width: 200, height: 60, text: '双击编辑文本', fill: '#334155' })

  const handleAddRect = () =>
    addElementOp({ type: 'rect', x: CANVAS_WIDTH / 2 - 120, y: CANVAS_HEIGHT / 2 - 70, width: 240, height: 140, fill: '#dbeafe', stroke: '#2d7cf6', strokeWidth: 1, radius: 4 })

  // 选图 → 上传服务端持久化 → 返回可访问 URL（失败回退 blob URL）
  const pickAndUploadImage = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      const input = document.createElement('input')
      input.type = 'file'; input.accept = 'image/*'
      input.onchange = async () => {
        const file = input.files?.[0]
        if (!file) { resolve(null); return }
        if (projectId) {
          try {
            const { url } = await projectsApi.uploadAsset(projectId, file)
            // 后端返回 /api/v1/files/... 绝对路径，直接使用即可
            // Vite dev proxy 自动转发 /api → localhost:8000
            const abs = url.startsWith('http') ? url : url
            resolve(abs)
            return
          } catch (err) {
            console.warn('[uploadAsset] 上传失败，回退本地预览:', err)
          }
        }
        resolve(URL.createObjectURL(file))
      }
      input.click()
    })
  }, [projectId])

  const handleAddImage = useCallback(async () => {
    const url = await pickAndUploadImage()
    if (!url) return
    addElementOp({ type: 'image', x: CANVAS_WIDTH * 0.15, y: CANVAS_HEIGHT * 0.1, width: CANVAS_WIDTH * 0.7, height: CANVAS_HEIGHT * 0.7, src: url })
  }, [pickAndUploadImage, addElementOp])

  const handleAddImageUrl = useCallback(() => {
    const url = window.prompt('请输入图片 URL：')?.trim()
    if (!url) return
    addElementOp({ type: 'image', x: CANVAS_WIDTH * 0.15, y: CANVAS_HEIGHT * 0.1, width: CANVAS_WIDTH * 0.7, height: CANVAS_HEIGHT * 0.7, src: url })
  }, [addElementOp])

  // 替换占位框 / 已有图片为新图片（原地保留位置与尺寸）
  const handleReplaceImage = useCallback(async (elId: string) => {
    const url = await pickAndUploadImage()
    if (!url) return
    useCanvasStore.getState().updateElement(activeIndex, elId, { type: 'image', src: url, name: undefined })
    syncStoreToInternal()
  }, [pickAndUploadImage, activeIndex, syncStoreToInternal])

  // ─── 裁剪模式操作 ────────────────────────────────────────
  const enterClipMode = useCallback(
    (elId: string) => {
      useCanvasStore.getState().setClipMode(elId)
      // 清空选中，只显示裁剪框
      useCanvasStore.getState().setSelectedElements([])
    },
    [],
  )

  const exitClipMode = useCallback(() => {
    useCanvasStore.getState().setClipMode(null)
  }, [])

  const applyClip = useCallback(
    (elId: string, clipRegion: { x: number; y: number; width: number; height: number }) => {
      useCanvasStore.getState().updateElement(activeIndex, elId, {
        clipX: clipRegion.x,
        clipY: clipRegion.y,
        clipWidth: clipRegion.width,
        clipHeight: clipRegion.height,
      })
      useCanvasStore.getState().setClipMode(null)
      syncStoreToInternal()
    },
    [activeIndex, syncStoreToInternal],
  )

  const resetClip = useCallback(
    (elId: string) => {
      useCanvasStore.getState().updateElement(activeIndex, elId, {
        clipX: undefined,
        clipY: undefined,
        clipWidth: undefined,
        clipHeight: undefined,
      })
      useCanvasStore.getState().setClipMode(null)
      syncStoreToInternal()
    },
    [activeIndex, syncStoreToInternal],
  )

  // 裁剪区域状态（在裁剪模式下使用）
  // 进入裁剪模式时初始化裁剪区域（坐标基于 bounding box 空间，保持向后兼容）
  useEffect(() => {
    if (!clipModeElementId) {
      setImageRenderBounds(null)
      return
    }
    const el = displayElements.find((e) => e.id === clipModeElementId)
    if (!el || el.type !== 'image' || !el.src) return

    // 加载图片以获取自然尺寸，计算 contain-fit 渲染区域（供暗色遮罩对齐用）
    const img = new window.Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const imgScale = Math.min(el.width / img.width, el.height / img.height)
      const drawW = img.width * imgScale
      const drawH = img.height * imgScale
      const drawX = el.x + (el.width - drawW) / 2
      const drawY = el.y + (el.height - drawH) / 2
      setImageRenderBounds({ x: drawX, y: drawY, w: drawW, h: drawH })

      // 裁剪坐标仍存储在 bounding-box 空间（clipFunc 中通过 offset 转换）
      if (el.clipWidth && el.clipWidth > 0) {
        setClipRegion({ x: el.clipX || 0, y: el.clipY || 0, width: el.clipWidth, height: el.clipHeight || el.height })
      } else {
        setClipRegion({
          x: el.width * 0.1,
          y: el.height * 0.1,
          width: el.width * 0.8,
          height: el.height * 0.8,
        })
      }
    }
    img.onerror = () => {
      setImageRenderBounds({ x: el.x, y: el.y, w: el.width, h: el.height })
      if (el.clipWidth && el.clipWidth > 0) {
        setClipRegion({ x: el.clipX || 0, y: el.clipY || 0, width: el.clipWidth, height: el.clipHeight || el.height })
      } else {
        setClipRegion({
          x: el.width * 0.1,
          y: el.height * 0.1,
          width: el.width * 0.8,
          height: el.height * 0.8,
        })
      }
    }
    img.src = el.src
  }, [clipModeElementId, displayElements])

  // ─── 幻灯片操作 ──────────────────────────────────────────
  const markInternal = () => { isInternalChange.current = true }

  const handleAddSlide = () => {
    markInternal()
    const newSlide = createBlankSlide(slidesInternal.length)
    const updated = [...slidesInternal, newSlide]
    setSlidesInternal(updated)
    onActiveIndexChange(updated.length - 1)
  }

  const handleDuplicateSlide = (index: number) => {
    markInternal()
    useCanvasStore.getState().duplicateSlide(index)
    syncStoreToInternal()
    // Update slidesInternal from store
    const storeSlides = useCanvasStore.getState().slides
    const pages = Object.keys(storeSlides).map(Number).sort((a, b) => a - b)
    const newSlides = pages.map((p) => ({
      pageNumber: p,
      sectionTitle: slidesInternal.find((s) => s.pageNumber === p)?.sectionTitle || `第 ${p + 1} 页`,
      elements: storeSlides[p] || [],
    }))
    setSlidesInternal(newSlides)
    onActiveIndexChange(index + 1)
  }

  const handleDeleteSlide = (index: number) => {
    if (slidesInternal.length <= 1) return
    const slide = slidesInternal[index]
    const elementCount = slide.elements.filter((el) => el.name !== 'decor').length
    if (elementCount > 0) {
      if (!window.confirm(`确定要删除「${slide.sectionTitle}」吗？该幻灯片包含 ${elementCount} 个元素。`)) return
    }
    markInternal()
    const filtered = slidesInternal.filter((_, i) => i !== index)
    setSlidesInternal(filtered.map((s, i) => ({ ...s, pageNumber: i })))
    if (activeIndex >= filtered.length) onActiveIndexChange(filtered.length - 1)
  }

  const handleMoveSlide = (index: number, dir: 'up' | 'down') => {
    const newIdx = dir === 'up' ? index - 1 : index + 1
    if (newIdx < 0 || newIdx >= slidesInternal.length) return
    markInternal()
    const arr = [...slidesInternal]
    ;[arr[index], arr[newIdx]] = [arr[newIdx], arr[index]]
    setSlidesInternal(arr.map((s, i) => ({ ...s, pageNumber: i })))
    onActiveIndexChange(newIdx)
  }

  // ─── 拖拽回调（Circle 中心点需转换为左上角 + 组拖拽支持） ──
  const handleDragEnd = useCallback(
    (elId: string, elType?: string) => (e: any) => {
      const node = e.target
      const store = useCanvasStore.getState()
      const draggedEl = store.slides[activeIndex]?.find((el) => el.id === elId)

      // 🆕 v6: 组拖拽 — 计算 delta（store 初始位置 → konva 最终位置）并广播给同组所有元素
      if (draggedEl?.groupId) {
        const groupElements = store.slides[activeIndex]?.filter(
          (e) => e.groupId === draggedEl.groupId,
        ) ?? []

        // 计算被拖元素的最终位置（转换为 store 坐标，即 top-left）
        let finalX = node.x()
        let finalY = node.y()
        if (elType === 'circle') {
          const r = draggedEl.radius || Math.min(draggedEl.width || 120, draggedEl.height || 120) / 2
          finalX -= r
          finalY -= r
        }

        // delta = konva最终位置 - store原始位置
        const dx = finalX - draggedEl.x
        const dy = finalY - draggedEl.y

        if (dx !== 0 || dy !== 0) {
          // 广播 delta 给所有组内元素
          groupElements.forEach((ge) => {
            store.updateElement(activeIndex, ge.id, {
              x: ge.x + dx,
              y: ge.y + dy,
            })
          })
        }
        syncStoreToInternal()
        return
      }

      // 非组元素：按原有逻辑处理
      let storeX = node.x()
      let storeY = node.y()
      if (elType === 'circle') {
        const storeEl = store.slides[activeIndex]?.find((el) => el.id === elId)
        const r = storeEl?.radius || Math.min(storeEl?.width || 120, storeEl?.height || 120) / 2
        storeX = node.x() - r
        storeY = node.y() - r
      }
      store.updateElement(activeIndex, elId, {
        x: storeX,
        y: storeY,
      })
      syncStoreToInternal()
    },
    [activeIndex, syncStoreToInternal],
  )

  // ─── Transform 结束（防文字拉伸失真 + Circle 中心点修正） ───
  const handleTransformEnd = useCallback(
    (elId: string, elType?: string) => (e: any) => {
      const node = e.target
      const scaleX = node.scaleX()
      const scaleY = node.scaleY()
      node.scaleX(1)
      node.scaleY(1)
      const newW = Math.max(10, node.width() * scaleX)
      const newH = Math.max(10, node.height() * scaleY)
      const attrs: Partial<CanvasElement> = {
        width: newW,
        height: newH,
      }
      if (elType === 'circle') {
        const newR = Math.min(newW, newH) / 2
        attrs.x = node.x() - newR
        attrs.y = node.y() - newR
        attrs.radius = newR
      } else {
        attrs.x = node.x()
        attrs.y = node.y()
      }
      useCanvasStore.getState().updateElement(activeIndex, elId, attrs)
      syncStoreToInternal()
    },
    [activeIndex, syncStoreToInternal],
  )

  // ─── 选中与清空 ──────────────────────────────────────────
  const clearSelection = () => useCanvasStore.getState().setSelectedElements([])

  /** 🆕 v6: 组感知选择 — 点击组内任一元素即选中整组 */
  const selectElement = (id: string) => {
    const store = useCanvasStore.getState()
    const el = store.slides[activeIndex]?.find((e) => e.id === id)
    if (el?.groupId) {
      const groupIds = store.slides[activeIndex]
        ?.filter((e) => e.groupId === el.groupId)
        .map((e) => e.id) ?? []
      store.setSelectedElements(groupIds.length > 0 ? groupIds : [id])
    } else {
      store.setSelectedElements([id])
    }
  }

  // ─── 双击编辑文字 ────────────────────────────────────────
  const handleTextDblClick = (id: string) => {
    useCanvasStore.getState().setEditingElement(id)
    useCanvasStore.getState().setSelectedElements([id])
  }

  // ─── 表格单元格编辑 ──────────────────────────────────────
  const handleCellDblClick = (elId: string) => (r: number, c: number) => {
    selectElement(elId)
    setTableEditCell({ elId, r, c })
  }
  const handleCellBlur =
    (elId: string) => (val: string) => {
      if (!tableEditCell) return
      const el = displayElements.find((e) => e.id === elId)
      if (!el?.tableData) return
      const newData = el.tableData.map((row) => [...row])
      newData[tableEditCell.r][tableEditCell.c] = val
      useCanvasStore.getState().updateElement(activeIndex, elId, { tableData: newData })
      syncStoreToInternal()
      setTableEditCell(null)
    }

  // ─── 删除选中元素 ────────────────────────────────────────
  const deleteSelected = useCallback(() => {
    const ids = useCanvasStore.getState().selectedElementIds
    if (ids.length === 0) return
    for (const id of ids) {
      useCanvasStore.getState().deleteElement(activeIndex, id)
    }
    useCanvasStore.getState().setSelectedElements([])
    syncStoreToInternal()
  }, [activeIndex, syncStoreToInternal])

  // ─── 键盘快捷键 ──────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return

      const editingId = useCanvasStore.getState().editingElementId

      // 裁剪模式下：Escape 取消 / Enter 应用
      const clipId = useCanvasStore.getState().clipModeElementId
      if (clipId) {
        if (e.key === 'Escape') {
          e.preventDefault()
          exitClipMode()
          return
        }
        if (e.key === 'Enter') {
          e.preventDefault()
          const cr = clipRegionRef.current
          applyClip(clipId, cr)
          return
        }
        return // 裁剪模式下阻止其他快捷键
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (editingId === null && !tableEditCell) {
          e.preventDefault()
          deleteSelected()
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        e.preventDefault()
        const ids = useCanvasStore.getState().selectedElementIds
        if (ids.length === 1) useCanvasStore.getState().copyElement(ids[0])
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        e.preventDefault()
        useCanvasStore.getState().pasteElement(activeIndex)
        syncStoreToInternal()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault()
        ;(useCanvasStore as any).temporal?.getState?.()?.undo?.()
        syncStoreToInternal()
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
        e.preventDefault()
        ;(useCanvasStore as any).temporal?.getState?.()?.redo?.()
        syncStoreToInternal()
      }
      // 幻灯片级别快捷键
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
        e.preventDefault()
        handleDuplicateSlide(activeIndex)
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault()
        useCanvasStore.getState().copySlide(activeIndex)
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'V') {
        e.preventDefault()
        useCanvasStore.getState().pasteSlide(activeIndex)
        syncStoreToInternal()
        onActiveIndexChange(activeIndex + 1)
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
        e.preventDefault()
        handleAddSlide()
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'Delete') {
        e.preventDefault()
        handleDeleteSlide(activeIndex)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [activeIndex, deleteSelected, syncStoreToInternal, tableEditCell])

  // ─── 选中元素的 style 引用 ────────────────────────────────
  const selectedEl = useMemo(
    () => displayElements.find((el) => selectedElementIds.includes(el.id)),
    [displayElements, selectedElementIds],
  )

  const hasHistory = () => {
    try {
      const ts = (useCanvasStore as any).temporal?.getState?.()
      return (ts?.pastStates?.length || 0) > 0
    } catch {
      return false
    }
  }
  const hasFuture = () => {
    try {
      const ts = (useCanvasStore as any).temporal?.getState?.()
      return (ts?.futureStates?.length || 0) > 0
    } catch {
      return false
    }
  }

  // ════════════════════════════════════════════════════════
  // 渲染
  // ════════════════════════════════════════════════════════

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* ─── 左侧：缩略图边栏 ──────────────────────────────── */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
          <span className="text-xs font-medium">幻灯片</span>
          <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
            {slidesInternal.length} 页
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {slidesInternal.map((slide, i) => (
            <div
              key={`s-${i}`}
              onClick={() => onActiveIndexChange(i)}
              className={cn(
                'group relative flex items-center gap-2 rounded-md px-2 py-2 cursor-pointer mb-0.5 transition-colors',
                activeIndex === i ? 'bg-primary/10 ring-1 ring-primary/30' : 'hover:bg-muted',
              )}
            >
              <div className="flex h-9 w-16 shrink-0 items-center justify-center rounded border border-border bg-white text-[9px] text-muted-foreground">
                {slide.pageNumber === 0 ? '封面' : `P${slide.pageNumber}`}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] font-medium">
                  {slide.pageNumber === 0 ? '🎨 封面' : slide.sectionTitle}
                </p>
              </div>
              {!readOnly && (
                <div className="absolute right-1 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5 bg-card/95 rounded px-0.5">
                  <button onClick={(ev) => { ev.stopPropagation(); handleMoveSlide(i, 'up') }} disabled={i === 0} className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20" title="上移"><ChevronUp className="h-3 w-3" /></button>
                  <button onClick={(ev) => { ev.stopPropagation(); handleMoveSlide(i, 'down') }} disabled={i === slidesInternal.length - 1} className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-20" title="下移"><ChevronDown className="h-3 w-3" /></button>
                  <button onClick={(ev) => { ev.stopPropagation(); handleDuplicateSlide(i) }} className="rounded p-0.5 text-muted-foreground hover:text-primary" title="复制幻灯片"><Copy className="h-3 w-3" /></button>
                  <button onClick={(ev) => { ev.stopPropagation(); handleDeleteSlide(i) }} disabled={slidesInternal.length <= 1} className="rounded p-0.5 text-muted-foreground hover:text-destructive disabled:opacity-20" title="删除"><Trash2 className="h-3 w-3" /></button>
                </div>
              )}
            </div>
          ))}
        </div>
        {!readOnly && (
          <div className="border-t border-border p-2 space-y-1.5">
            <Button variant="outline" size="sm" onClick={handleAddSlide} className="w-full gap-1 text-[11px]">
              <Plus className="h-3.5 w-3.5" /> 添加页面
            </Button>
            {copiedSlide && (
              <Button variant="ghost" size="sm" onClick={() => {
                useCanvasStore.getState().pasteSlide(activeIndex)
                syncStoreToInternal()
                // Rebuild slidesInternal from updated store
                const updatedSlides = useCanvasStore.getState().slides
                const pages = Object.keys(updatedSlides).map(Number).sort((a, b) => a - b)
                const rebuilt = pages.map((p) => ({
                  pageNumber: p,
                  sectionTitle: slidesInternal.find((s) => s.pageNumber === p)?.sectionTitle || `第 ${p + 1} 页`,
                  elements: updatedSlides[p] || [],
                }))
                setSlidesInternal(rebuilt)
                onActiveIndexChange(activeIndex + 1)
              }} className="w-full gap-1 text-[11px]">
                <ClipboardPaste className="h-3.5 w-3.5" /> 粘贴幻灯片
              </Button>
            )}
          </div>
        )}
      </aside>

      {/* ─── 中央：画布 + 工具栏 ────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* 增强工具栏 */}
        {showToolbar && !readOnly && (
          <div className="flex items-center gap-1 border-b border-border px-3 py-1.5 flex-wrap">
            {/* 插入 */}
            <Button variant="ghost" size="sm" onClick={handleAddTextBox} className="gap-1 text-[11px] h-7"><Type className="h-3.5 w-3.5" />文本</Button>
            <Button variant="ghost" size="sm" onClick={handleAddImage} className="gap-1 text-[11px] h-7"><ImageIcon className="h-3.5 w-3.5" />图片</Button>
            <Button variant="ghost" size="sm" onClick={handleAddImageUrl} className="gap-1 text-[11px] h-7" title="通过 URL 插入图片"><ImageIcon className="h-3.5 w-3.5" />图片URL</Button>
            <Button variant="ghost" size="sm" onClick={handleAddRect} className="gap-1 text-[11px] h-7"><Square className="h-3.5 w-3.5" />矩形</Button>
            <Button variant="ghost" size="sm" onClick={() => addElementOp({ type: 'circle', x: 500, y: 250, width: 120, height: 120, fill: '#6366f1', radius: 60 })} className="gap-1 text-[11px] h-7"><CircleDot className="h-3.5 w-3.5" />圆形</Button>
            <Button variant="ghost" size="sm" onClick={() => addElementOp({ type: 'line', x: 0, y: 0, width: 200, height: 4, points: [300, 400, 600, 400], stroke: '#6366f1', strokeWidth: 3 })} className="gap-1 text-[11px] h-7"><Minus className="h-3.5 w-3.5" />直线</Button>
            <Button variant="ghost" size="sm" onClick={() => addElementOp({ type: 'table', x: 200, y: 200, width: 500, height: 300, tableData: [['标题1','标题2','标题3'],['','',''],['','','']], headerFill: '#2d7cf6', headerColor: '#ffffff', rowAltFill: '#f8fafc', tableBorderColor: '#e2e8f0' })} className="gap-1 text-[11px] h-7"><Table2 className="h-3.5 w-3.5" />表格</Button>

            <span className="h-4 w-px bg-border mx-0.5" />

            {/* 颜色拾取器 */}
            {selectedEl && (
              <>
                <span className="text-[10px] text-muted-foreground">填充</span>
                <input
                  type="color"
                  value={selectedEl.fill || '#6366f1'}
                  onChange={(e) => {
                    useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { fill: e.target.value })
                    syncStoreToInternal()
                  }}
                  className="w-6 h-6 rounded border cursor-pointer p-0"
                />
                {(selectedEl.type === 'line' || selectedEl.type === 'circle' || selectedEl.type === 'rect') && (
                  <>
                    <span className="text-[10px] text-muted-foreground">描边</span>
                    <input
                      type="color"
                      value={selectedEl.stroke || '#6366f1'}
                      onChange={(e) => {
                        useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { stroke: e.target.value, strokeWidth: selectedEl.strokeWidth || 1 })
                        syncStoreToInternal()
                      }}
                      className="w-6 h-6 rounded border cursor-pointer p-0"
                    />
                  </>
                )}
                {selectedEl.type === 'image' && !clipModeElementId && (
                  <>
                    <button
                      onClick={() => handleReplaceImage(selectedEl.id)}
                      className="rounded p-1 hover:bg-muted"
                      title="替换图片"
                    ><RefreshCw className="h-3.5 w-3.5" /></button>
                    <button
                      onClick={() => enterClipMode(selectedEl.id)}
                      className="rounded p-1 hover:bg-muted"
                      title="裁剪图片"
                    ><Crop className="h-3.5 w-3.5" /></button>
                  </>
                )}
                {clipModeElementId && (
                  <>
                    <button
                      onClick={() => applyClip(clipModeElementId, clipRegion)}
                      className="rounded p-1 hover:bg-emerald-100 text-emerald-600"
                      title="应用裁剪"
                    ><Check className="h-3.5 w-3.5" /></button>
                    <button
                      onClick={() => resetClip(clipModeElementId)}
                      className="rounded p-1 hover:bg-amber-100 text-amber-600"
                      title="重置裁剪"
                    ><RefreshCw className="h-3.5 w-3.5" /></button>
                    <button
                      onClick={exitClipMode}
                      className="rounded p-1 hover:bg-red-100 text-red-500"
                      title="取消裁剪"
                    ><X className="h-3.5 w-3.5" /></button>
                  </>
                )}
                <span className="h-4 w-px bg-border mx-0.5" />

                {/* 排版按钮 */}
                {selectedEl.type === 'text' && (
                  <>
                    <button
                      onClick={() => {
                        const cur = selectedEl.fontWeight === 'bold' ? 'normal' : 'bold'
                        useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { fontWeight: cur })
                        syncStoreToInternal()
                      }}
                      className={cn('rounded p-1', selectedEl.fontWeight === 'bold' ? 'bg-primary/20' : 'hover:bg-muted')}
                    ><Bold className="h-3.5 w-3.5" /></button>
                    <button
                      onClick={() => {
                        const cur = selectedEl.fontStyle === 'italic' ? 'normal' : 'italic'
                        useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { fontStyle: cur })
                        syncStoreToInternal()
                      }}
                      className={cn('rounded p-1', selectedEl.fontStyle === 'italic' ? 'bg-primary/20' : 'hover:bg-muted')}
                    ><Italic className="h-3.5 w-3.5" /></button>
                    <button
                      onClick={() => {
                        const cur = selectedEl.textDecoration === 'underline' ? 'none' : 'underline'
                        useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { textDecoration: cur })
                        syncStoreToInternal()
                      }}
                      className={cn('rounded p-1', selectedEl.textDecoration === 'underline' ? 'bg-primary/20' : 'hover:bg-muted')}
                    ><Underline className="h-3.5 w-3.5" /></button>
                    <span className="h-4 w-px bg-border mx-0.5" />
                    <button onClick={() => { useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { align: 'left' }); syncStoreToInternal() }} className={cn('rounded p-1', selectedEl.align === 'left' ? 'bg-primary/20' : 'hover:bg-muted')}><AlignLeft className="h-3.5 w-3.5" /></button>
                    <button onClick={() => { useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { align: 'center' }); syncStoreToInternal() }} className={cn('rounded p-1', selectedEl.align === 'center' ? 'bg-primary/20' : 'hover:bg-muted')}><AlignCenter className="h-3.5 w-3.5" /></button>
                    <button onClick={() => { useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { align: 'right' }); syncStoreToInternal() }} className={cn('rounded p-1', selectedEl.align === 'right' ? 'bg-primary/20' : 'hover:bg-muted')}><AlignRight className="h-3.5 w-3.5" /></button>
                    <span className="h-4 w-px bg-border mx-0.5" />
                    {/* 字号控件 */}
                    <span className="text-[10px] text-muted-foreground">字号</span>
                    <input
                      type="number"
                      min={8}
                      max={120}
                      value={selectedEl.fontSize || 20}
                      onChange={(e) => {
                        const v = Math.max(8, Math.min(120, Number(e.target.value) || 20))
                        useCanvasStore.getState().updateElement(activeIndex, selectedEl.id, { fontSize: v })
                        syncStoreToInternal()
                      }}
                      className="w-12 h-6 rounded border border-border px-1 text-[11px] tabular-nums"
                    />
                    <span className="h-4 w-px bg-border mx-0.5" />
                  </>
                )}

                {/* 图层排序 */}
                <button onClick={() => { useCanvasStore.getState().moveLayer(activeIndex, selectedEl.id, 'up'); syncStoreToInternal() }} className="rounded p-1 hover:bg-muted" title="上移一层"><ArrowUpToLine className="h-3.5 w-3.5" /></button>
                <button onClick={() => { useCanvasStore.getState().moveLayer(activeIndex, selectedEl.id, 'down'); syncStoreToInternal() }} className="rounded p-1 hover:bg-muted" title="下移一层"><ArrowDownToLine className="h-3.5 w-3.5" /></button>
                <button onClick={() => { useCanvasStore.getState().moveLayer(activeIndex, selectedEl.id, 'top'); syncStoreToInternal() }} className="rounded p-1 hover:bg-muted" title="置顶"><ChevronsUp className="h-3.5 w-3.5" /></button>
                <button onClick={() => { useCanvasStore.getState().moveLayer(activeIndex, selectedEl.id, 'bottom'); syncStoreToInternal() }} className="rounded p-1 hover:bg-muted" title="置底"><ChevronsDown className="h-3.5 w-3.5" /></button>

                <span className="h-4 w-px bg-border mx-0.5" />
              </>
            )}

            {/* 复制粘贴 */}
            <button
              onClick={() => {
                const ids = useCanvasStore.getState().selectedElementIds
                if (ids.length === 1) useCanvasStore.getState().copyElement(ids[0])
              }}
              disabled={selectedElementIds.length !== 1}
              className="rounded p-1 hover:bg-muted disabled:opacity-30"
              title="复制 (Ctrl+C)"
            ><Copy className="h-3.5 w-3.5" /></button>
            <button
              onClick={() => { useCanvasStore.getState().pasteElement(activeIndex); syncStoreToInternal() }}
              disabled={!useCanvasStore.getState().clipboard}
              className="rounded p-1 hover:bg-muted disabled:opacity-30"
              title="粘贴 (Ctrl+V)"
            ><ClipboardPaste className="h-3.5 w-3.5" /></button>

            <span className="h-4 w-px bg-border mx-0.5" />

            {/* Undo / Redo */}
            <button
              onClick={() => { (useCanvasStore as any).temporal?.getState?.()?.undo?.(); syncStoreToInternal() }}
              disabled={!hasHistory()}
              className="rounded p-1 hover:bg-muted disabled:opacity-30"
              title="撤销 (Ctrl+Z)"
            ><Undo2 className="h-3.5 w-3.5" /></button>
            <button
              onClick={() => { (useCanvasStore as any).temporal?.getState?.()?.redo?.(); syncStoreToInternal() }}
              disabled={!hasFuture()}
              className="rounded p-1 hover:bg-muted disabled:opacity-30"
              title="重做 (Ctrl+Y)"
            ><Redo2 className="h-3.5 w-3.5" /></button>

            <span className="ml-auto text-[10px] text-muted-foreground/70">
              {selectedElementIds.length > 0 ? `${selectedElementIds.length} 个选中` : '单击选中 · 双击编辑 · Del 删除'}
            </span>
          </div>
        )}

        {/* 画布 */}
        <div
          ref={wrapperRef}
          className="flex-1 bg-[#e8eaed] p-4 flex items-center justify-center relative"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div
            className="shadow-2xl bg-white"
            style={{ width: CANVAS_WIDTH * scale, height: CANVAS_HEIGHT * scale }}
          >
            <Stage
              width={CANVAS_WIDTH * scale}
              height={CANVAS_HEIGHT * scale}
              scaleX={scale}
              scaleY={scale}
              ref={stageRef}
              onClick={(e) => {
                // 点击空白区域清空选中
                if (e.target === e.target.getStage()) clearSelection()
              }}
              onTap={(e) => {
                if (e.target === e.target.getStage()) clearSelection()
              }}
            >
              <Layer>
                {/* 背景 */}
                <Rect
                  width={CANVAS_WIDTH}
                  height={CANVAS_HEIGHT}
                  fill="#ffffff"
                  onClick={clearSelection}
                  onTap={clearSelection}
                />

                {/* 动态渲染元素 */}
                {displayElements.map((el: CanvasElement) => {
                  const isEditing = el.id === editingElementId
                  const isSelected = selectedElementIds.includes(el.id)
                  const isDecor = el.name === 'decor' || el.name === 'arrangement-decor'  // 装饰元素不可选中/拖拽

                  const interactionProps = isDecor
                    ? { draggable: false }  // 装饰元素：无交互
                    : {
                        draggable: !readOnly && !isEditing,
                        onClick: (e: any) => {
                          e.cancelBubble = true
                          selectElement(el.id)
                        },
                        onTap: (e: any) => {
                          e.cancelBubble = true
                          selectElement(el.id)
                        },
                        onDragEnd: handleDragEnd(el.id, el.type),
                        onTransformEnd: handleTransformEnd(el.id, el.type),
                      }

                  switch (el.type) {
                    case 'rect':
                      return (
                        <Rect
                          key={el.id}
                          id={el.id}
                          name="element"
                          x={el.x} y={el.y}
                          width={el.width} height={el.height}
                          fill={el.fill || '#6366f1'}
                          stroke={el.stroke}
                          strokeWidth={el.strokeWidth}
                          cornerRadius={el.radius || 0}
                          {...interactionProps}
                        />
                      )
                    case 'circle':
                      return (
                        <Circle
                          key={el.id}
                          id={el.id}
                          name="element"
                          x={el.x + (el.radius || el.width / 2)}
                          y={el.y + (el.radius || el.height / 2)}
                          radius={el.radius || Math.min(el.width, el.height) / 2}
                          fill={el.fill || '#6366f1'}
                          stroke={el.stroke}
                          strokeWidth={el.strokeWidth}
                          {...interactionProps}
                        />
                      )
                    case 'line':
                      return (
                        <Line
                          key={el.id}
                          id={el.id}
                          name="element"
                          x={el.x} y={el.y}
                          points={el.points || [0, 0, el.width, el.height]}
                          stroke={el.stroke || '#6366f1'}
                          strokeWidth={el.strokeWidth || 2}
                          hitStrokeWidth={20}
                          {...interactionProps}
                        />
                      )
                    case 'text':
                      // 双击编辑态：隐藏 Text，显示 HTML textarea
                      if (isEditing) {
                        return (
                          <Html
                            key={el.id}
                            groupProps={{ x: el.x, y: el.y }}
                            divProps={{ style: { pointerEvents: 'auto' } }}
                          >
                            <textarea
                              autoFocus
                              defaultValue={el.text}
                              style={{
                                width: el.width,
                                height: Math.max(el.height, 40),
                                fontSize: el.fontSize || 20,
                                fontFamily: 'sans-serif',
                                fontWeight: el.fontWeight || 'normal',
                                fontStyle: el.fontStyle || 'normal',
                                textDecoration: el.textDecoration || 'none',
                                color: el.fill || '#000000',
                                textAlign: (el.align || 'left') as any,
                                background: 'rgba(255,255,255,0.95)',
                                border: '2px dashed #6366f1',
                                padding: '4px 6px',
                                resize: 'none',
                                outline: 'none',
                                wordWrap: 'break-word',
                                lineHeight: 1.4,
                              }}
                              onBlur={(e) => {
                                useCanvasStore.getState().updateElement(activeIndex, el.id, { text: e.target.value })
                                useCanvasStore.getState().setEditingElement(null)
                                syncStoreToInternal()
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Escape') {
                                  useCanvasStore.getState().setEditingElement(null)
                                }
                              }}
                            />
                          </Html>
                        )
                      }
                      return (
                        <Text
                          key={el.id}
                          id={el.id}
                          name="element"
                          x={el.x} y={el.y}
                          width={el.width}
                          height={el.height}
                          text={el.text || ''}
                          fontSize={el.fontSize || 20}
                          fontFamily="sans-serif"
                          fontWeight={el.fontWeight || 'normal'}
                          fontStyle={el.fontStyle || 'normal'}
                          textDecoration={el.textDecoration || 'none'}
                          fill={el.fill || '#000000'}
                          align={el.align || 'left'}
                          lineHeight={1.4}
                          wrap="word"
                          ellipsis
                          {...interactionProps}
                          onDblClick={() => handleTextDblClick(el.id)}
                        />
                      )
                    case 'placeholder':
                      return (
                        <RenderPlaceholder
                          key={el.id}
                          el={el}
                          draggable={!readOnly && !isDecor}
                          onDragEnd={handleDragEnd(el.id, 'placeholder')}
                          onTransformEnd={handleTransformEnd(el.id, 'placeholder')}
                          onClick={(e: any) => { e.cancelBubble = true; selectElement(el.id) }}
                          onTap={(e: any) => { e.cancelBubble = true; selectElement(el.id) }}
                          onDblClick={() => handleReplaceImage(el.id)}
                        />
                      )
                    case 'image':
                      if (el.src) {
                        return (
                          <RenderImage
                            key={el.id}
                            id={el.id}
                            src={el.src}
                            x={el.x} y={el.y}
                            width={el.width} height={el.height}
                            draggable={!readOnly}
                            onDragEnd={handleDragEnd(el.id, 'image')}
                            onTransformEnd={handleTransformEnd(el.id, 'image')}
                            onClick={(e: any) => { e.cancelBubble = true; selectElement(el.id) }}
                            onTap={(e: any) => { e.cancelBubble = true; selectElement(el.id) }}
                            clipX={el.clipX}
                            clipY={el.clipY}
                            clipWidth={el.clipWidth}
                            clipHeight={el.clipHeight}
                          />
                        )
                      }
                      return null
                    case 'table':
                      if (el.tableData) {
                        return (
                          <Fragment key={el.id}>
                            <RenderTable
                              el={el}
                              draggable={!readOnly}
                              onDragEnd={handleDragEnd(el.id, 'table')}
                              onTransformEnd={handleTransformEnd(el.id, 'table')}
                              onClick={(e: any) => { e.cancelBubble = true; selectElement(el.id) }}
                              editingCell={
                                tableEditCell?.elId === el.id
                                  ? { r: tableEditCell.r, c: tableEditCell.c }
                                  : null
                              }
                              onCellDblClick={handleCellDblClick(el.id)}
                              onCellBlur={handleCellBlur(el.id)}
                            />
                            {/* 表格行列控制面板 */}
                            {isSelected && !readOnly && (
                              <TableControlPanel
                                el={el}
                                activePage={activeIndex}
                                syncStoreToInternal={syncStoreToInternal}
                              />
                            )}
                          </Fragment>
                        )
                      }
                      return null
                    default:
                      return null
                  }
                })}

                {/* 裁剪模式覆盖层 */}
                {clipModeElementId && imageRenderBounds && (() => {
                  const clipEl = displayElements.find((e) => e.id === clipModeElementId)
                  if (!clipEl || clipEl.type !== 'image') return null
                  const cr = clipRegion
                  const ib = imageRenderBounds
                  // 🆕 暗色遮罩基于图片的 contain-fit 渲染区域 (ib)，
                  // 与 bounding-box 空间的裁剪区域 (cr) 求交集，确保遮罩精确覆盖图片
                  const clipLeft = clipEl.x + cr.x
                  const clipRight = clipEl.x + cr.x + cr.width
                  const clipTop = clipEl.y + cr.y
                  const clipBottom = clipEl.y + cr.y + cr.height
                  // 裁剪区域与图片渲染区域的交集
                  const visLeft = Math.max(ib.x, clipLeft)
                  const visRight = Math.min(ib.x + ib.w, clipRight)
                  const visTop = Math.max(ib.y, clipTop)
                  const visBottom = Math.min(ib.y + ib.h, clipBottom)
                  return (
                    <>
                      {/* 暗色覆盖（四个区域，与图片渲染区域求交集） */}
                      <Rect x={ib.x} y={ib.y} width={Math.max(0, clipLeft - ib.x)} height={ib.h} fill="rgba(0,0,0,0.35)" listening={false} />
                      <Rect x={clipRight} y={ib.y} width={Math.max(0, ib.x + ib.w - clipRight)} height={ib.h} fill="rgba(0,0,0,0.35)" listening={false} />
                      <Rect x={visLeft} y={ib.y} width={Math.max(0, visRight - visLeft)} height={Math.max(0, clipTop - ib.y)} fill="rgba(0,0,0,0.35)" listening={false} />
                      <Rect x={visLeft} y={clipBottom} width={Math.max(0, visRight - visLeft)} height={Math.max(0, ib.y + ib.h - clipBottom)} fill="rgba(0,0,0,0.35)" listening={false} />
                      {/* 裁剪区域虚线框 — 可拖拽移动 + 可拖动角点/边缩放 */}
                      <Rect
                        id="clip-region-rect"
                        name="clip-region-rect"
                        x={clipLeft} y={clipTop}
                        width={cr.width} height={cr.height}
                        stroke="#6366f1"
                        strokeWidth={1.5}
                        dash={[6, 3]}
                        draggable
                        dragBoundFunc={(pos) => ({
                          x: Math.max(ib.x, Math.min(ib.x + ib.w - cr.width, pos.x)),
                          y: Math.max(ib.y, Math.min(ib.y + ib.h - cr.height, pos.y)),
                        })}
                        onDragEnd={(e) => {
                          setClipRegion((prev) => ({
                            ...prev,
                            x: e.target.x() - clipEl.x,
                            y: e.target.y() - clipEl.y,
                          }))
                        }}
                        onTransformEnd={(e) => {
                          const node = e.target
                          const scaleX = node.scaleX()
                          const scaleY = node.scaleY()
                          // 重置 scale 防止累积
                          node.scaleX(1)
                          node.scaleY(1)
                          const newW = Math.max(20, node.width() * scaleX)
                          const newH = Math.max(20, node.height() * scaleY)
                          const newX = node.x() - clipEl.x
                          const newY = node.y() - clipEl.y
                          // 限制在 bounding box 范围内
                          setClipRegion({
                            x: Math.max(0, newX),
                            y: Math.max(0, newY),
                            width: Math.min(clipEl.width - newX, newW),
                            height: Math.min(clipEl.height - newY, newH),
                          })
                        }}
                      />
                      {/* 裁剪区域专用 Transformer（四角缩放） */}
                      <Transformer
                        ref={clipTransformerRef}
                        rotateEnabled={false}
                        keepRatio={false}
                        borderStroke="#6366f1"
                        borderStrokeWidth={1}
                        anchorSize={8}
                        anchorCornerRadius={2}
                        enabledAnchors={[
                          'top-left', 'top-right',
                          'bottom-left', 'bottom-right',
                          'middle-left', 'middle-right',
                          'top-center', 'bottom-center',
                        ]}
                        boundBoxFunc={(_oldBox, newBox) => {
                          // 限制裁剪区域不能小于 20px
                          if (newBox.width < 20 || newBox.height < 20) return _oldBox
                          // 不能超出图片渲染区域边界（ib）
                          const nX = Math.max(ib.x, newBox.x)
                          const nY = Math.max(ib.y, newBox.y)
                          const maxW = ib.x + ib.w - nX
                          const maxH = ib.y + ib.h - nY
                          return {
                            ...newBox,
                            x: nX,
                            y: nY,
                            width: Math.min(maxW, newBox.width),
                            height: Math.min(maxH, newBox.height),
                          }
                        }}
                      />
                    </>
                  )
                })()}

                {/* Transformer（选中框，最上层）—— 裁剪模式下隐藏 */}
                {!clipModeElementId && (
                <Transformer
                  ref={transformerRef}
                  rotateEnabled={false}
                  keepRatio={selectedEl?.type === 'circle'}
                  boundBoxFunc={(oldBox, newBox) => {
                    if (newBox.width < 10 || newBox.height < 10) return oldBox
                    return newBox
                  }}
                  borderStroke="#6366f1"
                  borderStrokeWidth={1.5}
                  anchorSize={8}
                  anchorCornerRadius={2}
                  enabledAnchors={[
                    'top-left', 'top-right',
                    'bottom-left', 'bottom-right',
                    'middle-left', 'middle-right',
                    'top-center', 'bottom-center',
                  ]}
                />
                )}
              </Layer>
            </Stage>
          </div>
        </div>

        {/* 底部页码 */}
        {slidesInternal.length > 1 && (
          <div className="flex items-center justify-center gap-3 border-t border-border px-4 py-1.5">
            <button onClick={() => onActiveIndexChange(Math.max(0, activeIndex - 1))} disabled={activeIndex === 0} className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
            <span className="text-[11px] tabular-nums text-muted-foreground">{activeIndex + 1} / {slidesInternal.length}</span>
            <button onClick={() => onActiveIndexChange(Math.min(slidesInternal.length - 1, activeIndex + 1))} disabled={activeIndex >= slidesInternal.length - 1} className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
          </div>
        )}
      </div>
    </div>
  )
}
