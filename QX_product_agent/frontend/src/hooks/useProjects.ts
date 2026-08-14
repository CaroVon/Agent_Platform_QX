/**
 * ============================================================
 * React Query Hooks —— 项目管理
 * ============================================================
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api'
import type { ProjectCreateRequest } from '@/types/api'

const PROJECTS_KEY = ['projects'] as const

/** 获取项目列表 */
export function useProjectList() {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: () => projectsApi.list(),
    refetchInterval: 30_000, // 每 30 秒静默刷新列表
    staleTime: 10_000,
  })
}

/** 获取单个项目状态（支持长轮询） */
export function useProjectStatus(
  projectId: string | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'status'],
    queryFn: () => projectsApi.getStatus(projectId!),
    enabled: !!projectId && enabled,
    // ─── 核心轮询策略 ──────────────────────────────────────
    // 每 3 秒轮询一次进度，持续到项目完成或失败
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 3000
      const status = data.project_status
      // 需要用户交互 → 暂停轮询
      if (status === 'waiting_for_sources' || status === 'waiting_for_outline') return false
      // 项目已终态 → 停止轮询
      if (status === 'completed' || status === 'failed') return false
      return 3000
    },
    // 页面不可见时依然继续轮询（后台 Tab）
    refetchIntervalInBackground: true,
    staleTime: 0, // 每次都走网络请求，保证进度实时性
  })
}

/** 获取项目下载信息 */
export function useProjectDownload(projectId: string | undefined) {
  return useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'download'],
    queryFn: () => projectsApi.getDownload(projectId!),
    enabled: !!projectId,
    staleTime: 60_000,
  })
}

/** 创建新项目 */
export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ProjectCreateRequest) => projectsApi.create(data),
    onSuccess: () => {
      // 创建成功后，刷新项目列表
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY })
    },
  })
}

/** 删除项目 */
export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (projectId: string) => projectsApi.delete(projectId),
    onSuccess: () => {
      // 删除成功后，刷新项目列表
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY })
    },
  })
}
