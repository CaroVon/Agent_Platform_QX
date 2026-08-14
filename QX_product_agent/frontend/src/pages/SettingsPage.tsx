/**
 * SettingsPage —— 系统配置（表单壳，展示现行配置与配置方式）
 *
 * 不实现假保存逻辑：展示配置键与说明，引导用户通过环境变量配置。
 */

import { WorkspaceHeader } from '@/components/WorkspaceHeader'

function SettingBlock({
  title,
  description,
  rows,
}: {
  title: string
  description: string
  rows: { label: string; value: string; hint?: string }[]
}) {
  return (
    <section className="rounded-2xl border bg-card p-7 shadow-sm">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      <dl className="mt-5 divide-y">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-4 py-3.5">
            <dt className="w-52 shrink-0 text-sm text-muted-foreground">{row.label}</dt>
            <dd className="min-w-0 flex-1">
              <code className="block truncate rounded-md bg-secondary px-3 py-1.5 font-mono text-xs">
                {row.value}
              </code>
              {row.hint && <p className="mt-1 text-[11px] text-muted-foreground">{row.hint}</p>}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function SettingsPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 设置"
        title="Settings"
        description="模型、Agent 策略与工作区配置 —— 当前通过环境变量管理，配置项如下。"
      />

      <div className="space-y-6">
        <SettingBlock
          title="模型配置"
          description="多模型支持（DeepSeek / Qwen / GPT 兼容接口），演示节点可独立切换（如 Kimi）。"
          rows={[
            { label: '主模型', value: 'AGENT_PLATFORM_LLM_MODEL（默认 deepseek-chat）', hint: '由 DEEPSEEK_MODEL 桥接' },
            { label: '演示节点模型（可选）', value: 'AGENT_PLATFORM_PRESENTATION_LLM_MODEL / _BASE_URL / _API_KEY', hint: '未配置时回退主模型；配置 Kimi 即启用专用信息设计模型' },
          ]}
        />
        <SettingBlock
          title="Agent 策略配置"
          description="流水线节点重试与演示质量门参数。"
          rows={[
            { label: '节点重试次数', value: 'AGENT_PLATFORM_MAX_RETRIES（默认 2）' },
            { label: '演示评分阈值', value: 'PRESENTATION_SCORE_THRESHOLD（默认 80）', hint: '低于阈值触发 Critic 修订循环' },
            { label: '最大修订次数', value: 'PRESENTATION_MAX_REVISIONS（默认 2）' },
          ]}
        />
        <SettingBlock
          title="API Key 管理"
          description="密钥仅保存在后端 .env，不进入数据库与前端。"
          rows={[
            { label: '文本模型', value: 'DEEPSEEK_API_KEY' },
            { label: '搜索', value: 'TAVILY_API_KEY' },
            { label: '网页抓取', value: 'FIRECRAWL_API_KEY' },
            { label: '图像生成（可选）', value: 'SILICONFLOW_API_KEY' },
          ]}
        />
        <SettingBlock
          title="团队权限与工作区"
          description="多租户与团队协作能力规划中。"
          rows={[{ label: '状态', value: '规划中（架构已预留扩展点）' }]}
        />
      </div>
    </div>
  )
}
