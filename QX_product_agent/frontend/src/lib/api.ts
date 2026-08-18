/**
 * ============================================================
 * API 服务层
 * —— 基于 fetch 封装，对接后端 FastAPI
 * ============================================================
 */

import type {
  ProjectCreateRequest,
  ProjectCreateResponse,
  ProjectResponse,
  ProjectStatusResponse,
  SourcesListResponse,
  SourceReviewRequest,
  SourceReviewResponse,
  OutlineApproveRequest,
  OutlineApproveResponse,
  DocumentBlockListResponse,
  DownloadResponse,
  ReportContentResponse,
  EditorReviseRequest,
  EditorReviseResponse,
  EditorChatRequest,
  ExportPdfRequest,
  UploadDocsResponse,
  ImageResult,
  ImageSearchResponse,
  ProjectImagesResponse,
  KbImageUploadResponse,
  KnowledgeSearchResponse,
  SimilarProjectsResponse,
  KnowledgeAssetListResponse,
  DomainExperienceListResponse,
} from '@/types/api'
import type {
  ExportPdfResponse,
  PptAssetIndexEntry,
  StudioProduct,
  StudioProductCreateResponse,
  DesignStudioLibrary,
  DesignStudioItem,
} from '@/types/studio'
import type { PresentationDSL } from '@/types/presentation'

/**
 * API 基础路径（Netlify 部署适配）
 *
 * - 默认相对路径 /api/v1：走 Netlify Edge Function（api-proxy）转发到 BACKEND_URL
 *   （本机后端经隧道暴露公网，或 netlify dev 本地联调指向 localhost:8000）
 * - 可选环境变量 VITE_API_BASE：构建时覆盖为直连地址（需后端开启 CORS）
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

function productIdempotencyKey(idea: string): string {
  const normalized = idea.trim().replace(/\s+/g, ' ').toLocaleLowerCase()
  let hash = 2166136261
  for (let index = 0; index < normalized.length; index += 1) {
    hash ^= normalized.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `idea-${hash >>> 0}`
}

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API Error [${status}]: ${detail}`)
    this.name = 'ApiError'
  }
}

// ─── 认证（Bearer token）──────────────────────────────────────
// 单用户工作区模型：首次启动通过 /auth/bootstrap 免密获取 token
// （后端 AUTH_BOOTSTRAP=true 时；生产环境关闭后需接入登录页）。
const TOKEN_KEY = 'qx-auth-token'

let _tokenPromise: Promise<string> | null = null

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

async function bootstrapToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/bootstrap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    throw new ApiError(res.status, `auth bootstrap 失败: ${res.status}`)
  }
  const body = (await res.json()) as { access_token: string }
  setAuthToken(body.access_token)
  return body.access_token
}

/** 获取有效 token：已有则复用；没有则 bootstrap 一次（并发去重）。 */
export async function ensureAuthToken(): Promise<string> {
  const existing = getAuthToken()
  if (existing) return existing
  if (!_tokenPromise) {
    _tokenPromise = bootstrapToken().finally(() => {
      _tokenPromise = null
    })
  }
  return _tokenPromise
}

async function request<T>(
  url: string,
  options?: RequestInit,
  _retried = false,
): Promise<T> {
  const token = await ensureAuthToken()
  const res = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
    ...options,
  })

  // token 失效（重启换密钥等）：清缓存重试一次
  if (res.status === 401 && !_retried) {
    localStorage.removeItem(TOKEN_KEY)
    return request<T>(url, options, true)
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(res.status, detail)
  }

  return res.json() as Promise<T>
}

// ─── 项目 API ──────────────────────────────────────────────────

export const projectsApi = {
  /** 获取项目列表 */
  list(skip = 0, limit = 50): Promise<ProjectResponse[]> {
    return request(`/projects?skip=${skip}&limit=${limit}`)
  },

  /** Canvas 编辑器持久化（Konva slides） */
  saveCanvas(projectId: string, slides: unknown): Promise<{ project_id: string; saved: boolean }> {
    return request(`/projects/${projectId}/canvas`, {
      method: 'POST',
      body: JSON.stringify({ slides }),
    })
  },

  /** 读取 Canvas 持久化数据 */
  getCanvas(projectId: string): Promise<{ project_id: string; slides: Record<string, unknown>; saved_at?: string | null }> {
    return request(`/projects/${projectId}/canvas`)
  },

  /** 创建项目（提交分析主题，触发节点1：资料准备与大纲生成） */
  create(data: ProjectCreateRequest): Promise<ProjectCreateResponse> {
    return request('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 获取项目进度（轮询用） */
  getStatus(projectId: string): Promise<ProjectStatusResponse> {
    return request(`/projects/${projectId}/status`)
  },

  /**
   * 🎯 确认/修改大纲（交互核心节点）
   * 将状态机从 waiting_outline_approval 推进到 drafting，
   * 并触发节点2：分章节异步撰写
   */
  approveOutline(
    projectId: string,
    data: OutlineApproveRequest,
  ): Promise<OutlineApproveResponse> {
    return request(`/projects/${projectId}/approve-outline`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 获取项目的所有文档块（供 Tiptap 编辑器加载） */
  getBlocks(projectId: string): Promise<DocumentBlockListResponse> {
    return request(`/projects/${projectId}/blocks`)
  },

  /** 获取下载链接 */
  getDownload(projectId: string): Promise<DownloadResponse> {
    return request(`/projects/${projectId}/download`)
  },

  /** 🆕 获取报告全文内容（按章节排列，含引用映射） */
  getContent(projectId: string): Promise<ReportContentResponse> {
    return request(`/projects/${projectId}/content`)
  },

  /**
   * 🖥️ 获取项目时间轴日志（支持增量拉取）
   * 前端右侧面板使用此 API 渲染实时终端控制台
   */
  getLogs(projectId: string, afterSequence = 0): Promise<import('@/types/api').ProjectLogListResponse> {
    return request(`/projects/${projectId}/logs?after_sequence=${afterSequence}`)
  },

  /**
   * 🎯 获取资料来源列表（交互节点1）
   * 返回搜索结果的标题、URL、摘要，供用户审核
   */
  getSources(projectId: string): Promise<SourcesListResponse> {
    return request(`/projects/${projectId}/sources`)
  },

  /**
   * 🎯 提交资料审核结果（交互节点1确认）
   * 将筛选后的 URL 列表提交给后端，触发阶段2：大纲生成
   */
  reviewSources(
    projectId: string,
    data: SourceReviewRequest,
  ): Promise<SourceReviewResponse> {
    return request(`/projects/${projectId}/review-sources`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 删除项目及其所有关联数据 */
  delete(projectId: string): Promise<{ detail: string }> {
    return request(`/projects/${projectId}`, {
      method: 'DELETE',
    })
  },

  /** 🆕 上传本地参考文档 (PDF/DOCX/TXT)，逐个上传 */
  async uploadDocs(projectId: string, files: FileList | File[]): Promise<UploadDocsResponse> {
    let totalChunks = 0
    const messages: string[] = []

    for (let i = 0; i < files.length; i++) {
      const formData = new FormData()
      formData.append('file', files[i])

      const res = await fetch(`${API_BASE}/projects/${projectId}/upload-docs`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
        body: formData,
      })

      if (!res.ok) {
        let detail = `HTTP ${res.status}`
        try {
          const body = await res.json()
          detail = body.detail ?? detail
        } catch { /* ignore */ }
        throw new ApiError(res.status, `[${files[i].name}] ${detail}`)
      }

      const result: UploadDocsResponse = await res.json()
      totalChunks += result.chunk_count
      messages.push(result.message)
    }

    return {
      project_id: projectId,
      chunk_count: totalChunks,
      message: messages.length === 1
        ? messages[0]
        : `${messages.length} 个文件上传完成`,
    }
  },

  /** 上传项目 Logo 图片 */
  async uploadLogo(
    projectId: string,
    file: File,
  ): Promise<{ project_id: string; logo_url: string; message: string }> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch(`${API_BASE}/projects/${projectId}/logo`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
      body: formData,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }

    return res.json()
  },

  /** 🆕 手动导出 PDF (前端拼接 HTML/Markdown 内容) */
  exportPdf(projectId: string, data: ExportPdfRequest): Promise<DownloadResponse> {
    return request(`/projects/${projectId}/export-pdf`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 🆕 上传画布图片素材，返回持久化后的公开 URL */
  async uploadAsset(projectId: string, file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch(`${API_BASE}/projects/${projectId}/assets`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
      body: formData,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }

    return res.json()
  },

  /** 🔍 搜索图片（DuckDuckGo），结果持久化到项目图片库 */
  async searchImages(
    projectId: string,
    data: { query: string; max_results?: number; search_depth?: number },
  ): Promise<ImageSearchResponse> {
    return request(`/projects/${projectId}/search-images`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 🖼️ 获取项目图片库（所有已搜索保存的图片） */
  async getProjectImages(
    projectId: string,
  ): Promise<ProjectImagesResponse> {
    return request(`/projects/${projectId}/images`)
  },

  /** 🗑️ 从图片库中删除单张图片 */
  async deleteProjectImage(projectId: string, imageId: string): Promise<{ detail: string }> {
    return request(`/projects/${projectId}/images/${imageId}`, {
      method: 'DELETE',
    })
  },

  // ─── 🆕 知识系统 (P1-P3) ─────────────────────────────────────

  /** 🖼️ 图片知识库入库：上传本地图片并触发 MiniMax VL 异步分析 */
  async uploadKbImages(projectId: string, files: File[]): Promise<KbImageUploadResponse> {
    const formData = new FormData()
    for (const file of files) formData.append('files', file)

    const res = await fetch(`${API_BASE}/projects/${projectId}/kb-images`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
      body: formData,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }
    return res.json()
  },

  /** 🔗 相似任务判别：返回可借用经验的相似历史任务 */
  getSimilar(projectId: string): Promise<SimilarProjectsResponse> {
    return request(`/projects/${projectId}/similar`)
  },
}

// ─── 🆕 知识库 API（三层检索 / 资产 / 领域经验） ─────────────────

export const knowledgeApi = {
  /** 🔍 三层融合检索（L2 任务 + L1 领域 + L0 全局） */
  search(
    q: string,
    opts?: { scope?: string; projectId?: string; k?: number },
  ): Promise<KnowledgeSearchResponse> {
    const params = new URLSearchParams({ q })
    if (opts?.scope) params.set('scope', opts.scope)
    if (opts?.projectId) params.set('project_id', opts.projectId)
    if (opts?.k) params.set('k', String(opts.k))
    return request(`/knowledge/search?${params.toString()}`)
  },

  /** 📦 知识资产登记列表（upload/obsidian/experience） */
  assets(opts?: { scope?: string; source?: string }): Promise<KnowledgeAssetListResponse> {
    const params = new URLSearchParams()
    if (opts?.scope) params.set('scope', opts.scope)
    if (opts?.source) params.set('source', opts.source)
    const qs = params.toString()
    return request(`/knowledge/assets${qs ? `?${qs}` : ''}`)
  },

  /** 🧠 领域经验包列表 */
  domains(): Promise<DomainExperienceListResponse> {
    return request('/knowledge/domains')
  },
}

/**
 * 🌊 SSE 草稿流连接
 *
 * 使用方式:
 * ```typescript
 * const es = projectsApi.connectDraftStream(projectId);
 * es.addEventListener('section_chunk', (e) => {
 *   const block = JSON.parse(e.data);
 *   // 插入 Tiptap 编辑器
 * });
 * es.addEventListener('draft_complete', () => {
 *   es.close();
 * });
 * ```
 */
export function connectDraftStream(projectId: string): EventSource {
  return new EventSource(`${API_BASE}/projects/${projectId}/stream-draft`)
}

// ─── AI Product Studio API ────────────────────────────────────

export const productApi = {
  /** 创建产品：触发 Research → Product → Design → Presentation 流水线（异步） */
  create(idea: string): Promise<StudioProductCreateResponse> {
    return request('/product/create', {
      method: 'POST',
      headers: { 'Idempotency-Key': productIdempotencyKey(idea) },
      body: JSON.stringify({ idea }),
    })
  },

  /** 获取产品资产包（前端轮询直至 status=completed/failed） */
  get(productId: string): Promise<StudioProduct> {
    return request(`/product/${productId}`)
  },

  /** 产品列表 */
  list(skip = 0, limit = 50): Promise<Array<{ product_id: string; idea: string; status: string; created_at?: string | null }>> {
    return request(`/product?skip=${skip}&limit=${limit}`)
  },

  /** 局部重生成资产（instruction 为空则无指导重跑） */
  regenerate(productId: string, asset: string, instruction = ''): Promise<{ product_id: string; asset: string; updated: boolean; versions: number }> {
    return request(`/product/${productId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ asset, instruction }),
    })
  },

  /** 资产版本历史 */
  versions(productId: string): Promise<{ product_id: string; versions: Record<string, Array<{ ts: string }>> }> {
    return request(`/product/${productId}/versions`)
  },

  /** 从版本历史恢复资产 */
  restore(productId: string, asset: string, index: number): Promise<{ product_id: string; asset: string; restored: boolean }> {
    return request(`/product/${productId}/restore`, {
      method: 'POST',
      body: JSON.stringify({ asset, index }),
    })
  },

  /** 待审核资料列表（含权重） */
  getSources(productId: string): Promise<{
    product_id: string
    status: string
    sources: Array<{
      title: string
      url: string
      content?: string
      weight?: number
      weight_label?: string
      weight_detail?: string
      selected?: boolean
      local?: boolean
    }>
    paused_node?: string | null
  }> {
    return request(`/product/${productId}/sources`)
  },

  /** 上传本地资料（作为最高权重补充来源） */
  async uploadSource(productId: string, file: File): Promise<{
    product_id: string
    source: { title: string; url: string; weight_label?: string; selected?: boolean }
    total: number
  }> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_BASE}/product/${productId}/upload-source`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
      body: formData,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new ApiError(res.status, detail)
    }
    return res.json()
  },

  /** 批准暂停节点（Plan/Act 门；source_gathering 可携带 selected_urls） */
  approveNode(productId: string, node: string, selectedUrls?: string[]): Promise<{ product_id: string; node: string; approved: boolean }> {
    return request(`/product/${productId}/approve-node`, {
      method: 'POST',
      body: JSON.stringify(selectedUrls ? { node, selected_urls: selectedUrls } : { node }),
    })
  },

  /** 拒绝暂停节点 */
  rejectNode(productId: string, node: string): Promise<{ product_id: string; node: string; rejected: boolean }> {
    return request(`/product/${productId}/reject-node`, {
      method: 'POST',
      body: JSON.stringify({ node }),
    })
  },

  /** 真实执行事件日志（节点/状态/明细/时间） */
  logs(productId: string): Promise<{ product_id: string; logs: Array<{ ts: string; node: string; status: string; detail?: string }> }> {
    return request(`/product/${productId}/logs`)
  },

  /** 导出演示为 PPT 风格 PDF（Slide JSON → Renderer → WeasyPrint） */
  exportPdf(productId: string): Promise<ExportPdfResponse> {
    return request(`/product/${productId}/export-pdf`, {
      method: 'POST',
    })
  },

  /** 导出单文件 HTML 快照（与网页预览 100% 一致） */
  exportHtml(productId: string): Promise<ExportPdfResponse> {
    return request(`/product/${productId}/export-html`, {
      method: 'POST',
    })
  },

  /** 导出可编辑 PPTX（PptxGenJS） */
  exportPptx(productId: string): Promise<ExportPdfResponse> {
    return request(`/product/${productId}/export-pptx`, {
      method: 'POST',
    })
  },

  /** 更新演示 DSL（编辑器保存） */
  updatePresentation(
    productId: string,
    presentation: PresentationDSL,
  ): Promise<{ detail: string }> {
    return request(`/product/${productId}/presentation`, {
      method: 'PATCH',
      body: JSON.stringify({ presentation }),
    })
  },

  /** 编辑器素材搜索（无状态 DuckDuckGo，结果不持久化） */
  searchImages(
    productId: string,
    body: { query: string; max_results?: number; search_depth?: number },
  ): Promise<{ images: Array<{ id: string; query: string; title: string; image_url: string; source_url: string | null }>; total_count: number }> {
    return request(`/product/${productId}/search-images`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  /** DesignStudio 资产库：列出产品图片资产（生图/上传共用） */
  listAssets(productId: string): Promise<{ assets: Array<{ name: string; url: string; size: number }> }> {
    return request(`/product/${productId}/assets`)
  },

  /** P7: PPT 资产库 —— 扫描磁盘 ppt_projects 的全部 PPT 资产（只读） */
  pptAssets(): Promise<PptAssetIndexEntry[]> {
    return request('/product/ppt-assets')
  },

  /** P7: 该产品在磁盘上的 PPT 资产（即使 asset_package 未记录） */
  pptRecovery(productId: string): Promise<{
    product_id: string
    idea: string
    recovered: StudioProduct['ppt_design'] | null
    native?: string | null
  }> {
    return request(`/product/${productId}/ppt-recovery`)
  },

  /** 编辑器本地上传图片素材，返回公开访问 URL */
  async uploadAsset(productId: string, file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_BASE}/product/${productId}/assets`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
      body: formData,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }
    return res.json()
  },
}

// ─── Design Studio v2 API（任务级「设计思路 + 图片」资产库） ─────

export interface ComponentSuggestion {
  name: string
  text: string
}

export const designStudioApi = {
  /** 读取资产库（后端首次访问时自动导入 pipeline 图片资产） */
  get(productId: string): Promise<DesignStudioLibrary> {
    return request(`/design-studio/${productId}`)
  },

  /** LLM 智能拆解产品组件建议（[{name, text}]，未生成图片） */
  suggestComponents(productId: string): Promise<{ product_id: string; suggestions: ComponentSuggestion[] }> {
    return request(`/design-studio/${productId}/suggest-components`, { method: 'POST' })
  },

  /** 创建条目（standalone / component / composite） */
  createItem(
    productId: string,
    body: { kind: 'standalone' | 'component' | 'composite'; name: string; text?: string; parent?: string; children?: string[] },
  ): Promise<{ product_id: string; item: DesignStudioItem }> {
    return request(`/design-studio/${productId}/items`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  /** 原子创建「组合设计」（组件 + 组合总图条目） */
  createComposite(
    productId: string,
    body: {
      name?: string
      text?: string
      components: Array<{ name: string; text?: string }>
    },
  ): Promise<{ product_id: string; composite: DesignStudioItem; components: DesignStudioItem[] }> {
    return request(`/design-studio/${productId}/composite`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  /** 修改条目名称 / 设计思路（不触发重新生图） */
  updateItem(
    productId: string,
    itemId: string,
    body: { name?: string; text?: string },
  ): Promise<{ product_id: string; item: DesignStudioItem }> {
    return request(`/design-studio/${productId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    })
  },

  /** 按当前文字生成 / 重新生成图片（同步等待生图模型） */
  generate(
    productId: string,
    itemId: string,
  ): Promise<{ product_id: string; item: DesignStudioItem }> {
    return request(`/design-studio/${productId}/items/${itemId}/generate`, { method: 'POST' })
  },

  /** 从版本历史恢复 */
  restore(
    productId: string,
    itemId: string,
    index: number,
  ): Promise<{ product_id: string; item: DesignStudioItem }> {
    return request(`/design-studio/${productId}/items/${itemId}/restore`, {
      method: 'POST',
      body: JSON.stringify({ index }),
    })
  },

  /** 删除条目 */
  deleteItem(productId: string, itemId: string): Promise<{ product_id: string; deleted: string }> {
    return request(`/design-studio/${productId}/items/${itemId}`, { method: 'DELETE' })
  },

  /** 打包下载全部图片（ZIP，带鉴权 → Blob 触发下载） */
  async downloadZip(productId: string): Promise<Blob> {
    const res = await fetch(`${API_BASE}/design-studio/${productId}/download`, {
      headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new ApiError(res.status, detail)
    }
    return res.blob()
  },
}

// ─── 编辑器 AI API ──────────────────────────────────────────────

export const editorApi = {
  /**
   * 🎯 划词改写
   * 将选中文本发送给 AI，返回改写后的内容
   */
  async revise(data: EditorReviseRequest): Promise<EditorReviseResponse> {
    return request('/editor/revise', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /**
   * 🆕 侧边栏 AI 对话（SSE 流式输出）
   *
   * 返回原始 fetch Response，调用方通过 ReadableStream 读取 SSE 事件。
   * 事件类型：content（增量文本）、done（完成）、error（错误）
   */
  async chat(data: EditorChatRequest): Promise<Response> {
    const res = await fetch(`${API_BASE}/editor/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${await ensureAuthToken()}`,
      },
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new ApiError(res.status, detail)
    }
    return res
  },
}
