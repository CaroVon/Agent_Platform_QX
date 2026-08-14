import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/common/dialog'
import { Button } from '@/components/common/button'
import { Input } from '@/components/common/input'
import { useCreateProject } from '@/hooks/useProjects'
import { projectsApi } from '@/lib/api'

interface CreateProjectModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const TEMPLATE_OPTIONS = [
  { value: 'product', label: '📊 产品预研', desc: '聚焦产品定位、功能、竞品、定价' },
  { value: 'design', label: '🎨 工业设计推演', desc: '聚焦设计语言、CMF、人机工程' },
] as const

const SEARCH_DEPTH_OPTIONS = [
  { value: 5, label: '⚡ 快速', desc: '5 篇资料' },
  { value: 10, label: '📊 标准', desc: '10 篇资料' },
  { value: 15, label: '🔍 深度', desc: '15 篇资料' },
  { value: 20, label: '🚀 极致', desc: '20 篇资料' },
] as const

const IMAGES_PER_PAGE_OPTIONS = [
  { value: 0, label: '关闭', desc: '不搜索' },
  { value: 1, label: '1 张', desc: '最少' },
  { value: 2, label: '2 张', desc: '默认' },
  { value: 3, label: '3 张', desc: '较多' },
  { value: 5, label: '5 张', desc: '最多' },
] as const

/**
 * "新建分析" 模态框
 *
 * 用户选择模板类型 + 搜索强度 + 输入 Topic + 可选 Logo → 创建项目
 */
export function CreateProjectModal({ open, onOpenChange }: CreateProjectModalProps) {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [templateType, setTemplateType] = useState<string>('product')
  const [searchDepth, setSearchDepth] = useState<number>(10)
  const [imagesPerPage, setImagesPerPage] = useState<number>(2)
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const createProject = useCreateProject()

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null
    if (file && file.size > 2 * 1024 * 1024) {
      // 客户端预检：超过 2MB 拒绝
      return
    }
    setLogoFile(file)
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => setLogoPreview(reader.result as string)
      reader.readAsDataURL(file)
    } else {
      setLogoPreview(null)
    }
  }

  const resetForm = () => {
    setTopic('')
    setTemplateType('product')
    setSearchDepth(10)
    setImagesPerPage(2)
    setLogoFile(null)
    setLogoPreview(null)
  }

  const handleSubmit = async () => {
    if (!topic.trim()) return

    try {
      const result = await createProject.mutateAsync({
        topic: topic.trim(),
        template_type: templateType,
        search_depth: searchDepth,
        images_per_page: imagesPerPage,
      })

      // 如果选择了 Logo，在项目创建后上传
      if (logoFile && result.project.id) {
        try {
          await projectsApi.uploadLogo(result.project.id, logoFile)
        } catch (err) {
          console.warn('Logo 上传失败，将跳过:', err)
          // 非致命错误：不阻塞跳转
        }
      }

      onOpenChange(false)
      resetForm()
      navigate(`/projects/${result.project.id}/workspace`)
    } catch {
      // 错误由 React Query 处理
    }
  }

  // 按钮样式（复用模板选择器的样式模式）
  const radioBtnCls = (active: boolean) =>
    `flex flex-col items-center justify-center gap-0.5 rounded-lg border px-2 py-2.5 text-center transition-colors ${
      active
        ? 'border-primary bg-primary/5 ring-1 ring-primary'
        : 'border-border hover:bg-muted/50'
    }`

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>新建产品分析</DialogTitle>
          <DialogDescription>
            输入您想要分析的产品或主题，AI 将自动生成深度分析报告。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* ─── 模板类型选择 ──────────────────────────────── */}
          <div className="space-y-2">
            <label className="text-sm font-medium">报告模板</label>
            <div className="grid grid-cols-2 gap-2">
              {TEMPLATE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setTemplateType(opt.value)}
                  disabled={createProject.isPending}
                  className={`
                    flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2.5 text-left
                    transition-colors
                    ${templateType === opt.value
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted/50'
                    }
                  `}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-[11px] text-muted-foreground leading-tight">
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* ─── 搜索强度选择 ──────────────────────────────── */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              搜索深度
              <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                （控制资料检索数量）
              </span>
            </label>
            <div className="grid grid-cols-4 gap-2">
              {SEARCH_DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSearchDepth(opt.value)}
                  disabled={createProject.isPending}
                  className={radioBtnCls(searchDepth === opt.value)}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-[11px] text-muted-foreground leading-tight">
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* ─── 图片搜索强度选择 ──────────────────────────── */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              每页图片
              <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                （撰写时自动搜索并关联到每页幻灯片）
              </span>
            </label>
            <div className="grid grid-cols-5 gap-2">
              {IMAGES_PER_PAGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setImagesPerPage(opt.value)}
                  disabled={createProject.isPending}
                  className={radioBtnCls(imagesPerPage === opt.value)}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-[11px] text-muted-foreground leading-tight">
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* ─── 分析主题输入 ──────────────────────────────── */}
          <div className="space-y-2">
            <label htmlFor="topic" className="text-sm font-medium">
              分析主题
            </label>
            <Input
              id="topic"
              placeholder="例如：智能手表产品分析、新能源汽车竞品对比..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !createProject.isPending) {
                  handleSubmit()
                }
              }}
              disabled={createProject.isPending}
              autoFocus
            />
          </div>

          {/* ─── Logo 上传（可选） ─────────────────────────── */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              项目 Logo
              <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                （可选，将显示在幻灯片左上角）
              </span>
            </label>
            <div className="flex items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground hover:bg-muted/50 transition-colors">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
                  onChange={handleLogoChange}
                  disabled={createProject.isPending}
                  className="hidden"
                />
                <span className="truncate max-w-[160px]">
                  {logoFile ? logoFile.name : '选择图片...'}
                </span>
              </label>
              {logoPreview && (
                <img
                  src={logoPreview}
                  alt="Logo preview"
                  className="h-10 w-16 rounded border border-border object-contain"
                />
              )}
              {logoFile && (
                <button
                  type="button"
                  onClick={() => {
                    setLogoFile(null)
                    setLogoPreview(null)
                  }}
                  className="text-[11px] text-muted-foreground hover:text-destructive"
                >
                  移除
                </button>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={createProject.isPending}
          >
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            loading={createProject.isPending}
            disabled={!topic.trim()}
          >
            提交分析
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
