/**
 * ============================================================
 * useProjectLogs —— 项目时间轴增量日志轮询
 *
 * 前端右侧面板通过此 Hook 获取后端 Agent 的执行日志。
 * 采用增量拉取策略：仅获取自上次拉取后的新日志。
 *
 * 轮询策略：
 * - 活跃状态（preparing_data / preparing_outline / drafting）→ 每 2 秒轮询
 * - 交互状态（waiting_for_sources / waiting_for_outline）→ 停止轮询
 * - 终态（completed / failed）→ 最后一次拉取后停止
 * ============================================================
 */

import { useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api'
import type { ProjectLogResponse } from '@/types/api'
import type { ProjectStatusEnum } from '@/types/api'

const PROJECTS_KEY = ['projects'] as const

interface UseProjectLogsOptions {
  projectId: string | undefined
  status: ProjectStatusEnum | undefined
  enabled?: boolean
}

export function useProjectLogs({ projectId, status, enabled = true }: UseProjectLogsOptions) {
  // 增量拉取：记录上次获取的最大 sequence
  const lastSequenceRef = useRef(0)

  // 累积的日志列表
  const allLogsRef = useRef<ProjectLogResponse[]>([])

  const query = useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'logs'],
    queryFn: async () => {
      if (!projectId) return { logs: [], total_count: 0 }

      const data = await projectsApi.getLogs(projectId, lastSequenceRef.current)

      // 增量追加
      if (data.logs.length > 0) {
        allLogsRef.current = [...allLogsRef.current, ...data.logs]
        // 更新游标
        const maxSeq = Math.max(...data.logs.map((l) => l.sequence))
        lastSequenceRef.current = maxSeq
      }

      return {
        logs: allLogsRef.current,
        total_count: data.total_count,
      }
    },
    enabled: !!projectId && enabled,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000

      // 仅在活跃的生成状态中轮询
      if (status === 'preparing_data' || status === 'preparing_outline' || status === 'drafting') {
        return 2000
      }
      // 终态：停止轮询
      return false
    },
    refetchIntervalInBackground: false,
    staleTime: 0,
    // select：从累积日志中提取
    select: (data) => ({
      logs: data.logs,
      total_count: data.total_count,
    }),
  })

  // 重置日志（项目切换时调用）
  const resetLogs = useCallback(() => {
    lastSequenceRef.current = 0
    allLogsRef.current = []
  }, [])

  return {
    logs: (query.data?.logs ?? []) as ProjectLogResponse[],
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    resetLogs,
  }
}
