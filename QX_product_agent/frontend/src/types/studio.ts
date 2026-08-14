/**
 * ============================================================
 * AI Product Studio 类型定义
 * —— 与 agent-platform 的 Pydantic Schemas 保持同步
 *    （research / product / design / presentation 四类结构化资产）
 * ============================================================
 */

export type StudioStatus = 'queued' | 'running' | 'completed' | 'failed'

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

export interface MarketResearch {
  market_size: MarketSizeInfo
  competitors: CompetitorInfo[]
  customer_pain_points: string[]
  industry_trends: string[]
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
}

// ─── 演示（Presentation Agent → SlideDeck / Slide JSON） ─────

export type SlideBlockType =
  | 'title'
  | 'subtitle'
  | 'text'
  | 'bullets'
  | 'metric'
  | 'quote'
  | 'table'
  | 'image'

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
  requirement?: Record<string, unknown> | null
  research?: MarketResearch | null
  competitor_analysis?: CompetitorAnalysis | null
  strategy?: ProductStrategy | null
  design?: UXDesign | null
  presentation?: SlideDeck | null
  node_status: Record<string, string>
  errors: Record<string, string>
}

export interface ExportPdfResponse {
  product_id: string
  pdf_url: string
  message: string
}
