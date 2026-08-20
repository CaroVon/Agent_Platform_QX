/**
 * ============================================================
 * AI Product Studio 类型定义
 * —— 与 agent-platform 的 Pydantic Schemas 保持同步
 *    （research / product / design / presentation 四类结构化资产）
 * ============================================================
 */

export type StudioStatus =
  | 'queued'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'waiting_approval'

export type KeywordGroups = Record<string, string[]>

export type SuggestionResponse = {
  suggestions: string[]
}

export type ClarifyRequest = {
  idea: string
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
  max_rounds?: number
}

export interface StudioProductCreateResponse {
  product_id: string
  idea: string
  status: StudioStatus
}

// ─── 市场研究（Research Agent → MarketResearch） ─────────────

export interface MarketSizeInfo {
  summary: string
  tam?: string | null
  sam?: string | null
  som?: string | null
  cagr?: string | null
  source?: string | null
}

export interface CompetitorInfo {
  name: string
  url?: string | null
  positioning?: string | null
}

export interface SourceRef {
  url: string
  title?: string
  weight?: number
}

export interface MarketResearch {
  market_size: MarketSizeInfo
  competitors: CompetitorInfo[]
  customer_pain_points: string[]
  industry_trends: string[]
  sources?: SourceRef[]
}

// ─── 竞品分析（Competitor Analysis → CompetitorAnalysis） ────

export interface CompetitorProfile {
  name: string
  positioning?: string
  target_segment?: string | null
  pricing?: string | null
  strengths: string[]
  weaknesses: string[]
  threat_level: 'high' | 'medium' | 'low'
}

export interface CompetitorMatrixInfo {
  dimensions: string[]
  profiles: CompetitorProfile[]
}

export interface CompetitorAnalysis {
  competitors: CompetitorProfile[]
  matrix: CompetitorMatrixInfo
  competitive_landscape: string
  differentiation_opportunities: string[]
}

// ─── 产品策略（Product Agent → ProductStrategy） ─────────────

export interface Persona {
  name: string
  role?: string
  goals: string[]
  pain_points: string[]
  behavior?: string | null
}

export interface Feature {
  name: string
  description?: string
  category?: string | null
  priority: 'P0' | 'P1' | 'P2'
}

export interface RoadmapItem {
  phase: string
  title: string
  goal?: string | null
  timeline?: string | null
  milestones: string[]
}

export interface PRDSection {
  title: string
  content: string
}

export interface ProductStrategy {
  positioning: string
  personas: Persona[]
  features: Feature[]
  roadmap: RoadmapItem[]
  prd_sections: PRDSection[]
  sources?: SourceRef[]
}

// ─── UX 设计（Design Agent → UXDesign） ──────────────────────

export interface UserFlowStep {
  step: string
  description?: string
  is_entry?: boolean
  is_exit?: boolean
}

export interface PageSpec {
  name: string
  purpose?: string | null
  key_elements: string[]
}

export interface ComponentSpec {
  name: string
  kind?: string
  description?: string | null
}

export interface UXDesign {
  user_flow: UserFlowStep[]
  pages: PageSpec[]
  components: ComponentSpec[]
  sources?: SourceRef[]
}

// ─── 演示（P2/P4: Presentation DSL；旧 SlideDeck 见下方兼容类型） ──

import type {
  PresentationDSL,
  QualityGateReport,
} from '@/types/presentation'

// @deprecated 旧版 SlideDeck（P2 前资产包，兼容展示用）
export type SlideBlockType =
  | 'title' | 'subtitle' | 'text' | 'bullets'
  | 'metric' | 'quote' | 'table' | 'image'

export interface SlideBlock {
  id: string
  block_type: SlideBlockType
  content: string
  emphasis?: 'low' | 'normal' | 'high'
  meta?: Record<string, unknown>
}

export interface Slide {
  id: string
  title: string
  subtitle?: string | null
  layout_type: string
  blocks: SlideBlock[]
  visual_metadata?: Record<string, unknown>
}

export interface DeckSection {
  title: string
  slide_ids: string[]
}

export interface SlideDeck {
  topic: string
  slides: Slide[]
  sections: DeckSection[]
}

// ─── 资产包（GET /api/v1/product/{id} 响应） ─────────────────

export interface StudioProduct {
  product_id: string
  idea: string
  status: StudioStatus
  error_message?: string | null
  created_at?: string | null
  updated_at?: string | null
  keywords?: KeywordGroups | null
  node_status?: Record<string, string>
  node_models?: Record<string, string>
  errors?: Record<string, string>
  requirement?: Record<string, unknown> | null
  research?: MarketResearch | null
  competitor_analysis?: CompetitorAnalysis | null
  strategy?: ProductStrategy | null
  design?: UXDesign | null
  document?: Record<string, unknown> | null
  presentation?: PresentationDSL | SlideDeck | null
  ppt_design?: {
    project_dir?: string
    pptx_path?: string
    pptx_relative?: string
    pages?: number
    created_at?: string
    svg_files?: string[]
    /** 后端 ppt-master 的最终 SVG 缩略图 URL */
    svg_previews?: string[]
    images?: Array<{ name: string; url: string; size: number }>
    model?: string
    design_brief?: string
    status?: string
    /** P7: 资产对账恢复标记 —— 表示此 ppt_design 由磁盘 ppt_projects 恢复而来 */
    recovered?: boolean
  } | null
  critic_score?: number | null
  gate_report?: QualityGateReport | null
}

export interface ExportPdfResponse {
  product_id: string
  pdf_url: string
  message: string
}

/** P7: PPT 资产库索引项（GET /api/v1/product/ppt-assets 响应） */
export interface PptAssetIndexEntry {
  folder_name: string
  title: string
  pptx_url: string
  size: number
  svg_count: number
  created_at?: string | null
  svg_previews: string[]
}

// ─── Design Studio v2（任务级「设计思路 + 图片」资产库） ──────

export type DesignStudioItemKind = 'standalone' | 'component' | 'composite'

export interface DesignStudioImage {
  name: string
  url: string
  size: number
}

export interface DesignStudioVersion {
  ts: string
  text: string
  prompt: string
  image: DesignStudioImage | null
}

export interface DesignStudioItem {
  id: string
  kind: DesignStudioItemKind
  name: string
  /** 设计思路（用户可编辑，重新生图时作为 prompt 主体） */
  text: string
  /** 实际发送给生图模型的完整 prompt（只读） */
  prompt: string
  /** 生图模型返回的文本输出（如 MiniMax data.text，无则 null） */
  api_text: string | null
  image: DesignStudioImage | null
  source: 'pipeline' | 'user'
  parent: string | null
  children: string[]
  created_at: string
  updated_at: string
  versions: DesignStudioVersion[]
}

export interface DesignStudioLibrary {
  schema_version: number
  product_id: string
  idea: string
  status: string
  created_at: string
  updated_at: string
  items: DesignStudioItem[]
}
