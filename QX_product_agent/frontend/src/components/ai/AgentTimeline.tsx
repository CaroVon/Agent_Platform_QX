/**
 * ai/AgentTimeline —— AI 产品团队进度（"与 AI 团队协作"体验）
 *
 * 八节点流水线映射为五个团队角色 + 交付打包：
 *   Research Agent       research + competitor_analysis
 *   Product Agent        strategy
 *   Design Agent         design
 *   Presentation Agent   presentation + critic
 *   PPT Design Agent     ppt_design
 * 进度由后端在节点边界实时回写（node_status 持久化）：
 *   - 顶部「当前步骤」横幅：正在工作的 Agent + 说明 + 模型 + 打字动画
 *   - 整体进度条（按节点顺序百分比，运行中斜纹流动）
 *   - 每行步骤流转动画（pending→running→completed 淡入）
 */

import { Loader2, Users } from 'lucide-react'
import { AgentPhase, AgentStatus } from '@/components/ai/AgentStatus'
import { cn } from '@/lib/utils'

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
    nodes: ['research', 'competitor_matrix', 'competitor_analysis'],
    task: '搜索市场信息，抓取亚马逊竞品数据，分析竞品格局…',
    doneTask: '✓ 市场研究、竞品矩阵、竞品分析已完成',
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

// 节点执行顺序（对齐 NODE_ORDER + critic/ppt_design/assemble）
const NODE_ORDER = [
  'requirement_parser', 'source_gathering', 'research', 'competitor_matrix',
  'competitor_analysis', 'strategy', 'design', 'presentation', 'critic', 'ppt_design', 'assemble',
]

// 节点 → 人话说明（当前正在做什么）
const NODE_MESSAGES: Record<string, string> = {
  requirement_parser: '解析产品需求，明确目标与边界',
  source_gathering: '全网检索资料并标注权重（等待审核）',
  research: '市场研究：搜索行业规模、竞品与用户痛点',
  competitor_matrix: '竞品矩阵：抓取亚马逊真实价格/评价数据并生成 MOD 报告',
  competitor_analysis: '竞品分析：构建矩阵与差异化机会',
  strategy: '产品策略：定位、画像、功能与路线图',
  design: 'UX 设计：用户旅程与信息架构',
  presentation: '演示编排：SCR 叙事与演示 DSL',
  critic: '质量评审：覆盖度与视觉门禁',
  ppt_design: 'PPT 制作：设计规范 → 逐页 SVG → 原生 PPTX',
  assemble: '资产打包：收敛全部节点产物',
}

function phaseOf(
  nodes: string[],
  nodeStatus: Record<string, string>,
  opts?: { productStatus?: string },
): AgentPhase {
  const statuses = nodes.map((n) => nodeStatus[n] ?? 'pending')
  // 产品整体已成功时，节点级 failed 不应再标红（可能是可降级/已恢复的节点）
  const productSucceeded = opts?.productStatus === 'completed'
  const failed = statuses.filter((s) => s === 'failed')
  const recovered = statuses.some((s) => s === 'recovered')
  if (failed.length && !productSucceeded) return 'failed'
  if (statuses.some((s) => s === 'running')) return 'running'
  if (statuses.every((s) => s === 'completed' || s === 'recovered')) return recovered ? 'recovered' : 'completed'
  if (statuses.some((s) => s === 'completed' || s === 'recovered')) return 'running' // 部分完成视为进行中
  if (failed.length) return 'recovered' // 已成功但个别节点降级 → 用"已恢复"表达，不再标红
  return 'pending'
}

function TypingDotsInline() {
  return (
    <span className="ml-1 inline-flex items-center text-[#24415E]">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </span>
  )
}

export function AgentTimeline({
  nodeStatus,
  nodeModels,
  productStatus,
  logs,
}: {
  nodeStatus: Record<string, string>
  nodeModels?: Record<string, string>
  productStatus?: string
  /** 真实执行事件（后端 progress_log），有数据时展示真实过程 */
  logs?: Array<{ ts: string; node: string; status: string; detail?: string }>
}) {
  const assembleDone = nodeStatus['assemble'] === 'completed'

  /** 团队成员当前/所用模型（分工可见性：DeepSeek 主流水线，MiniMax 承接 PPT） */
  const modelOf = (nodes: string[]): string | undefined => {
    for (const n of nodes) {
      if (nodeModels?.[n]) return nodeModels[n]
    }
    return undefined
  }

  // ── 整体进度（按节点顺序） ──
  const completedCount = NODE_ORDER.filter((n) => nodeStatus[n] === 'completed').length
  const progressPct = Math.round((completedCount / NODE_ORDER.length) * 100)
  const anyRunning = NODE_ORDER.some((n) => nodeStatus[n] === 'running')

  // ── 当前步骤（正在运行的节点） ──
  const activeNode = NODE_ORDER.find((n) => nodeStatus[n] === 'running')
  const activeTeam = TEAM.find((m) => activeNode && m.nodes.includes(activeNode))
  const activeMessage = activeNode ? (NODE_MESSAGES[activeNode] ?? '执行中…') : ''

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

      {/* ── 整体进度条 ── */}
      <div className="mb-4">
        <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>流水线进度</span>
          <span>{completedCount}/{NODE_ORDER.length} 步骤 · {progressPct}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-secondary">
          <div
            className={cn(
              'h-full rounded-full bg-[#24415E] transition-all duration-500',
              anyRunning && 'progress-stripes',
            )}
            style={{ width: `${Math.max(progressPct, 4)}%` }}
          />
        </div>
      </div>

      {/* ── 当前步骤横幅（运行中显示，带打字动画） ── */}
      {activeNode && (
        <div className="mb-4 flex items-center gap-3 rounded-xl border border-[#24415E]/20 bg-[#24415E]/5 px-4 py-3 animate-step-in">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#24415E] text-white animate-soft-pulse">
            <Loader2 className="h-4 w-4 animate-spin" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
              <span>{activeTeam?.name ?? activeNode}</span>
              <span className="font-normal text-muted-foreground/70">正在</span>
              <span className="text-[#24415E]">{activeMessage}</span>
              <TypingDotsInline />
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              模型：{modelOf(activeTeam?.nodes ?? [activeNode]) ?? '—'}
            </div>
          </div>
        </div>
      )}
      {!activeNode && !assembleDone && (
        <div className="mb-4 rounded-xl border border-dashed px-4 py-3 text-[12px] text-muted-foreground animate-step-in">
          排队等待调度：任务即将开始…
        </div>
      )}

      <div className="divide-y divide-border/60">
        {TEAM.map((member) => {
          const phase = phaseOf(member.nodes, nodeStatus, { productStatus })
          const model = modelOf(member.nodes)
          return (
            <AgentStatus
              key={`${member.name}-${phase}`}
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

      {/* ── 真实执行事件（后端 progress_log） ── */}
      {logs && logs.length > 0 && (
        <div className="mt-5 rounded-xl border border-border/60 bg-card/60 p-4">
          <div className="mb-2.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
            执行事件（实时）
          </div>
          <div className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
            {logs.slice(-30).map((ev, i) => (
              <div key={`${ev.ts}-${i}`} className="flex items-start gap-2 text-[11px] leading-snug">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#24415E]/50" />
                <span className="shrink-0 text-muted-foreground/70">
                  {new Date(ev.ts).toLocaleTimeString('zh-CN', { hour12: false })}
                </span>
                <span className="shrink-0 font-medium text-foreground/90">{ev.node}</span>
                <span className={cn(
                  'shrink-0 rounded px-1 py-px text-[10px]',
                  ev.status === 'completed' && 'bg-emerald-500/10 text-emerald-600',
                  ev.status === 'running' && 'bg-sky-500/10 text-sky-600',
                  ev.status === 'failed' && 'bg-red-500/10 text-red-600',
                )}>
                  {ev.status}
                </span>
                {ev.detail && <span className="min-w-0 flex-1 truncate text-muted-foreground" title={ev.detail}>{ev.detail}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
