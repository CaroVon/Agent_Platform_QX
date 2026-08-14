/**
 * ============================================================
 * API 服务层
 * —— 基于 fetch 封装，对接后端 FastAPI
 *     新增 approve-outline、blocks 等端点
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
} from '@/types/api'
import type {
  ExportPdfResponse,
  StudioProduct,
  StudioProductCreateResponse,
} from '@/types/studio'

const API_BASE = '/api/v1'

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API Error [${status}]: ${detail}`)
    this.name = 'ApiError'
  }
}

async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

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
      headers: { 'Content-Type': 'application/json' },
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
