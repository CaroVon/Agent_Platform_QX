/**
 * Presentation DSL 类型 —— 与 agent-platform schemas/presentation.py 同步（P2/P4）
 */

export type ComponentType =
  | 'metric' | 'text' | 'chart' | 'table' | 'card'
  | 'timeline' | 'matrix' | 'quote' | 'image'

export type PageType =
  | 'cover' | 'executive_summary' | 'market_overview'
  | 'competitor_matrix' | 'user_persona' | 'user_journey'
  | 'feature_priority' | 'product_architecture' | 'roadmap' | 'conclusion'

export type LayoutId =
  | 'cover' | 'summary' | 'market' | 'matrix' | 'persona'
  | 'journey' | 'features' | 'architecture' | 'roadmap' | 'closing'

export interface PresentationTheme {
  id: string
  name?: string
  palette?: Record<string, string>
  font_scale?: number
}

export interface PresentationComponent {
  id: string
  type: ComponentType
  data: Record<string, unknown>
  emphasis?: 'low' | 'normal' | 'high'
}

export interface PresentationPage {
  id: string
  type: PageType
  layout: LayoutId
  title: string
  subtitle?: string | null
  insight?: string | null
  components: PresentationComponent[]
}

export interface PresentationDSL {
  title: string
  theme?: PresentationTheme
  pages: PresentationPage[]
}

// ─── Critic 评审结果（P5） ─────────────────────────────────

export interface CritiqueIssue {
  page_id?: string | null
  type:
    | 'content_density' | 'information_hierarchy' | 'layout_consistency'
    | 'visual_variety' | 'text_overflow' | 'duplicate_information'
  severity: 'high' | 'medium' | 'low'
  description: string
}

export interface QualityGateReport {
  passed: boolean
  errors: string[]
  warnings: string[]
  checks: Record<string, boolean>
}
