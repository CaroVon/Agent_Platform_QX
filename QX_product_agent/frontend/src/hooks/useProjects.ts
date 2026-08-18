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
