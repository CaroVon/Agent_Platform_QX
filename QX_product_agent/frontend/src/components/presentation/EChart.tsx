/**
 * presentation/EChart —— ECharts 通用容器（自适应 + 主题联动）
 * 用于象限图等高级图表（美观度升级，替代 recharts 基础散点）
 */

import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export function EChart({
  option,
  height = 200,
}: {
  option: Record<string, unknown>
  height?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chartRef.current = chart
    chart.setOption(option)

    const resizeObserver = new ResizeObserver(() => {
      chart.resize()
    })
    resizeObserver.observe(ref.current)
    return () => {
      resizeObserver.disconnect()
      chart.dispose()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, true)
  }, [option])

  return <div ref={ref} style={{ width: '100%', height }} />
}
