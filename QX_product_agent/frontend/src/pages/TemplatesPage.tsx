/**
 * TemplatesPage —— 模板中心（空态 + 扩展点）
 */

import { Briefcase, FileText, FlaskConical, LayoutTemplate, MonitorPlay } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { TemplateCard } from '@/components/TemplateCard'

const TEMPLATES = [
  {
    icon: Briefcase,
    title: '行业模板',
    description: '消费电子 / 智能硬件 / SaaS 等行业分析框架',
    tag: '研究',
    exampleIdea: '面向 Z 世代的智能睡眠健康枕（睡眠监测 + 助眠白噪音 + 智能闹钟）',
  },
  {
    icon: FlaskConical,
    title: '研究模板',
    description: '市场研究、竞品矩阵与趋势洞察的标准结构',
    tag: '研究',
    exampleIdea: '国潮风格智能床品',
  },
  {
    icon: FileText,
    title: 'PRD 模板',
    description: '产品概述、画像、功能与路线图章节规范',
    tag: 'PRD',
    exampleIdea: '一款面向独居青年的智能植物护理花盆',
  },
  {
    icon: MonitorPlay,
    title: '演示模板',
    description: '路演 / 咨询 / 发布三种叙事版式',
    tag: '演示',
    exampleIdea: '面向中小企业的 AI 客服工作台',
  },
  {
    icon: LayoutTemplate,
    title: '产品策略模板',
    description: '定位、差异化与进入策略分析框架',
    tag: '策略',
    exampleIdea: '宠物智能喂食器（远程喂养 + 健康管理）',
  },
]

export function TemplatesPage() {
  const navigate = useNavigate()
  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 模板"
        title="Templates"
        description="选择模板开始一个新的产品想法 —— 将自动带入示例想法到工作台。"
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATES.map((t) => (
          <TemplateCard
            key={t.title}
            icon={t.icon}
            title={t.title}
            description={t.description}
            tag={t.tag}
            onClick={() => navigate('/workspace', { state: { templateIdea: t.exampleIdea } })}
          />
        ))}
      </div>
    </div>
  )
}
