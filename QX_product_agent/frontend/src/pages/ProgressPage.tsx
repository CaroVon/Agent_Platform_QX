/**
 * ProgressPage —— 自动重定向到 WorkspacePage
 *
 * 旧的进度独立页面已废弃，所有交互和进度展示已统一在 WorkspacePage 中。
 * 保留此路由是为了兼容旧链接（如 A 标签中的 /projects/:id/progress）。
 */
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

export function ProgressPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  useEffect(() => {
    if (projectId) {
      navigate(`/projects/${projectId}/workspace`, { replace: true })
    }
  }, [projectId, navigate])

  return (
    <div className="flex h-64 items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">正在跳转到工作台...</p>
      </div>
    </div>
  )
}
