/**
 * ai/AgentTimeline —— AI 产品团队进度（"与 AI 团队协作"体验）
 *
 * 把八节点流水线映射为四个团队角色：
 *   Research Agent       research + competitor_analysis
 *   Product Agent        strategy
 *   Design Agent         design
 *   Presentation Agent   presentation + critic
 * （assemble 作为收尾步骤展示）
 */

import { AgentPhase, AgentStatus } from '@/components/ai/AgentStatus'
import { Users } from 'lucide-react'

interface TeamRole {
  name: string
  role: string
  nodes: string[]
  task: string
  doneTask: string
}

const TEAM: TeamRole[] = [
  {
    name: 'Research Agent',
    role: '研究员',
    nodes: ['research', 'competitor_analysis'],
    task: '搜索市场信息，分析竞品格局…',
    doneTask: '✓ 市场研究、竞品分析已完成',
  },
  {
    name: 'Product Agent',
    role: '产品负责人',
    nodes: ['strategy'],
    task: '制定产品定位、画像与功能路线…',
    doneTask: '✓ 产品策略、PRD 已完成',
  },
  {
    name: 'Design Agent',
    role: '设计师',
    nodes: ['design'],
    task: '梳理用户旅程与信息架构…',
    doneTask: '✓ UX 设计规格已完成',
  },
  {
    name: 'Presentation Agent',
    role: '演示专家',
    nodes: ['presentation', 'critic'],
    task: '编排演示叙事，评审视觉质量…',
    doneTask: '✓ 演示资产已完成并通过评审',
  },
  {
    name: 'PPT Design Agent',
    role: 'PPT 设计师',
    nodes: ['ppt_design'],
    task: '按 ppt-master 工作流设计逐页 SVG 并导出原生 PPTX…',
    doneTask: '✓ 原生可编辑 PPTX 已生成',
  },
]

function phaseOf(nodes: string[], nodeStatus: Record<string, string>): AgentPhase {
  const statuses = nodes.map((n) => nodeStatus[n] ?? 'pending')
  if (statuses.some((s) => s === 'failed')) return 'failed'
  if (statuses.some((s) => s === 'running')) return 'running'
  if (statuses.every((s) => s === 'completed')) return 'completed'
  if (statuses.some((s) => s === 'completed')) return 'running' // 部分完成视为进行中
  return 'pending'
}

export function AgentTimeline({
  nodeStatus,
  nodeModels,
}: {
  nodeStatus: Record<string, string>
  nodeModels?: Record<string, string>
}) {
  const assembleDone = nodeStatus['assemble'] === 'completed'

  /** 团队成员当前/所用模型（分工可见性：DeepSeek 主流水线，MiniMax 承接 PPT） */
  const modelOf = (nodes: string[]): string | undefined => {
    for (const n of nodes) {
      if (nodeModels?.[n]) return nodeModels[n]
    }
    return undefined
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-2 border-b pb-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#24415E]/8">
          <Users className="h-3.5 w-3.5 text-[#24415E]" />
        </span>
        <div>
          <div className="text-sm font-medium">AI 产品团队</div>
          <div className="text-[11px] text-muted-foreground">
            5 位专业 Agent 正在协作完成产品工作流（DeepSeek ↔ MiniMax 分工）
          </div>
        </div>
      </div>

      <div className="divide-y divide-border/60">
        {TEAM.map((member) => {
          const phase = phaseOf(member.nodes, nodeStatus)
          const model = modelOf(member.nodes)
          return (
            <AgentStatus
              key={member.name}
              name={member.name}
              task={
                phase === 'completed'
                  ? member.doneTask
                  : model
                    ? `${member.task}（模型：${model}）`
                    : member.task
              }
              phase={phase}
              detail={`${member.role}${model ? ' · ' + model : ''}`}
            />
          )
        })}
        <AgentStatus
          name="交付打包"
          task={assembleDone ? '✓ 产品资产包已生成' : '汇总结构化资产为最终交付物…'}
          phase={assembleDone ? 'completed' : 'pending'}
          detail="Final Asset Package"
        />
      </div>
    </div>
  )
}
