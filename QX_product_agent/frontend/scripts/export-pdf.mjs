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
      // transform 兜底页（scale<1）：视觉已完整缩放，不再计溢出
      const transform = getComputedStyle(section).transform
      const scaleMatch = transform && transform !== 'none' ? parseFloat(transform.split('(')[1]) : 1
      if (scaleMatch < 1) continue
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

// ─── 溢出自适应 ─────────────────────────────────────────────
// 1) 逐级缩字号（每级 10%，最多三级，最低 64%）—— 流式重排
// 2) 仍溢出 → transform 视觉缩放兜底（内容完整，绝不截断）
async function autoFitOverflow(page, maxIterations = 3) {
  for (let iter = 0; iter < maxIterations; iter++) {
    const report = await runOverflowGate(page)
    if (!report.overflow_pages.length) return report
    const overflowIds = report.overflow_pages.map((o) => o.page)
    await page.evaluate((ids) => {
      for (const section of document.querySelectorAll('.export-page')) {
        if (ids.includes(section.dataset.page)) {
          const current = parseFloat(section.style.fontSize || '100')
          section.style.fontSize = `${Math.max(current - 10, 64)}%`
        }
      }
    }, overflowIds)
    await page.waitForTimeout(150)
  }
  // 终极兜底：transform 缩放（保留全部内容，仅视觉缩小）
  let report = await runOverflowGate(page)
  if (report.overflow_pages.length) {
    await page.evaluate(() => {
      for (const section of document.querySelectorAll('.export-page')) {
        const rect = section.getBoundingClientRect()
        const ratio = rect.height / (section.scrollHeight || 1)
        if (ratio < 1) {
          section.style.transform = `scale(${(ratio - 0.02).toFixed(3)})`
          section.style.transformOrigin = 'top left'
        }
      }
    })
    await page.waitForTimeout(150)
    report = await runOverflowGate(page)
  }
  return report
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

async function exportHtml() {
  const browser = await launchBrowser()
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
  await page.goto(`${baseUrl}/export/${productId}`, {
    waitUntil: 'networkidle',
    timeout: 60000,
  })
  await page.waitForSelector('.export-page', { timeout: 30000 })
  await page.waitForTimeout(800)

  const gate = await autoFitOverflow(page)

  // ── 交互式演示快照（导出后与 Web 预览一致的翻页/动效） ─────
  // 收集渲染样式 + DOM，注入原生 JS 播放器（翻页/键盘/进度点/过渡动画/自适应缩放）
  const html = await page.evaluate(() => {
    let css = ''
    for (const sheet of document.styleSheets) {
      try {
        for (const rule of sheet.cssRules) css += rule.cssText + '\n'
      } catch {
        /* 跳过跨域样式 */
      }
    }

    const root = document.getElementById('root')
    const clone = root.cloneNode(true)
    clone.querySelectorAll('script').forEach((s) => s.remove())
    const title = document.title || 'Presentation'

    const playerCss = `
      html,body{margin:0;padding:0;background:#0f1117;height:100%;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
      .player-root{display:flex;flex-direction:column;height:100%;align-items:center;justify-content:center;gap:14px;padding:18px;box-sizing:border-box}
      .player-stage{position:relative;width:1280px;height:720px;flex-shrink:0;transform-origin:center center}
      .player-stage .export-page{position:absolute;top:0;left:0;opacity:0;pointer-events:none;transition:opacity .45s ease,transform .45s ease;transform:translateY(10px)}
      .player-stage .export-page.active{opacity:1;pointer-events:auto;transform:translateY(0)}
      .player-nav{display:flex;align-items:center;gap:14px;color:#94a3b8;font-size:13px;position:relative;z-index:10}
      .player-nav button{background:#1e2534;color:#cbd5e1;border:1px solid #2a3348;border-radius:8px;padding:7px 16px;cursor:pointer;font-size:13px;transition:background .2s}
      .player-nav button:hover{background:#2a3348;color:#f1f5f9}
      .player-dots{display:flex;gap:6px}
      .player-dots .dot{width:7px;height:7px;border-radius:99px;background:#3a4560;border:none;cursor:pointer;padding:0;transition:width .2s,background .2s}
      .player-dots .dot.active{width:20px;background:#6366f1}
      .player-counter{font-variant-numeric:tabular-nums;min-width:56px;text-align:center}
    `

    const playerJs = `
      (function(){
        var stage=document.querySelector('.player-stage');
        var sections=Array.prototype.slice.call(stage.querySelectorAll('.export-page'));
        var dotsWrap=document.querySelector('.player-dots');
        var counter=document.querySelector('.player-counter');
        var idx=0,n=sections.length;
        sections.forEach(function(s,j){var d=document.createElement('button');d.className='dot';d.setAttribute('aria-label','第'+(j+1)+'页');d.onclick=function(){show(j)};dotsWrap.appendChild(d)});
        var dots=Array.prototype.slice.call(dotsWrap.children);
        function show(i){idx=((i%n)+n)%n;sections.forEach(function(s,j){s.classList.toggle('active',j===idx)});dots.forEach(function(d,j){d.classList.toggle('active',j===idx)});counter.textContent=(idx+1)+' / '+n}
        document.getElementById('prev').onclick=function(){show(idx-1)};
        document.getElementById('next').onclick=function(){show(idx+1)};
        document.addEventListener('keydown',function(e){if(e.key==='ArrowRight'||e.key==='PageDown')show(idx+1);if(e.key==='ArrowLeft'||e.key==='PageUp')show(idx-1);if(e.key==='Home')show(0);if(e.key==='End')show(n-1)});
        function fit(){var sw=window.innerWidth-36,sh=window.innerHeight-110;var s=Math.min(sw/1280,sh/720,1);stage.style.transform='scale('+s+')'}
        window.addEventListener('resize',fit);fit();show(0);
      })();
    `

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>${css}</style>
<style>${playerCss}</style>
</head>
<body>
<div class="player-root">
  <div class="player-stage">${clone.innerHTML}</div>
  <div class="player-nav">
    <button id="prev" type="button">← 上一页</button>
    <div class="player-dots"></div>
    <span class="player-counter"></span>
    <button id="next" type="button">下一页 →</button>
  </div>
</div>
<script>${playerJs}</script>
</body>
</html>`
  })
  fs.writeFileSync(outPath, html, 'utf-8')
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
} else if (format === 'html') {
  await exportHtml()
} else {
  await exportPdf()
}
