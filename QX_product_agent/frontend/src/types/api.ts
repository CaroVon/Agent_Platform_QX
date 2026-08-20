/**
 * ============================================================
 * 后端 API 类型定义
 * —— 与 research_agent/backend/app/schemas/__init__.py 一致
 *     新增：状态机枚举、大纲审批、DocumentBlock、SSE 事件
 * ============================================================
 */

// ─── 通用 ──────────────────────────────────────────────────────

export interface MessageResponse {
  detail: string
}

// ─── 项目 (Project) ────────────────────────────────────────────

export interface ProjectCreateRequest {
  topic: string
  template_type?: string  // 模板类型："product"（默认）或 "design"
  search_depth?: number   // 搜索强度：5=快速, 10=标准, 15=深度, 20=极致
  images_per_page?: number  // 每页自动搜索图片数量：0=关闭, 默认 2
}

export interface ProjectResponse {
  id: string
  topic: string
  status: ProjectStatusEnum
  template_type: string  // 模板类型："product" 或 "design"
  outline_content: string | null
  pdf_path: string | null
  md_path: string | null
  error_message: string | null
  search_depth: number
  logo_url: string | null
  created_at: string
  updated_at: string | null
}

/**
 * 状态机枚举 —— 与后端 ProjectStatus 一一对应
 *
 * 状态流转:
 *   preparing_data
 *     → waiting_for_sources (🛑 等待用户审核资料)
 *       → preparing_outline (用户确认资料后，生成大纲)
 *         → waiting_for_outline (🛑 等待用户确认大纲)
 *           → drafting (用户确认大纲后开始撰写)
 *             → completed
 *   any → failed
 */
export type ProjectStatusEnum =
  | 'preparing_data'
  | 'waiting_for_sources'
  | 'preparing_outline'
  | 'waiting_for_outline'
  | 'drafting'
  | 'completed'
  | 'failed'

export interface ProjectCreateResponse {
  project: ProjectResponse
  celery_task_id: string
  message: string
}

// ─── 资料审核 (Source Review) ───────────────────────────────────

export interface SourceItem {
  index: number
  title: string
  url: string
  snippet: string
  selected: boolean
}

export interface SourcesListResponse {
  project_id: string
  topic: string
  sources: SourceItem[]
  total_count: number
}

export interface SourceReviewRequest {
  selected_urls: string[]
  additional_notes?: string
}

export interface SourceReviewResponse {
  project_id: string
  new_status: string
  message: string
  kept_sources: number
  celery_task_id: string | null
}

// ─── 大纲审批 (Outline Approval) ───────────────────────────────

export interface OutlineApproveRequest {
  outline: string
}

export interface OutlineApproveResponse {
  project_id: string
  new_status: string
  message: string
  sections_count: number
  celery_task_id: string | null
}

// ─── 任务 (Task) ───────────────────────────────────────────────

export interface TaskResponse {
  id: string
  task_type: TaskTypeEnum
  status: TaskStatusEnum
  sequence_order: number
  section_title: string | null
  retry_count: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

/**
 * TaskType 枚举 —— 必须与 backend/app/models/task.py 的 TaskType 值严格一致。
 * 后端为 source of truth；若新增枚举值需两边同步更新。
 */
export type TaskTypeEnum =
  | 'search'
  | 'build_knowledge_base'
  | 'generate_outline'
  | 'write_section'
  | 'build_report'
  | 'generate_pdf'
  | 'image_generation'

export type TaskStatusEnum =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'

export interface ProgressInfo {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  percentage: number
}

export interface CurrentStep {
  step: string
  message: string
  icon: string | null
  level: string
}

export interface ProjectStatusResponse {
  project_id: string
  topic: string
  project_status: ProjectStatusEnum
  template_type: string
  outline_content: string | null
  pdf_path: string | null
  search_depth: number
  images_per_page: number
  logo_url: string | null
  current_step: CurrentStep | null
  progress: ProgressInfo
  tasks: TaskResponse[]
}

// ─── 文档块 (DocumentBlock) ────────────────────────────────────

export interface DocumentBlockResponse {
  id: string
  section_title: string
  order_index: number
  content: string
  citations: string | null
  created_at: string
  updated_at: string | null
}

export interface DocumentBlockListResponse {
  project_id: string
  blocks: DocumentBlockResponse[]
}

// ─── 文档 (Document) ───────────────────────────────────────────

export interface DocumentResponse {
  id: string
  section_title: string
  section_order: number
  version: number
  content: string
  source_urls: string | null
  created_at: string
}

// ─── 下载 ──────────────────────────────────────────────────────

export interface DownloadResponse {
  project_id: string
  topic: string
  download_url: string
  filename: string
  file_size_bytes: number | null
  report_ready: boolean
}

// ─── 编辑器 AI 改写 (Editor Revise) ────────────────────────────

// ─── 🆕 项目时间轴日志 (ProjectLog) ───────────────────────────────

export interface ProjectLogResponse {
  id: string
  sequence: number
  level: 'info' | 'warn' | 'error' | 'milestone'
  step: string
  message: string
  icon: string | null
  created_at: string
}

export interface ProjectLogListResponse {
  project_id: string
  logs: ProjectLogResponse[]
  total_count: number
}

/** 编辑器 AI 改写请求 */
export interface EditorReviseRequest {
  /** 选中的文本内容 */
  selected_text: string
  /** 改写指令（如 "扩写", "精简", "润色"） */
  instruction: string
  /** 上下文：选中文本前后的完整段落内容（供 AI 参考语境） */
  context?: string
}

/** 编辑器 AI 改写响应 */
export interface EditorReviseResponse {
  /** AI 改写后的新文本 */
  revised_text: string
}

// ─── 报告内容 (Report Content) ──────────────────────────────────

export interface ReportContentResponse {
  project_id: string
  topic: string
  sections: SectionContent[]
}

export interface SectionContent {
  title: string
  order: number
  content: string
  citations: Record<string, string>
}

// ─── 前端自定义类型 ────────────────────────────────────────────

/**
 * 从后端 document 的 source_urls JSON 字符串解析出的引用映射
 * { "1": "https://example.com/article1", "2": "https://example.com/article2" }
 */
export interface CitationMap {
  [key: string]: string
}

/**
 * 章节与溯源信息的组合
 */
export interface SectionWithCitations {
  section: DocumentResponse
  citationMap: CitationMap
  /** 渲染后的章节标题（如 "1. 产品设计理念"） */
  renderedTitle: string
}

/**
 * 任务步骤标签映射 —— 用于进度指示器
 */
export const TASK_STEP_LABELS: Record<TaskTypeEnum, string> = {
  search: '数据采集',
  build_knowledge_base: '构建知识库',
  generate_outline: '规划大纲',
  write_section: 'AI 撰写中',
  image_generation: '生成图表',
  build_report: '报告排版',
  generate_pdf: 'PDF 渲染',
}

/**
 * 状态机步骤标签（含交互节点标记）
 */
export const STATE_MACHINE_STEPS = [
  { status: 'preparing_data' as ProjectStatusEnum, label: '资料搜索', icon: '🔍', interactive: false },
  { status: 'waiting_for_sources' as ProjectStatusEnum, label: '审核资料', icon: '📋', interactive: true },
  { status: 'preparing_outline' as ProjectStatusEnum, label: '大纲生成', icon: '📝', interactive: false },
  { status: 'waiting_for_outline' as ProjectStatusEnum, label: '确认大纲', icon: '📋', interactive: true },
  { status: 'drafting' as ProjectStatusEnum, label: 'AI 撰写中', icon: '✍️', interactive: false },
  { status: 'completed' as ProjectStatusEnum, label: '报告完成', icon: '✅', interactive: false },
] as const

/**
 * 任务进度指示器的核心步骤（按后端定义的 sequence_order）
 */
export const PROGRESS_STEPS = [
  { type: 'search' as TaskTypeEnum, label: '搜集资料', icon: '🔍' },
  { type: 'build_knowledge_base' as TaskTypeEnum, label: '知识库', icon: '📚' },
  { type: 'generate_outline' as TaskTypeEnum, label: '规划大纲', icon: '📋' },
  { type: 'write_section' as TaskTypeEnum, label: 'AI 撰写', icon: '✍️' },
  { type: 'build_report' as TaskTypeEnum, label: '报告排版', icon: '📄' },
  { type: 'generate_pdf' as TaskTypeEnum, label: 'PDF 输出', icon: '📕' },
] as const

// ─── 🆕 侧边栏 AI 对话 (Editor Chat SSE) ──────────────────────────

export interface EditorChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface EditorChatRequest {
  project_id: string
  chat_mode: 'chat' | 'work'
  message: string
  selected_text?: string | null
  history: EditorChatMessage[]
}

// ─── 🆕 手动导出 PDF ───────────────────────────────────────────

export interface ExportPdfRequest {
  html_content: string
}

// ─── 🆕 本地上传文档 ──────────────────────────────────────────

export interface UploadDocsResponse {
  project_id: string
  chunk_count: number
  message: string
}

// ─── 🆕 图片搜索 (Image Search) ─────────────────────────────────

export interface ImageSearchRequest {
  query: string
  max_results?: number
  search_depth?: number
  page_number?: number  // 关联页码（自动搜索时由后端传入）
}

export interface ImageResult {
  id: string
  query: string
  title: string
  image_url: string
  source_url: string | null
  search_depth: number
  page_number: number | null  // 关联页码，手动搜索为 null
  created_at: string
}

export interface ImageSearchResponse {
  images: ImageResult[]
  total_count: number
}

export interface ProjectImagesResponse {
  project_id: string
  images: ImageResult[]
  total_count: number
}

// ─── 🆕 知识系统 (P1-P3)：图片知识库 / 三层检索 / 相似任务 / 领域经验 ──

/** 图片分析状态：pending 待分析 / analyzing 分析中 / ready 已入库 / failed 失败 */
export type KbImageStatus = 'pending' | 'analyzing' | 'ready' | 'failed'

/** 知识库图片（含 MiniMax VL 分析结果） */
export interface KbImage extends ImageResult {
  source: 'search' | 'upload'
  status: KbImageStatus | null
  analysis_text: string | null   // VL 结构化 JSON
  tags: string[]                 // 分析标签
}

/** 上传图片入库响应 */
export interface KbImageUploadResponse {
  project_id: string
  saved: { image_id: string; title: string; status: string }[]
  errors: string[]
  message: string
}

/** 三层融合检索命中项 */
export interface KnowledgeSearchHit {
  scope: string          // task / domain:xxx / global / document
  content: string
  source_url: string
  score: number
  title?: string
  project_topic?: string
}

export interface KnowledgeSearchResponse {
  query: string
  scope: string
  total: number
  hits: KnowledgeSearchHit[]
}

/** 相似任务条目（L1 领域知识） */
export interface SimilarProject {
  project_id: string
  topic: string
  template_type: string
  similarity: number
  status: string
  domain_tags: string[]
}

export interface SimilarProjectsResponse {
  project_id: string
  topic: string
  threshold: number
  similar_projects: SimilarProject[]
  borrowable_experience: string
}

/** 知识资产登记条目 */
export interface KnowledgeAsset {
  id: string
  scope: string
  source: 'upload' | 'obsidian' | 'experience' | string
  title: string
  source_url: string | null
  tags: string[]
  chunk_count: number
  version: number
  stale_at: string | null
  created_at: string
}

export interface KnowledgeAssetListResponse {
  total: number
  assets: KnowledgeAsset[]
}

/** 领域经验包 */
export interface DomainExperience {
  id: string
  project_id: string
  topic: string
  domain_tags: string[]
  summary: string
  source_url: string | null
  created_at: string
}

export interface DomainExperienceListResponse {
  total: number
  experiences: DomainExperience[]
}

// ─── Memory Graph (v2 Studio) ─────────────────────────────────

export type MemoryEntityType =
  | 'company'
  | 'product'
  | 'technology'
  | 'person'
  | 'market'
  | 'metric'
  | 'other'

export interface MemoryGraphNode {
  id: string
  name: string
  type: MemoryEntityType
  scope: 'global' | 'project'
  degree: number
  confidence: number
  summary?: string
  aliases: string[]
  focused?: boolean
  last_seen_at?: string | null
}

export interface MemoryGraphEdge {
  source: string
  target: string
  relation: string
  weight: number
  expired?: boolean
}

export interface MemoryGraphResponse {
  nodes: MemoryGraphNode[]
  edges: MemoryGraphEdge[]
  query?: string
  meta: {
    entity_count: number
    relation_count: number
    projects_covered: number
    studio_products_covered?: number
    truncated?: boolean
  }
}

export interface MemoryEntityDetail {
  id: string
  name: string
  type: MemoryEntityType
  scope: 'global' | 'project'
  summary?: string
  aliases?: string[]
  /** 后端契约（/memory/entities/{id}）：{relation_id, relation, direction, other} */
  relations?: Array<{
    relation_id?: string
    relation: string
    direction?: 'out' | 'in'
    other?: { id: string; name: string; type?: MemoryEntityType }
  }>
  sources?: Array<{ url?: string; title?: string }>
}

export interface MemoryInsightsResponse {
  insights: Array<{ id: string; content: string; source: string }>
}
