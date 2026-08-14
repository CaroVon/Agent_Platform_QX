/**
 * ============================================================
 * 工作台类型定义
 * —— 面向三栏工作台、Tiptap 编辑器、大纲确认流程
 * ============================================================
 */
// @ts-nocheck

import type {
  ProjectStatusEnum,
  DocumentBlockResponse,
  TaskResponse,
} from './api'

// ─── 重新导出 api 类型以统一入口 ──────────────────────────────
export type {
  ProjectStatusEnum,
  DocumentBlockResponse,
  TaskResponse,
}
export type {
  ProjectResponse,
  ProjectCreateRequest,
  ProjectCreateResponse,
  ProjectStatusResponse,
  SourceItem,
  SourcesListResponse,
  SourceReviewRequest,
  SourceReviewResponse,
  OutlineApproveRequest,
  OutlineApproveResponse,
  DocumentBlockListResponse,
  ProgressInfo,
  DownloadResponse,
  CitationMap,
  SectionWithCitations,
  TaskTypeEnum,
  TaskStatusEnum,
} from './api'

// ─── 大纲章节节点 ──────────────────────────────────────────────
/** 从大纲 Markdown 解析出的单个章节 */
export interface OutlineSection {
  /** 章节标题（不含 ## 前缀） */
  title: string
  /** 原始 Markdown 行（含 ##） */
  raw: string
  /** 从 0 开始的排序索引 */
  index: number
}

// ─── DocumentBlock 扩展（前端渲染用） ──────────────────────────
/** 带前端渲染状态的文档块 */
export interface EditorBlock extends DocumentBlockResponse {
  /** 是否正在通过 SSE 流式接收（闪烁占位动画） */
  isStreaming: boolean
  /** Tiptap JSON 内容（从 Markdown 转换而来） */
  jsonContent?: Record<string, unknown>
}

// ─── SSE 草稿事件 ─────────────────────────────────────────────
/** SSE stream-draft 推送的 section_chunk 事件负载 */
export interface SSESectionChunk {
  event: 'section_chunk'
  data: {
    section_title: string
    order_index: number
    content: string
    citations: Record<string, string> | null
  }
}

/** SSE draft_complete 事件 */
export interface SSEDraftComplete {
  event: 'draft_complete'
  data: {
    project_id: string
    total_blocks: number
  }
}

export type SSEDraftEvent = SSESectionChunk | SSEDraftComplete

// ─── 工作台视图状态 ────────────────────────────────────────────
/** 右侧面板视图模式 */
export type RightPanelView = 'closed' | 'citations' | 'agent-chat' | 'logs'

/** 工作台整体状态 */
export interface WorkspaceState {
  /** 项目核心状态 */
  projectStatus: ProjectStatusEnum
  /** 右侧面板 */
  rightPanel: RightPanelView
  /** 是否显示大纲确认横幅 */
  showOutlineApproval: boolean
  /** 当前选中的章节标题（左栏高亮） */
  activeSectionTitle: string | null
}
