/**
 * ============================================================
 * useProjectStatus —— 状态机感知的轮询 Hook
 *
 * 核心职责：
 * 1. 使用 React Query 以可变速率的频率轮询 /status
 * 2. 根据返回的 project_status 决定渲染逻辑：
 *    - preparing_data → 节点1 执行中，继续轮询
 *    - waiting_for_sources → 🛑 暂停轮询，等待用户审核资料
 *    - preparing_outline → 大纲生成中，继续轮询
 *    - waiting_for_outline → 🛑 暂停轮询，等待用户确认大纲
 *    - drafting → 节点3 执行中，继续轮询 + 拉取 blocks
 *    - completed / failed → 停止轮询
 * 3. 对外暴露 isWaitingSources, isWaitingApproval, isDrafting 等语义化标志
 * 4. 🆕 支持乐观状态更新 (optimistic transition)，在用户点击确认后
 *    立即将 UI 锁定为过渡态，避免因轮询延迟导致的状态闪烁
 * ============================================================
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api'
import type {
  OutlineApproveResponse,
  OutlineApproveRequest,
  SourceReviewRequest,
  SourceReviewResponse,
} from '@/types/api'
import type { ProjectStatusEnum } from '@/types/api'

const PROJECTS_KEY = ['projects'] as const

// ─── 乐观过渡状态管理 ────────────────────────────────────────

/**
 * 在用户触发状态迁移 (如审核资料 / 确认大纲) 后，
 * 前端立即设置一个乐观状态，防止 UI 在等待下一次轮询时出现闪烁。
 *
 * 乐观状态将在下一次成功的轮询响应到达后自动清除。
 */
let _optimisticStatus: ProjectStatusEnum | null = null

/** 设置乐观状态（由 mutation onMutate 调用） */
export function setOptimisticStatus(status: ProjectStatusEnum) {
  _optimisticStatus = status
}

/** 清除乐观状态（由 mutation onSuccess / 轮询成功响应 调用） */
export function clearOptimisticStatus() {
  _optimisticStatus = null
}

/** 获取当前有效状态（优先返回乐观状态） */
export function getEffectiveStatus(serverStatus: ProjectStatusEnum | undefined): ProjectStatusEnum | undefined {
  if (_optimisticStatus) {
    // 乐观状态优先——但只在我们"向前推进"时生效
    // (WAITING_* → PROCESSING/DRAFTING 等过渡态)
    return _optimisticStatus
  }
  return serverStatus
}

interface UseProjectStatusOptions {
  /** 项目 ID */
  projectId: string | undefined
  /** 是否启用轮询 */
  enabled?: boolean
}

/**
 * 状态机感知的项目状态轮询
 *
 * 轮询策略 (修复：使用闭包安全的方式获取最新状态):
 * - preparing_data / preparing_outline / drafting → 每 3 秒轮询
 * - waiting_for_sources → 停止轮询（等待用户审核资料）
 * - waiting_for_outline → 停止轮询（等待用户确认大纲）
 * - completed / failed → 停止轮询（终态）
 *
 * 🆕 乐观状态: 当 mutation.onMutate 设置乐观状态后，
 * 即使服务器尚未返回新状态，前端也按过渡态渲染。
 */
export function useProjectStatus({ projectId, enabled = true }: UseProjectStatusOptions) {
  const queryClient = useQueryClient()

  return useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'status'],
    queryFn: async () => {
      const data = await projectsApi.getStatus(projectId!)
      // 轮询成功返回后清除乐观状态（真实数据优先）
      if (_optimisticStatus) {
        clearOptimisticStatus()
      }
      return data
    },
    enabled: !!projectId && enabled,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 3000

      // 🆕 如果在乐观过渡期，继续高频轮询 (1.5s) 以快速获取真实状态
      if (_optimisticStatus) return 1500

      const status = data.project_status as ProjectStatusEnum
      // 需要用户交互 → 暂停轮询
      if (status === 'waiting_for_sources' || status === 'waiting_for_outline') return false
      // 终态 → 停止轮询
      if (status === 'completed' || status === 'failed') return false
      // 活跃态 → 每 3 秒轮询
      return 3000
    },
    refetchIntervalInBackground: false,  // 🆕 后台标签页不轮询，节省资源
    staleTime: 0,
    structuralSharing: true,
  })
}

// ─── 语义化状态标志计算 ──────────────────────────────────────

/** 提取语义化状态标志 */
export function getStatusFlags(status: ProjectStatusEnum | undefined) {
  // 🆕 允许乐观状态覆盖
  const effective = getEffectiveStatus(status)

  return {
    /** 节点1 资料搜索中 */
    isPreparing: effective === 'preparing_data',
    /** 🛑 等待用户审核资料（交互节点1） */
    isWaitingSources: effective === 'waiting_for_sources',
    /** 大纲生成中 */
    isPreparingOutline: effective === 'preparing_outline',
    /** 🎯 等待用户确认大纲（交互节点2） */
    isWaitingApproval: effective === 'waiting_for_outline',
    /** 节点3 AI 撰写中 */
    isDrafting: effective === 'drafting',
    /** 已完成 */
    isCompleted: effective === 'completed',
    /** 已失败 */
    isFailed: effective === 'failed',
    /** 是否处于活跃状态（非终态） */
    isActive: effective !== 'completed' && effective !== 'failed',
    /** 🆕 是否处于过渡态（乐观更新中） */
    isTransitioning: _optimisticStatus !== null,
  }
}

// ─── 文档块查询 ──────────────────────────────────────────────

/**
 * 获取项目的所有 DocumentBlock
 * 仅在 drafting / completed 状态下才启用
 */
export function useProjectBlocks(projectId: string | undefined, enabled = false) {
  return useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'blocks'],
    queryFn: () => projectsApi.getBlocks(projectId!),
    enabled: !!projectId && enabled,
    // drafting 阶段每 5 秒轮询新块（SSE 降级方案）
    refetchInterval: 5000,
    refetchIntervalInBackground: false,  // 🆕 后台不轮询
    staleTime: 0,
  })
}

// ─── 大纲确认 Mutation ──────────────────────────────────────

/**
 * 提交大纲确认
 *
 * 调用后：
 * 1. 前端立即设置乐观状态为 'drafting'（UI 即刻响应）
 * 2. 后端将 ProjectStatus 从 waiting_for_outline → drafting
 * 3. 触发 Celery 节点3：run_draft_sections_workflow
 * 4. 前端以 1.5s 高频轮询获取真实状态
 */
export function useApproveOutline() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: string
      data: OutlineApproveRequest
    }) => projectsApi.approveOutline(projectId, data),
    onMutate: () => {
      // 🆕 乐观更新：立即设置过渡态
      setOptimisticStatus('drafting')
    },
    onSuccess: (response: OutlineApproveResponse, variables) => {
      // 刷新状态到 drafting
      queryClient.invalidateQueries({
        queryKey: [...PROJECTS_KEY, variables.projectId, 'status'],
      })
      // 触发 blocks 查询
      queryClient.invalidateQueries({
        queryKey: [...PROJECTS_KEY, variables.projectId, 'blocks'],
      })
    },
    onError: (_error, _variables) => {
      // 🆕 失败时清除乐观状态，回归实际状态
      clearOptimisticStatus()
    },
    onSettled: () => {
      // 延迟清除乐观状态（让下一次轮询结果覆盖）
      setTimeout(() => clearOptimisticStatus(), 5000)
    },
  })
}

// ─── 资料审核 Hooks ──────────────────────────────────────────

/**
 * 获取项目的资料来源列表（交互节点1 审核面板数据）
 */
export function useSources(projectId: string | undefined, enabled = false) {
  return useQuery({
    queryKey: [...PROJECTS_KEY, projectId, 'sources'],
    queryFn: () => projectsApi.getSources(projectId!),
    enabled: !!projectId && enabled,
    staleTime: 0,
  })
}

/**
 * 提交资料审核结果
 *
 * 调用后：
 * 1. 前端立即设置乐观状态为 'preparing_outline'（UI 即刻响应）
 * 2. 后端将 ProjectStatus 从 waiting_for_sources → preparing_outline
 * 3. 触发 Celery generate_outline_workflow
 * 4. 前端以 1.5s 高频轮询获取真实状态
 */
export function useReviewSources() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: string
      data: SourceReviewRequest
    }) => projectsApi.reviewSources(projectId, data),
    onMutate: () => {
      // 🆕 乐观更新：立即设置过渡态
      setOptimisticStatus('preparing_outline')
    },
    onSuccess: (response: SourceReviewResponse, variables) => {
      // 刷新状态
      queryClient.invalidateQueries({
        queryKey: [...PROJECTS_KEY, variables.projectId, 'status'],
      })
    },
    onError: (_error, _variables) => {
      // 🆕 失败时清除乐观状态，回归实际状态
      clearOptimisticStatus()
    },
    onSettled: () => {
      // 延迟清除乐观状态
      setTimeout(() => clearOptimisticStatus(), 5000)
    },
  })
}
