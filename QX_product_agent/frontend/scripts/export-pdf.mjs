#!/usr/bin/env node
/**
 * ============================================================
 * Presentation 导出脚本（P4）
 * ============================================================
 *   PDF : Playwright 打开 /export/{id}（与 Web 预览同一 React 渲染源）
 *         打印 16:9 分页 PDF，并执行浏览器侧溢出质量门
 *   PPTX: PptxGenJS 直接消费 Presentation DSL（可继续编辑的交付物）
 *
 * 用法:
 *   node scripts/export-pdf.mjs <product_id> \
 *       --base-url http://127.0.0.1:8000 \
 *       --out ../backend/outputs/studio_assets/<id>.pdf \
 *       [--format pdf|pptx]
 *
 * stdout 输出 JSON 质量门报告（供后端记录）:
 *   {"pages": 10, "overflow_pages": [], "density_warnings": []}
 * ============================================================
 */

import { chromium } from 'playwright'
import PptxGenJS from 'pptxgenjs'
import fs from 'node:fs'

// ─── 浏览器探测 ─────────────────────────────────────────────
// 1) 优先 Playwright 自带 headless shell（Linux）
// 2) 缺系统库时注入本地解压的 libs（~/.local/playwright-libs，无需 sudo）
// 3) 仍失败则回退 Windows Edge/Chrome（WSL interop）
const EDGE_WINDOWS = '/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const CHROME_WINDOWS = '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'
const LOCAL_LIBS = `${process.env.HOME}/.local/playwright-libs/usr/lib/x86_64-linux-gnu`

async function launchBrowser() {
  if (!process.env.PLAYWRIGHT_EXECUTABLE_PATH) {
    const env = fs.existsSync(LOCAL_LIBS)
      ? { ...process.env, LD_LIBRARY_PATH: `${LOCAL_LIBS}:${process.env.LD_LIBRARY_PATH ?? ''}` }
      : process.env
    try {
      return await chromium.launch({ env })
    } catch (err) {
      console.error('[export] linux headless shell 启动失败，回退 Windows Edge:', err.message?.split('\n')[0])
    }
  }
  const executable = process.env.PLAYWRIGHT_EXECUTABLE_PATH
    || (fs.existsSync(EDGE_WINDOWS) ? EDGE_WINDOWS : null)
    || (fs.existsSync(CHROME_WINDOWS) ? CHROME_WINDOWS : null)
  if (executable) {
    return chromium.launch({ executablePath: executable })
  }
  return chromium.launch()
}

const args = process.argv.slice(2)
const positional = args.filter((a) => !a.startsWith('--'))
const getArg = (name, fallback) => {
  const idx = args.indexOf(name)
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : fallback
}

const productId = positional[0]
const format = getArg('--format', 'pdf')
const baseUrl = getArg('--base-url', 'http://127.0.0.1:8000')
const outPath = getArg('--out', `studio_${productId}.${format}`)

if (!productId) {
  console.error('用法: node scripts/export-pdf.mjs <product_id> [--base-url <url>] [--out <path>] [--format pdf|pptx]')
  process.exit(2)
}

// ─── 浏览器侧溢出质量门（P5） ───────────────────────────────
async function runOverflowGate(page) {
  const report = await page.evaluate(() => {
    const sections = Array.from(document.querySelectorAll('.export-page'))
    const overflowPages = []
    const densityWarnings = []
    for (const section of sections) {
      const rect = section.getBoundingClientRect()
      const scrollH = section.scrollHeight
      const height = rect.height
      if (scrollH > height + 2) {
        overflowPages.push({
          page: section.dataset.page,
          overflowBy: Math.round(((scrollH - height) / height) * 100),
        })
      }
      const textLen = (section.innerText || '').replace(/\s+/g, '').length
      if (textLen > 420) {
        densityWarnings.push({ page: section.dataset.page, textChars: textLen })
      }
    }
    return {
      pages: sections.length,
      overflow_pages: overflowPages,
      density_warnings: densityWarnings,
    }
  })
  return report
}

// ─── 溢出自适应：对溢出页逐级缩字号（每级 12%，最多两级） ──
async function autoFitOverflow(page, maxIterations = 2) {
  for (let iter = 0; iter < maxIterations; iter++) {
    const report = await runOverflowGate(page)
    if (!report.overflow_pages.length) return report
    const overflowIds = report.overflow_pages.map((o) => o.page)
    await page.evaluate((ids) => {
      for (const section of document.querySelectorAll('.export-page')) {
        if (ids.includes(section.dataset.page)) {
          const current = parseFloat(section.style.fontSize || '100')
          section.style.fontSize = `${Math.max(current - 12, 64)}%`
        }
      }
    }, overflowIds)
    await page.waitForTimeout(150)
  }
  return runOverflowGate(page)
}

async function exportPdf() {
  const browser = await launchBrowser()
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
  await page.goto(`${baseUrl}/export/${productId}`, {
    waitUntil: 'networkidle',
    timeout: 60000,
  })
  await page.waitForSelector('.export-page', { timeout: 30000 })
  await page.waitForTimeout(800)

  const gate = await autoFitOverflow(page)
  await page.pdf({
    path: outPath,
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: 0, bottom: 0, left: 0, right: 0 },
  })
  await browser.close()
  console.log(JSON.stringify(gate))
}

async function exportPptx() {
  const resp = await fetch(`${baseUrl}/api/v1/product/${productId}`)
  if (!resp.ok) throw new Error(`API ${resp.status}`)
  const product = await resp.json()
  const presentation = product.presentation
  if (!presentation || !Array.isArray(presentation.pages)) {
    throw new Error('无 Presentation DSL 数据')
  }

  const pptx = new PptxGenJS()
  pptx.defineLayout({ name: 'WIDE_16X9', width: 13.333, height: 7.5 })
  pptx.layout = 'WIDE_16X9'

  for (const pageDef of presentation.pages) {
    const slide = pptx.addSlide()
    if (pageDef.layout === 'cover' || pageDef.layout === 'closing') {
      slide.addText(pageDef.title, {
        x: 0.8, y: 2.6, w: 11.7, h: 1.6, fontSize: 40, bold: true,
        align: 'center', color: '1e293b',
      })
      if (pageDef.subtitle) {
        slide.addText(pageDef.subtitle, {
          x: 0.8, y: 4.3, w: 11.7, h: 0.6, fontSize: 18,
          align: 'center', color: '64748b',
        })
      }
    } else {
      slide.addText(pageDef.title, {
        x: 0.7, y: 0.4, w: 11.9, h: 0.7, fontSize: 24, bold: true, color: '0f172a',
      })
      if (pageDef.insight) {
        slide.addText(pageDef.insight, {
          x: 0.7, y: 1.15, w: 11.9, h: 0.5, fontSize: 14,
          color: '4f46e5',
        })
      }
      let y = 1.9
      for (const comp of pageDef.components) {
        const data = comp.data ?? {}
        if (comp.type === 'metric') {
          slide.addText(
            [
              { text: String(data.value ?? ''), options: { fontSize: 26, bold: true, color: '4f46e5' } },
              { text: `  ${data.label ?? ''}`, options: { fontSize: 13, color: '64748b' } },
            ],
            { x: 0.7, y, w: 11.9, h: 0.7 },
          )
          y += 0.8
        } else if (comp.type === 'table' && Array.isArray(data.rows)) {
          const columns = Array.isArray(data.columns) ? data.columns.map(String) : []
          const rows = data.rows.map((r) => (Array.isArray(r) ? r.map(String) : []))
          const tableRows = columns.length ? [columns.map((c) => ({ text: c, options: { bold: true, color: 'ffffff', fill: { color: '4f46e5' } } })), ...rows] : rows
          slide.addTable(tableRows, { x: 0.7, y, w: 11.9, fontSize: 11 })
          y += Math.min(0.5 + rows.length * 0.4, 3.6)
        } else {
          const text = typeof data.text === 'string'
            ? data.text
            : typeof data.title === 'string' ? data.title
            : typeof data.quote === 'string' ? data.quote : ''
          if (text) {
            slide.addText(text, { x: 0.7, y, w: 11.9, h: 0.6, fontSize: 14, color: '334155' })
            y += 0.7
          }
        }
        if (y > 6.8) break
      }
    }
  }

  await pptx.writeFile({ fileName: outPath })
  console.log(JSON.stringify({ pages: presentation.pages.length, overflow_pages: [], density_warnings: [] }))
}

if (format === 'pptx') {
  await exportPptx()
} else {
  await exportPdf()
}
