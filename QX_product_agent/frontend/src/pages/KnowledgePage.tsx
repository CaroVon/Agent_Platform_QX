/**
 * KnowledgePage —— 三层知识库（P1-P3 升级版）
 *
 * Tab1 文档库：跨项目文档列表 + 三层融合检索（任务/领域/全局）
 * Tab2 图片知识：本地上图 → MiniMax VL 分析入库（含分析状态/标签）
 * Tab3 领域与全局：相似任务判别（可借用经验）+ 领域经验包 + 知识资产
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Brain,
  Database,
  FileText,
  Layers,
  Loader2,
  Search,
  Sparkles,
} from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { FileUploader } from '@/components/FileUploader'
import { ImageSearch } from '@/components/ImageSearch'
import { projectsApi, knowledgeApi, API_BASE, ensureAuthToken } from '@/lib/api'
import type {
  ProjectResponse,
  KnowledgeSearchHit,
  SimilarProject,
  DomainExperience,
  KnowledgeAsset,
  KbImage,
} from '@/types/api'

interface KnowledgeDocument {
  document_id: string
  project_id: string
  project_topic: string
  section_title: string
  version: number
  updated_at: string | null
}

type Tab = 'docs' | 'images' | 'domain'

const STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: '待分析', cls: 'bg-amber-500/15 text-amber-600' },
  analyzing: { label: '分析中', cls: 'bg-blue-500/15 text-blue-600' },
  ready: { label: '已入库', cls: 'bg-emerald-500/15 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-red-500/15 text-red-600' },
}

export function KnowledgePage() {
  const [tab, setTab] = useState<Tab>('docs')
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [projectId, setProjectId] = useState('')
  const [loading, setLoading] = useState(true)

  // ── Tab1: 检索 ────────────────────────────────────────────
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [hits, setHits] = useState<KnowledgeSearchHit[]>([])
  const [searched, setSearched] = useState(false)

  // ── Tab2: 图片知识 ────────────────────────────────────────
  const [kbImages, setKbImages] = useState<KbImage[]>([])
  const [imagesLoading, setImagesLoading] = useState(false)

  // ── Tab3: 相似任务 + 领域经验 + 资产 ──────────────────────
  const [similar, setSimilar] = useState<SimilarProject[]>([])
  const [borrowable, setBorrowable] = useState('')
  const [experiences, setExperiences] = useState<DomainExperience[]>([])
  const [assets, setAssets] = useState<KnowledgeAsset[]>([])
  const [domainLoading, setDomainLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [docs, projList] = await Promise.all([
          fetch(`${API_BASE}/knowledge/documents`, {
            headers: { Authorization: `Bearer ${await ensureAuthToken()}` },
          }).then((r) => (r.ok ? r.json() : [])),
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

  const loadImages = useMemo(
    () => async (pid: string) => {
      setImagesLoading(true)
      try {
        const data = await projectsApi.getProjectImages(pid)
        setKbImages((data.images as KbImage[]) ?? [])
      } catch {
        setKbImages([])
      } finally {
        setImagesLoading(false)
      }
    },
    [],
  )

  const loadDomain = useMemo(
    () => async (pid: string) => {
      setDomainLoading(true)
      try {
        const [sim, exp, ast] = await Promise.all([
          projectsApi.getSimilar(pid).catch(() => null),
          knowledgeApi.domains().catch(() => null),
          knowledgeApi.assets().catch(() => null),
        ])
        setSimilar(sim?.similar_projects ?? [])
        setBorrowable(sim?.borrowable_experience ?? '')
        setExperiences(exp?.experiences ?? [])
        setAssets(ast?.assets ?? [])
      } finally {
        setDomainLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (!projectId) return
    void loadImages(projectId)
    void loadDomain(projectId)
  }, [projectId, loadImages, loadDomain])

  // 切到图片/领域 Tab 时刷新
  useEffect(() => {
    if (tab === 'images' && projectId) void loadImages(projectId)
    if (tab === 'domain' && projectId) void loadDomain(projectId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  const doSearch = async () => {
    if (!query.trim() || searching) return
    setSearching(true)
    setSearched(true)
    try {
      const data = await knowledgeApi.search(query.trim(), {
        projectId: projectId || undefined,
        k: 12,
      })
      setHits(data.hits)
    } catch {
      setHits([])
    } finally {
      setSearching(false)
    }
  }

  const parseAnalysis = (img: KbImage): { summary: string; tags: string[] } | null => {
    if (!img.analysis_text) return null
    try {
      const parsed = JSON.parse(img.analysis_text)
      return {
        summary: parsed.summary ?? '',
        tags: Array.isArray(parsed.tags) ? parsed.tags : [],
      }
    } catch {
      return null
    }
  }

  const tabs: { key: Tab; label: string; icon: typeof Database }[] = [
    { key: 'docs', label: '文档库', icon: Database },
    { key: 'images', label: '图片知识', icon: Layers },
    { key: 'domain', label: '领域与全局', icon: Brain },
  ]

  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 知识"
        title="Knowledge Base"
        description="三层知识体系：任务知识（L2）· 领域知识（L1，相似任务借用）· 全局知识（L0，企业文档/Obsidian）。"
      />

      {/* ─── Tab 切换 ─────────────────────────────────────────── */}
      <div className="mb-6 flex items-center gap-1 rounded-xl border bg-card p-1 shadow-sm">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-secondary'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* ─── 项目选择（三个 Tab 共用） ───────────────────────── */}
      <div className="mb-6 flex items-center gap-3 rounded-2xl border bg-card px-5 py-3 shadow-sm">
        <label htmlFor="kb-project" className="shrink-0 text-xs font-medium text-muted-foreground">
          当前任务
        </label>
        <select
          id="kb-project"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="h-9 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {projects.length === 0 && <option value="">（暂无研究项目）</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.topic}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中…
        </div>
      ) : (
        <div className="space-y-6">
          {/* ═══════════ Tab1: 文档库 + 三层检索 ═══════════ */}
          {tab === 'docs' && (
            <>
              <section className="rounded-2xl border bg-card p-6 shadow-sm">
                <div className="mb-3 flex items-center gap-2">
                  <Search className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">三层融合检索</h2>
                  <span className="text-xs text-muted-foreground">
                    任务库 + 领域库 + 全局库
                  </span>
                </div>
                <div className="flex gap-2">
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && doSearch()}
                    placeholder="输入关键词，检索全部知识层…"
                    className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <button
                    type="button"
                    onClick={doSearch}
                    disabled={searching}
                    className="flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                  >
                    {searching && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    检索
                  </button>
                </div>

                {searched && (
                  <ul className="mt-4 space-y-2">
                    {hits.length === 0 && (
                      <li className="rounded-lg border border-dashed py-6 text-center text-sm text-muted-foreground">
                        未找到相关内容
                      </li>
                    )}
                    {hits.map((hit, i) => (
                      <li key={i} className="rounded-lg border bg-card px-4 py-3">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                            {hit.scope}
                          </span>
                          {hit.title && (
                            <span className="truncate text-xs font-medium">{hit.title}</span>
                          )}
                          <span className="ml-auto shrink-0 truncate text-[10px] text-muted-foreground">
                            {hit.source_url}
                          </span>
                        </div>
                        <p className="line-clamp-3 text-sm text-muted-foreground">{hit.content}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-2xl border bg-card p-7 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">文档库</h2>
                  <span className="text-xs text-muted-foreground">（{documents.length}）</span>
                </div>
                {documents.length === 0 ? (
                  <div className="rounded-xl border border-dashed py-12 text-center text-sm text-muted-foreground">
                    暂无文档 —— 在下方上传文件，文件将进入任务知识库供 Agent 检索
                  </div>
                ) : (
                  <ul className="divide-y">
                    {documents.map((doc) => (
                      <li key={doc.document_id} className="flex items-center gap-3 py-3">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{doc.section_title}</div>
                          <div className="truncate text-xs text-muted-foreground">
                            {doc.project_topic}
                          </div>
                        </div>
                        <span className="shrink-0 text-[10px] text-muted-foreground">
                          v{doc.version}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {projectId && (
                  <div className="mt-6 border-t pt-5">
                    <h3 className="mb-3 text-sm font-medium">文件上传（文档 → 任务知识库）</h3>
                    <FileUploader projectId={projectId} />
                  </div>
                )}
              </section>
            </>
          )}

          {/* ═══════════ Tab2: 图片知识 ═══════════ */}
          {tab === 'images' && projectId && (
            <>
              <section className="rounded-2xl border bg-card p-7 shadow-sm">
                <div className="mb-2 flex items-center gap-2">
                  <Layers className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">图片上传入库</h2>
                  <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                  <span className="text-xs text-muted-foreground">
                    MiniMax VL 自动分析（概述/OCR/标签）后写入任务知识库
                  </span>
                </div>
                <FileUploader projectId={projectId} imageKb />
              </section>

              <section className="rounded-2xl border bg-card p-7 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <Database className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">图片知识库</h2>
                  <span className="text-xs text-muted-foreground">
                    含网络搜索与本地入库图片
                  </span>
                </div>

                {imagesLoading ? (
                  <div className="flex items-center justify-center py-10 text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中…
                  </div>
                ) : kbImages.length === 0 ? (
                  <div className="rounded-xl border border-dashed py-10 text-center text-sm text-muted-foreground">
                    暂无图片 —— 上传图片后将在此显示 VL 分析状态与标签
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
                    {kbImages.map((img) => {
                      const analysis = parseAnalysis(img)
                      const meta = STATUS_META[img.status ?? ''] ?? STATUS_META.pending
                      return (
                        <div
                          key={img.id}
                          className="overflow-hidden rounded-xl border bg-card shadow-sm"
                        >
                          <div className="flex h-28 items-center justify-center bg-secondary/40">
                            {img.source === 'upload' ? (
                              <FileText className="h-8 w-8 text-muted-foreground/50" />
                            ) : (
                              <img
                                src={img.image_url}
                                alt={img.title}
                                className="h-full w-full object-cover"
                              />
                            )}
                          </div>
                          <div className="p-3">
                            <div className="flex items-center gap-2">
                              <span
                                className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${meta.cls}`}
                              >
                                {meta.label}
                              </span>
                              <span className="truncate text-[11px] font-medium">
                                {img.title}
                              </span>
                            </div>
                            {analysis?.tags && analysis.tags.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {analysis.tags.slice(0, 4).map((t) => (
                                  <span
                                    key={t}
                                    className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground"
                                  >
                                    {t}
                                  </span>
                                ))}
                              </div>
                            )}
                            {analysis?.summary && (
                              <p className="mt-1.5 line-clamp-2 text-[11px] text-muted-foreground">
                                {analysis.summary}
                              </p>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>
            </>
          )}

          {/* ═══════════ Tab3: 领域与全局 ═══════════ */}
          {tab === 'domain' && projectId && (
            <>
              <section className="rounded-2xl border bg-card p-7 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <Brain className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">相似任务判别</h2>
                  <span className="text-xs text-muted-foreground">
                    主题向量 + 领域标签 + 模板 加权相似度
                  </span>
                </div>
                {domainLoading ? (
                  <div className="flex items-center justify-center py-8 text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 计算中…
                  </div>
                ) : similar.length === 0 ? (
                  <div className="rounded-xl border border-dashed py-8 text-center text-sm text-muted-foreground">
                    暂无高相似度历史任务（可借用阈值由后端配置）
                  </div>
                ) : (
                  <ul className="space-y-2">
                    {similar.map((s) => (
                      <li
                        key={s.project_id}
                        className="flex items-center gap-3 rounded-lg border px-4 py-3"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{s.topic}</div>
                          <div className="mt-0.5 flex flex-wrap gap-1.5">
                            {s.domain_tags.map((t) => (
                              <span
                                key={t}
                                className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold text-primary">
                            {(s.similarity * 100).toFixed(0)}%
                          </div>
                          <div className="text-[10px] text-muted-foreground">相似度</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {borrowable && (
                  <div className="mt-4 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                    <div className="mb-1 text-[11px] font-medium text-primary">
                      可借用的领域经验
                    </div>
                    <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
                      {borrowable}
                    </pre>
                  </div>
                )}
              </section>

              <div className="grid gap-6 lg:grid-cols-2">
                <section className="rounded-2xl border bg-card p-6 shadow-sm">
                  <h2 className="mb-3 text-sm font-semibold">领域经验包</h2>
                  {experiences.length === 0 ? (
                    <p className="rounded-lg border border-dashed py-6 text-center text-sm text-muted-foreground">
                      暂无经验包 —— 任务完成后自动抽取
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {experiences.slice(0, 6).map((e) => (
                        <li key={e.id} className="rounded-lg border px-3 py-2">
                          <div className="mb-1 flex items-center gap-2">
                            <span className="truncate text-xs font-medium">{e.topic}</span>
                            <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                              {e.domain_tags.join(' · ')}
                            </span>
                          </div>
                          <p className="line-clamp-2 text-[11px] text-muted-foreground">
                            {e.summary}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="rounded-2xl border bg-card p-6 shadow-sm">
                  <h2 className="mb-3 text-sm font-semibold">全局知识资产</h2>
                  {assets.length === 0 ? (
                    <p className="rounded-lg border border-dashed py-6 text-center text-sm text-muted-foreground">
                      暂无全局资产 —— 配置 Obsidian Vault 同步后自动积累
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {assets.slice(0, 8).map((a) => (
                        <li key={a.id} className="flex items-center gap-3 rounded-lg border px-3 py-2">
                          <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-xs font-medium">{a.title}</div>
                            <div className="truncate text-[10px] text-muted-foreground">
                              {a.source} · {a.scope} · {a.chunk_count} 切片
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
