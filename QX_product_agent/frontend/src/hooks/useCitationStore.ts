/**
 * ============================================================
 * useCitationStore —— 引用角标点击状态管理
 *
 * 当用户在编辑器中点击 `<sup class="citation-badge">` 时，
 * 更新 `activeCitationId`，右侧 CitationsPanel 响应展示详情。
 *
 * 使用方式：
 * ```tsx
 * const { activeCitationId, setActiveCitationId } = useCitationStore()
 * ```
 * ============================================================
 */

import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

// ─── 接口 ──────────────────────────────────────────────────────

interface CitationState {
  /** 当前选中的引用编号（null = 无选中） */
  activeCitationId: string | null
  /** 设置选中引用 */
  setActiveCitationId: (id: string | null) => void
  /** 清除选中 */
  clearCitation: () => void
}

// ─── Store ─────────────────────────────────────────────────────

export const useCitationStore = create<CitationState>()(
  subscribeWithSelector((set) => ({
    activeCitationId: null,
    setActiveCitationId: (id) => set({ activeCitationId: id }),
    clearCitation: () => set({ activeCitationId: null }),
  })),
)
