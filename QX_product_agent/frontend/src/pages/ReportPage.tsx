import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Loader2, AlertCircle, Download, FileDown } from 'lucide-react'
import { Button } from '@/components/common/button'
import { CitationMarkdown } from '@/components/report/CitationMarkdown'
import { useProjectDownload } from '@/hooks/useProjects'
import { projectsApi } from '@/lib/api'
import type { ReportContentResponse, SectionContent } from '@/types/api'
import { useEffect, useState } from 'react'

/**
 * 交互式报告阅读器页面（任务 4）
 *
 * 核心功能：
 * - 通过 GET /api/v1/projects/{id}/content 获取报告全文
 * - 使用 react-markdown 渲染带 [^n] 角标的 Markdown 正文
 * - 自定义渲染器实现 Citation Hover：悬停角标时弹出气泡卡片
 * - 显示参考来源 URL 或标题
 */
export function ReportPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: downloadData } = useProjectDownload(projectId)
  const [report, setReport] = useState<ReportContentResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ─── 获取报告内容 ────────────────────────────────────────────
  useEffect(() => {
    if (!projectId) return

    setLoading(true)
    setError(null)

    projectsApi
      .getContent(projectId)
      .then((data) => {
        setReport(data)
        setLoading(false)
      })
      .catch((err: Error) => {
        setError(err.message || '获取报告内容失败')
        setLoading(false)
      })
  }, [projectId])

  // ─── 加载中 ──────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">加载报告内容...</p>
        </div>
      </div>
    )
  }

  // ─── 错误 ────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="flex flex-col items-center gap-4">
          <AlertCircle className="h-10 w-10 text-destructive" />
          <p className="font-medium text-destructive">无法加载报告</p>
          <p className="max-w-md text-center text-sm text-muted-foreground">
            {error}
          </p>
          <div className="flex gap-3 mt-2">
            <Link to={`/projects/${projectId}/workspace`}>
              <Button variant="outline" size="sm">
                返回工作区
              </Button>
            </Link>
            <Link to="/">
              <Button variant="outline" size="sm">
                返回控制台
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* ─── 顶部导航 ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          返回控制台
        </Link>

        {/* 下载按钮 */}
        {downloadData?.download_url && (
          <a href={downloadData.download_url} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="h-4 w-4" />
              下载 PDF
            </Button>
          </a>
        )}
      </div>

      {/* ─── 报告标题 ─────────────────────────────────────────── */}
      <div className="border-b pb-4">
        <h1 className="text-2xl font-bold">
          {report?.topic ?? '产品分析报告'}
        </h1>
        <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <FileDown className="h-3 w-3" />
            PDF 导出可用
          </span>
          {downloadData?.file_size_bytes && (
            <span>
              文件大小: {(downloadData.file_size_bytes / 1024 / 1024).toFixed(1)} MB
            </span>
          )}
          {report?.sections && (
            <span>
              共 {report.sections.length} 个章节
            </span>
          )}
        </div>
      </div>

      {/* ─── 章节列表（Tab 切换） ─────────────────────────────── */}
      {report && report.sections.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {report.sections.map((section) => (
            <a
              key={section.order}
              href={`#section-${section.order}`}
              className="shrink-0 rounded-full border bg-secondary/50 px-3 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary transition-colors"
            >
              {section.title}
            </a>
          ))}
        </div>
      )}

      {/* ─── 报告正文（带溯源的 Markdown） ────────────────────── */}
      <div className="space-y-10">
        {report && report.sections.length === 0 && !loading && !error && (
          <div className="rounded-xl border border-dashed p-12 text-center">
            <p className="text-sm text-muted-foreground">
              暂无章节内容。请确认后端已完成报告生成。
            </p>
          </div>
        )}

        {report?.sections.map((section: SectionContent) => {
          const citationMap = section.citations
          return (
            <section
              key={section.order}
              id={`section-${section.order}`}
              className="scroll-mt-20"
            >
              {/* ─── 章节标题 ────────────────────────────────── */}
              <h2 className="mb-4 text-lg font-semibold">
                {section.title}
              </h2>

              {/* ─── 引用角标渲染 ────────────────────────────── */}
              <CitationMarkdown
                content={section.content}
                citationMap={citationMap}
              />

              {/* ─── 章节引用列表 ────────────────────────────── */}
              {Object.keys(citationMap).length > 0 && (
                <div className="mt-6 rounded-lg border bg-muted/30 p-4">
                  <h4 className="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    本章参考来源
                  </h4>
                  <ol className="space-y-1.5">
                    {Object.entries(citationMap).map(([num, url]) => (
                      <li key={num} className="text-xs">
                        <span className="font-medium text-muted-foreground">[{num}]</span>{' '}
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline break-all"
                        >
                          {url}
                        </a>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* ─── 章节分隔 ──────────────────────────────────── */}
              <div className="mt-10 border-t" />
            </section>
          )
        })}
      </div>
    </div>
  )
}
