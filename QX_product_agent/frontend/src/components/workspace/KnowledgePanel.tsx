/**
 * KnowledgePanel —— Knowledge Context（知识上下文）
 * 研究项目绑定 + 文件上传 + 图片搜索
 */

import { useEffect, useState } from 'react'
import { Database } from 'lucide-react'
import { projectsApi } from '@/lib/api'
import type { ProjectResponse } from '@/types/api'
import { FileUploader } from '@/components/FileUploader'
import { ImageSearch } from '@/components/ImageSearch'

export function KnowledgePanel() {
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [projectId, setProjectId] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const list = await projectsApi.list(0, 100)
        if (cancelled) return
        setProjects(list)
        if (!projectId && list.length > 0) setProjectId(list[0].id)
      } catch {
        /* 非关键路径 */
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
      <div className="mb-5 flex items-center gap-3">
        <Database className="h-4 w-4 text-[#24415E]" />
        <label htmlFor="kp-project" className="shrink-0 text-xs font-medium text-muted-foreground">
          研究项目
        </label>
        <select
          id="kp-project"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="h-10 w-full max-w-md rounded-lg border bg-card px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {projects.length === 0 && <option value="">（暂无研究项目）</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.topic}
            </option>
          ))}
        </select>
      </div>

      {projectId ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <div>
            <h3 className="mb-4 text-sm font-medium">上传文档</h3>
            <FileUploader projectId={projectId} />
          </div>
          <div>
            <h3 className="mb-4 text-sm font-medium">图片素材</h3>
            <ImageSearch projectId={projectId} />
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          暂无研究项目 —— 在控制台创建一个研究项目，或直接输入产品想法启动 AI 团队。
        </p>
      )}
    </div>
  )
}
