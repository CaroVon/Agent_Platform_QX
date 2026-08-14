/**
 * TemplatesPage —— 模板中心（空态 + 扩展点）
 */

import { Briefcase, FileText, FlaskConical, LayoutTemplate, MonitorPlay } from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { TemplateCard } from '@/components/TemplateCard'

const TEMPLATES = [
  {
    icon: Briefcase,
    title: '行业模板',
    description: '消费电子 / 智能硬件 / SaaS 等行业分析框架',
    tag: '研究',
  },
  {
    icon: FlaskConical,
    title: '研究模板',
    description: '市场研究、竞品矩阵与趋势洞察的标准结构',
    tag: '研究',
  },
  {
    icon: FileText,
    title: 'PRD 模板',
    description: '产品概述、画像、功能与路线图章节规范',
    tag: 'PRD',
  },
  {
    icon: MonitorPlay,
    title: '演示模板',
    description: '路演 / 咨询 / 发布三种叙事版式',
    tag: '演示',
  },
  {
    icon: LayoutTemplate,
    title: '产品策略模板',
    description: '定位、差异化与进入策略分析框架',
    tag: '策略',
  },
]

export function TemplatesPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 模板"
        title="Templates"
        description="可复用模板让生成结果更一致 —— 模板库建设中。"
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATES.map((t) => (
          <TemplateCard key={t.title} icon={t.icon} title={t.title} description={t.description} tag={t.tag} />
        ))}
      </div>
    </div>
  )
}
