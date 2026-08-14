/**
 * ai/ToolExecution —— 工具执行展示（真实能力映射）
 *
 * 按当前活跃节点展示团队正在使用的工具；无活跃节点时展示团队能力清单。
 */

import { BookOpen, Globe, Image as ImageIcon, LayoutGrid, ShieldCheck } from 'lucide-react'

const TOOL_POOL = {
  research: [
    { icon: Globe, name: 'Web Search', desc: '全网市场信息检索' },
    { icon: BookOpen, name: 'Document Retrieval', desc: '知识库文档召回' },
  ],
  competitor_analysis: [
    { icon: LayoutGrid, name: 'Competitor Matrix', desc: '竞品象限对比' },
  ],
  strategy: [
    { icon: BookOpen, name: 'Document Retrieval', desc: '上游研究结论读取' },
  ],
  presentation: [
    { icon: LayoutGrid, name: 'Layout Library', desc: '版式库排版决策' },
    { icon: ShieldCheck, name: 'Quality Gate', desc: '覆盖度与溢出检查' },
  ],
  design: [
    { icon: LayoutGrid, name: 'Component Library', desc: 'UI 组件规格' },
  ],
}

const ALL_TOOLS = [
  { icon: Globe, name: 'Web Search', desc: 'Tavily 全网搜索' },
  { icon: BookOpen, name: 'Document Retrieval', desc: '知识库 RAG 检索' },
  { icon: ImageIcon, name: 'Image Search', desc: 'DuckDuckGo 图片素材' },
  { icon: LayoutGrid, name: 'Layout Library', desc: '10 版式排版决策' },
  { icon: ShieldCheck, name: 'Quality Gate', desc: '质量门自动评审' },
]

function activeNode(nodeStatus: Record<string, string>): string | null {
  return (
    Object.entries(nodeStatus).find(([, s]) => s === 'running')?.[0] ?? null
  )
}

export function ToolExecution({ nodeStatus }: { nodeStatus: Record<string, string> }) {
  const active = activeNode(nodeStatus)
  const tools = active ? (TOOL_POOL[active as keyof typeof TOOL_POOL] ?? []) : null

  if (tools === null) {
    // 空闲/完成：展示团队能力清单
    return (
      <div className="space-y-2">
        {ALL_TOOLS.map((tool) => (
          <div key={tool.name} className="flex items-center gap-3 rounded-lg px-2 py-2">
            <tool.icon className="h-3.5 w-3.5 text-[#3F6B4F]" />
            <span className="text-xs font-medium">{tool.name}</span>
            <span className="flex-1 truncate text-[11px] text-muted-foreground/70">
              {tool.desc}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-[#3F6B4F]">
        正在使用
      </div>
      {tools.map((tool) => (
        <div
          key={tool.name}
          className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5"
        >
          <tool.icon className="h-3.5 w-3.5 animate-breathe text-[#3F6B4F]" />
          <span className="text-xs font-medium">{tool.name}</span>
          <span className="flex-1 truncate text-[11px] text-muted-foreground/70">
            {tool.desc}
          </span>
          <span className="rounded-full bg-[#3F6B4F]/10 px-2 py-0.5 text-[10px] text-[#3F6B4F]">
            运行中
          </span>
        </div>
      ))}
    </div>
  )
}
