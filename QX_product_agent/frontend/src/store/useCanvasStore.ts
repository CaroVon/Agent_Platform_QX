/**
 * ============================================================
 * useCanvasStore —— Zustand 原子化 Canvas 状态管理 + Undo/Redo
 *
 * v0.4 扩展:
 * - 新增 circle / line 元素类型
 * - 新增排版、边框、装饰字段
 * - 新增 selectedElementIds / editingElementId / clipboard
 * - 新增 duplicateSlide / copyElement / pasteElement / moveLayer
 * - 集成 zundo temporal 中间件实现无侵入式 Undo/Redo
 * ============================================================
 */

import { create } from 'zustand'
import { temporal } from 'zundo'

// ══════════════════════════════════════════════════════════════
// 类型定义
// ══════════════════════════════════════════════════════════════

export interface CanvasElement {
  id: string
  type: 'text' | 'rect' | 'image' | 'table' | 'circle' | 'line' | 'placeholder'
  x: number
  y: number
  width: number
  height: number
  fill?: string
  text?: string
  src?: string // 图片专用
  tableData?: string[][] // 表格专用

  // 表格样式（可选，渲染器内有默认兜底）
  headerFill?: string       // 表头背景色
  headerColor?: string      // 表头文字色
  rowAltFill?: string       // 斑马纹偶数行背景
  tableBorderColor?: string // 单元格边框色

  // 排版字段
  fontWeight?: string      // 'normal' | 'bold'
  fontStyle?: string       // 'normal' | 'italic'
  textDecoration?: string  // 'none' | 'underline'
  align?: string           // 'left' | 'center' | 'right'
  fontSize?: number

  // 边框与装饰
  stroke?: string
  strokeWidth?: number
  radius?: number  // 圆形/圆角半径
  points?: number[] // 线条专用 [x1,y1,x2,y2,...]

  // 元素分类（用于编辑器过滤非交互装饰元素）
  name?: string // 'decor' | 'arrangement-decor' = 不可选中的装饰元素

  // 🆕 v6: 排列多样性元数据
  arrangement?: string  // 排列格式名称 (vertical, card_grid, timeline, ...)
  groupId?: string      // 同组元素共享 ID（用于组选择和组拖拽）
  groupIndex?: number   // 组内序号（0-based）

  // 图片裁剪 (非破坏性，相对图片自身的裁剪区域)
  clipX?: number
  clipY?: number
  clipWidth?: number
  clipHeight?: number
}

export interface CanvasState {
  slides: { [pageNumber: number]: CanvasElement[] }
  activePage: number
  selectedElementIds: string[]
  editingElementId: string | null
  clipboard: CanvasElement | null
  clipModeElementId: string | null
  copiedSlide: CanvasElement[] | null

  // ─── 现有 Actions ──────────────────────────────────────────
  updateElement: (page: number, id: string, attrs: Partial<CanvasElement>) => void
  addElement: (page: number, element: Omit<CanvasElement, 'id'>) => void
  deleteElement: (page: number, id: string) => void
  setSlides: (slides: { [pageNumber: number]: CanvasElement[] }) => void
  setActivePage: (page: number) => void

  // ─── 新增 Actions ──────────────────────────────────────────
  setSelectedElements: (ids: string[]) => void
  setEditingElement: (id: string | null) => void
  duplicateSlide: (page: number) => void
  copyElement: (id: string) => void
  pasteElement: (page: number) => void
  moveLayer: (page: number, id: string, direction: 'up' | 'down' | 'top' | 'bottom') => void
  setClipMode: (elementId: string | null) => void
  copySlide: (page: number) => void
  pasteSlide: (afterPage: number) => void
}

// ══════════════════════════════════════════════════════════════
// Store 实现（temporal 包裹 → 自动 Undo/Redo）
// ══════════════════════════════════════════════════════════════

export const useCanvasStore = create<CanvasState>()(
  temporal(
    (set, get) => ({
      slides: {},
      activePage: 0,
      selectedElementIds: [],
      editingElementId: null,
      clipboard: null,
      clipModeElementId: null,
      copiedSlide: null,

      // ─── 现有 Actions ────────────────────────────────────
      updateElement: (page, id, attrs) =>
        set((state) => {
          const pageElements = state.slides[page] || []
          return {
            slides: {
              ...state.slides,
              [page]: pageElements.map((el) =>
                el.id === id ? { ...el, ...attrs } : el,
              ),
            },
          }
        }),

      addElement: (page, el) =>
        set((state) => {
          const pageElements = state.slides[page] || []
          const newEl: CanvasElement = {
            ...el,
            id: Math.random().toString(36).substring(2, 11),
          }
          return {
            slides: {
              ...state.slides,
              [page]: [...pageElements, newEl],
            },
          }
        }),

      deleteElement: (page, id) =>
        set((state) => {
          const pageElements = state.slides[page] || []
          return {
            slides: {
              ...state.slides,
              [page]: pageElements.filter((el) => el.id !== id),
            },
          }
        }),

      setSlides: (slides) => set({ slides }),

      setActivePage: (page) =>
        set({
          activePage: page,
          selectedElementIds: [],
          editingElementId: null,
        }),

      // ─── 新增 Actions ────────────────────────────────────
      setSelectedElements: (ids) => set({ selectedElementIds: ids }),

      setEditingElement: (id) => set({ editingElementId: id }),

      duplicateSlide: (page) =>
        set((state) => {
          const sourceElements = state.slides[page] || []
          // 深拷贝所有元素并生成新 id
          const cloned = sourceElements.map((el) => ({
            ...JSON.parse(JSON.stringify(el)),
            id: Math.random().toString(36).substring(2, 11),
          }))
          // 重建 slides，插入新页
          const newSlides: { [p: number]: CanvasElement[] } = {}
          const pages = Object.keys(state.slides)
            .map(Number)
            .sort((a, b) => a - b)
          for (let i = pages.length - 1; i >= 0; i--) {
            const p = pages[i]
            if (p > page) {
              newSlides[p + 1] = state.slides[p]
            } else {
              newSlides[p] = state.slides[p]
            }
          }
          newSlides[page + 1] = cloned
          return { slides: newSlides, activePage: page + 1 }
        }),

      copyElement: (id) =>
        set((state) => {
          // 从所有页面中查找元素
          for (const elements of Object.values(state.slides)) {
            const found = elements.find((el) => el.id === id)
            if (found) {
              return { clipboard: JSON.parse(JSON.stringify(found)) }
            }
          }
          return {}
        }),

      pasteElement: (page) =>
        set((state) => {
          if (!state.clipboard) return {}
          const cloned: CanvasElement = {
            ...JSON.parse(JSON.stringify(state.clipboard)),
            id: Math.random().toString(36).substring(2, 11),
            x: state.clipboard.x + 20,
            y: state.clipboard.y + 20,
          }
          const pageElements = state.slides[page] || []
          return {
            slides: {
              ...state.slides,
              [page]: [...pageElements, cloned],
            },
            selectedElementIds: [cloned.id],
          }
        }),

      moveLayer: (page, id, direction) =>
        set((state) => {
          const pageElements = [...(state.slides[page] || [])]
          const idx = pageElements.findIndex((el) => el.id === id)
          if (idx === -1) return {}

          const [item] = pageElements.splice(idx, 1)
          switch (direction) {
            case 'up':
              pageElements.splice(Math.min(idx + 1, pageElements.length), 0, item)
              break
            case 'down':
              pageElements.splice(Math.max(idx - 1, 0), 0, item)
              break
            case 'top':
              pageElements.push(item)
              break
            case 'bottom':
              pageElements.unshift(item)
              break
          }
          return {
            slides: { ...state.slides, [page]: pageElements },
          }
        }),

      setClipMode: (elementId) => set({ clipModeElementId: elementId }),

      copySlide: (page) =>
        set((state) => {
          const sourceElements = state.slides[page] || []
          const cloned = sourceElements.map((el) =>
            JSON.parse(JSON.stringify(el)),
          )
          return { copiedSlide: cloned }
        }),

      pasteSlide: (afterPage) =>
        set((state) => {
          if (!state.copiedSlide) return {}
          const cloned = state.copiedSlide.map((el) => ({
            ...JSON.parse(JSON.stringify(el)),
            id: Math.random().toString(36).substring(2, 11),
          }))
          const newSlides: { [p: number]: CanvasElement[] } = {}
          const pages = Object.keys(state.slides)
            .map(Number)
            .sort((a, b) => a - b)
          for (let i = pages.length - 1; i >= 0; i--) {
            const p = pages[i]
            if (p > afterPage) {
              newSlides[p + 1] = state.slides[p]
            } else {
              newSlides[p] = state.slides[p]
            }
          }
          newSlides[afterPage + 1] = cloned
          return { slides: newSlides, activePage: afterPage + 1 }
        }),

    }),
    {
      limit: 50, // 最多保留 50 步历史
      partialize: (state) => ({
        // 只记录 slides 和 activePage 的历史，忽略选中/编辑状态
        slides: state.slides,
        activePage: state.activePage,
      }),
    },
  ),
)
