/**
 * KnowledgePage —— 知识库
 * 研究项目文档列表（后端 /api/v1/knowledge/documents）+ 上传与图片素材入口
 */

import { useEffect, useState } from 'react'
import { Database, FileText, Loader2 } from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { FileUploader } from '@/components/FileUploader'
import { ImageSearch } from '@/components/ImageSearch'
import { projectsApi, API_BASE } from '@/lib/api'
import type { ProjectResponse } from '@/types/api'

interface KnowledgeDocument {
  document_id: string
  project_id: string
  project_topic: string
  section_title: string
  version: number
  updated_at: string | null
}

export function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [projectId, setProjectId] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [docs, projList] = await Promise.all([
          fetch(`${API_BASE}/knowledge/documents`).then((r) => (r.ok ? r.json() : [])),
          projectsApi.list(0, 100),
        ])
        if (cancelled) return
        setDocuments(Array.isArray(docs) ? docs : [])
        setProjects(projList)
        if (!projectId && projList.length > 0) setProjectId(projList[0].id)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 知识"
        title="Knowledge Base"
        description="企业文档、历史项目与检索语料 —— 为 Agent 工作流提供长期上下文。"
      />

      <div className="space-y-6">
        {/* ─── 文档库 ─────────────────────────────────────────── */}
        <section className="rounded-2xl border bg-card p-7 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">文档库</h2>
            <span className="text-xs text-muted-foreground">（{documents.length}）</span>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中…
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-xl border border-dashed py-12 text-center text-sm text-muted-foreground">
              暂无文档 —— 选择下方研究项目并上传文件，文档将入库供 Agent 检索
            </div>
          ) : (
            <ul className="divide-y">
              {documents.map((doc) => (
                <li key={doc.document_id} className="flex items-center gap-3 py-3">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{doc.section_title}</div>
                    <div className="text-xs text-muted-foreground">{doc.project_topic}</div>
                  </div>
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    v{doc.version}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ─── 上传与素材 ─────────────────────────────────────── */}
        <section className="rounded-2xl border bg-card p-7 shadow-sm">
          <div className="mb-4 flex items-center gap-3">
            <label htmlFor="kb-project" className="shrink-0 text-xs font-medium text-muted-foreground">
              研究项目
            </label>
            <select
              id="kb-project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="h-10 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {projects.length === 0 && <option value="">（暂无研究项目）</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.topic}
                </option>
              ))}
            </select>
          </div>
          {projectId && (
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <h3 className="mb-3 text-sm font-medium">文件上传</h3>
                <FileUploader projectId={projectId} />
              </div>
              <div>
                <h3 className="mb-3 text-sm font-medium">图片素材</h3>
                <ImageSearch projectId={projectId} />
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
