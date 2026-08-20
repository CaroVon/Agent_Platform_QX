/**
 * useGraphData —— 记忆图数据 Hook
 *
 * 管理 scope / projectId / 搜索 / 类型过滤 / 刷新，对接 /memory/graph。
 *
 * 修复记录（2026-08-20）：
 *  - scope=project 且 projectId 为空 → 不发请求（后端会回落 global 造成
 *    项目视图闪现全局旧数据）
 *  - rebuild 轮询闭包捕获旧 data 导致 break 永不命中 → 改用函数式读取
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { memoryApi } from '@/lib/api'
import type { MemoryEntityType, MemoryGraphResponse } from '@/types/api'

export interface GraphFilter {
  scope: 'global' | 'project'
  projectId: string
  q: string
  entityTypes: MemoryEntityType[]
}

const DEFAULT_FILT: GraphFilter = {
  scope: 'global',
  projectId: '',
  q: '',
  entityTypes: [],
}

export function useGraphData() {
  const [filter, setFilter] = useState<GraphFilter>(DEFAULT_FILT)
  const [data, setData] = useState<MemoryGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rebuilding, setRebuilding] = useState(false)
  const dataRef = useRef(data)
  dataRef.current = data

  const refresh = useCallback(async () => {
    // 项目视图未选定项目：置空数据并挂起（避免后端 scope 回落 global）
    if (filter.scope === 'project' && !filter.projectId) {
      setData(null)
      setLoading(false)
      setError('')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await memoryApi.graph({
        scope: filter.scope,
        projectId:
          filter.scope === 'project' && !filter.projectId.startsWith('studio:')
            ? filter.projectId || undefined
            : undefined,
        studioProductId:
          filter.scope === 'project' && filter.projectId.startsWith('studio:')
            ? filter.projectId.slice('studio:'.length)
            : undefined,
        q: filter.q || undefined,
        entityTypes: filter.entityTypes.length ? filter.entityTypes : undefined,
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
        await memoryApi.rebuild(projectId)
        // 等异步沉淀完成后刷新（轮询，命中即停；dataRef 读取最新值）
        for (let i = 0; i < 5; i++) {
          await new Promise((r) => setTimeout(r, 4000))
          await refresh()
          if ((dataRef.current?.nodes.length ?? 0) > 0) break
        }
      } finally {
        setRebuilding(false)
      }
    },
    [refresh],
  )

  return { filter, patchFilter, data, loading, error, refresh, rebuild, rebuilding }
}
