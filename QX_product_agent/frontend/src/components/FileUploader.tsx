/**
 * FileUploader —— 本地文件上传（拖拽 + 进度 + 预览 + 移除）
 *
 * 文本类（pdf/md/txt/doc/docx）→ POST /projects/{id}/upload-docs（入库检索）
 * 图片类（png/jpg/webp）      → POST /projects/{id}/assets（持久化为项目素材）
 *                             → imageKb=true 时：POST /projects/{id}/kb-images（VL 分析入库）
 * 使用 XMLHttpRequest 提供真实上传进度。
 */

import { useCallback, useRef, useState } from 'react'
import { FileText, Image as ImageIcon, Loader2, UploadCloud, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { API_BASE } from '@/lib/api'

interface UploadItem {
  key: string
  name: string
  size: number
  kind: 'doc' | 'image'
  progress: number
  status: 'uploading' | 'done' | 'error'
  previewUrl?: string
  error?: string
}

const DOC_EXT = ['pdf', 'md', 'markdown', 'txt', 'doc', 'docx']
const IMG_EXT = ['png', 'jpg', 'jpeg', 'webp']

function extOf(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? ''
}

function uploadWithProgress(
  url: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<{ ok: boolean; body: unknown }> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        /* ignore */
      }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, body })
    }
    xhr.onerror = () => resolve({ ok: false, body: null })
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}

export function FileUploader({
  projectId,
  imageKb = false,
}: {
  projectId: string
  /** 图片知识库模式：图片走 /kb-images 触发 MiniMax VL 分析入库（而非仅存素材） */
  imageKb?: boolean
}) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      for (const file of Array.from(files)) {
        const ext = extOf(file.name)
        const kind: UploadItem['kind'] = IMG_EXT.includes(ext)
          ? 'image'
          : DOC_EXT.includes(ext)
            ? 'doc'
            : (undefined as never)
        if (!kind) continue

        const key = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2)}`
        const item: UploadItem = {
          key,
          name: file.name,
          size: file.size,
          kind,
          progress: 0,
          status: 'uploading',
          previewUrl: kind === 'image' ? URL.createObjectURL(file) : undefined,
        }
        setItems((prev) => [item, ...prev])

        // 图片知识库模式：图片走 VL 分析入库；其余走原路径
        const url =
          kind === 'image' && imageKb
            ? `${API_BASE}/projects/${projectId}/kb-images`
            : kind === 'image'
              ? `${API_BASE}/projects/${projectId}/assets`
              : `${API_BASE}/projects/${projectId}/upload-docs`

        const result = await uploadWithProgress(url, file, (pct) =>
          setItems((prev) => prev.map((i) => (i.key === key ? { ...i, progress: pct } : i))),
        )
        setItems((prev) =>
          prev.map((i) =>
            i.key === key
              ? {
                  ...i,
                  status: result.ok ? 'done' : 'error',
                  progress: result.ok ? 100 : i.progress,
                  error: result.ok ? undefined : '上传失败',
                }
              : i,
          ),
        )
      }
    },
    [projectId],
  )

  return (
    <div>
      {/* ─── 拖拽上传区 ─────────────────────────────────────── */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors duration-150',
          dragging
            ? 'border-primary bg-primary/5'
            : 'border-border bg-card hover:border-primary/40 hover:bg-secondary/40',
        )}
      >
        <UploadCloud className="h-7 w-7 text-muted-foreground" />
        <p className="mt-3 text-sm font-medium">拖拽文件到此处，或点击选择</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {imageKb
            ? '支持 PNG / JPG / WEBP，上传后由 MiniMax 视觉分析自动入库'
            : '支持 PDF / Markdown / TXT / DOC / DOCX 与 PNG / JPG / WEBP'}
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={
            imageKb
              ? '.png,.jpg,.jpeg,.webp,.gif,.bmp'
              : '.pdf,.md,.markdown,.txt,.doc,.docx,.png,.jpg,.jpeg,.webp'
          }
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {/* ─── 文件列表（进度/预览/移除） ─────────────────────── */}
      {items.length > 0 && (
        <ul className="mt-4 space-y-2">
          {items.map((item) => (
            <li
              key={item.key}
              className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3"
            >
              {item.kind === 'image' && item.previewUrl ? (
                <img
                  src={item.previewUrl}
                  alt={item.name}
                  className="h-10 w-10 rounded-md object-cover"
                />
              ) : item.kind === 'image' ? (
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary">
                  <ImageIcon className="h-4 w-4 text-muted-foreground" />
                </div>
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                </div>
              )}

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{item.name}</span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {(item.size / 1024).toFixed(0)} KB
                  </span>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-secondary">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-200',
                      item.status === 'error' ? 'bg-destructive' : 'bg-primary',
                    )}
                    style={{ width: `${item.progress}%` }}
                  />
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  {item.status === 'uploading' && (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" /> 上传中 {item.progress}%
                    </>
                  )}
                  {item.status === 'done' &&
                    (item.kind === 'image' && imageKb
                      ? '✓ 已提交视觉分析入库'
                      : '✓ 已入库（可被 Agent 检索）')}
                  {item.status === 'error' && (
                    <span className="text-destructive">{item.error}</span>
                  )}
                </div>
              </div>

              <button
                type="button"
                title="移除"
                onClick={() => setItems((prev) => prev.filter((i) => i.key !== item.key))}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
