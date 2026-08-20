/**
 * useGraphData —— 记忆图数据 Hook
 *
 * 管理 scope / projectId / 搜索 / 类型过滤 / 刷新，对接 /memory/graph。
 */

import { useCallback, useEffect, useState } from 'react'
import { memoryApi } from '@/lib/api'
import type { MemoryEntityType, MemoryGraphResponse } from '@/types/api'

export interface GraphFilter {
  scope: 'global' | 'project'
  projectId: string
  q: string
  entityTypes: MemoryEntityType[]
}

const DEFAULT_FILTER: GraphFilter = {
  scope: 'global',
  projectId: '',
  q: '',
  entityTypes: [],
}

export function useGraphData() {
  const [filter, setFilter] = useState<GraphFilter>(DEFAULT_FILTER)
  const [data, setData] = useState<MemoryGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rebuilding, setRebuilding] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await memoryApi.graph({
        scope: filter.scope,
        projectId: filter.scope === 'project' && !filter.projectId.startsWith('studio:')
          ? filter.projectId || undefined : undefined,
        studioProductId: filter.scope === 'project' && filter.projectId.startsWith('studio:')
          ? filter.projectId.slice('studio:'.length) : undefined,
        q: filter.q || undefined,
        entityTypes: filter.entityTypes.length ? filter.entityTypes : undefined,
        limit: 400,
      })
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : '记忆图谱加载失败')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    refresh()
  }, [refresh])

  const patchFilter = useCallback((patch: Partial<GraphFilter>) => {
    setFilter((prev) => ({ ...prev, ...patch }))
  }, [])

  const rebuild = useCallback(
    async (projectId: string) => {
      setRebuilding(true)
      try {
        if (projectId.startsWith('studio:')) {
          await memoryApi.rebuildStudio(projectId.slice('studio:'.length))
        } else {
          await memoryApi.rebuild(projectId)
        }
        // 等异步沉淀完成后刷新（轮询 3 次）
        for (let i = 0; i < 3; i++) {
          await new Promise((r) => setTimeout(r, 4000))
          await refresh()
          if (data && data.nodes.length > 0) break
        }
      } finally {
        setRebuilding(false)
      }
    },
    [refresh, data],
  )

  return { filter, patchFilter, data, loading, error, refresh, rebuild, rebuilding }
}
