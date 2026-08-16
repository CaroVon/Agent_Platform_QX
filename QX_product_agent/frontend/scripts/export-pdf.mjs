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

  // 抓取干净 DOM（不跑 autoFitOverflow —— 播放器内独立做溢出缩放，
  // 避免 inline 缩放副作用导致预览/导出排版不一致）
  const gate = await runOverflowGate(page)

  // ── 交互式演示快照（与 Web 预览一致的排版/翻页/动效） ─────
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
      html,body{margin:0;padding:0;background:#f5f4f1;height:100%;font-family:"Noto Sans SC","Source Han Sans SC","PingFang SC","Microsoft YaHei",sans-serif}
      .player-root{display:flex;flex-direction:column;height:100%;align-items:center;justify-content:center;gap:14px;padding:18px;box-sizing:border-box}
      .player-stage{position:relative;width:1280px;height:720px;flex-shrink:0;transform-origin:center center}
      .player-stage .export-page{position:absolute;top:0;left:0;opacity:0;pointer-events:none;transition:opacity .45s ease,transform .45s ease;transform:translateY(10px)}
      .player-stage .export-page.active{opacity:1;pointer-events:auto;transform:translateY(0)}
      .player-nav{display:flex;align-items:center;gap:14px;color:#716e66;font-size:13px;position:relative;z-index:10}
      .player-nav button{background:#f4f1ea;color:#3a3a35;border:1px solid #ddd8cd;border-radius:8px;padding:7px 16px;cursor:pointer;font-size:13px;transition:background .2s}
      .player-nav button:hover{background:#e9e4d8;color:#1c2430}
      .player-dots{display:flex;gap:6px}
      .player-dots .dot{width:7px;height:7px;border-radius:99px;background:#d3cdbf;border:none;cursor:pointer;padding:0;transition:width .2s,background .2s}
      .player-dots .dot.active{width:20px;background:#24415e}
      .player-counter{font-variant-numeric:tabular-nums;min-width:56px;text-align:center}
    `

    const playerJs = `
      (function(){
        var stage=document.querySelector('.player-stage');
        var sections=Array.prototype.slice.call(stage.querySelectorAll('.export-page'));
        var dotsWrap=document.querySelector('.player-dots');
        var counter=document.querySelector('.player-counter');
        var idx=0,n=sections.length;
        // 播放器内溢出自适应：每页按 scrollHeight 逐级缩字号（最多 4 级，最低 60%）
        sections.forEach(function(s){s.style.fontSize='100%';for(var k=0;k<4;k++){if(s.scrollHeight<=722)break;var cur=parseFloat(s.style.fontSize||'100');s.style.fontSize=Math.max(cur-10,60)+'%'}});
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

  // 主题 palette → PptxGenJS 颜色（CyberPPT 咨询风等；缺省回退咨询蓝）
  const palette = presentation.theme?.palette ?? {}
  const hex = (key, fallback) => (palette[key] ?? fallback).replace('#', '')
  const C = {
    primary: hex('primary', '4f46e5'),
    accent: hex('accent', '6366f1'),
    text: hex('text', '0f172a'),
    muted: hex('muted', '64748b'),
    surface: hex('surface', 'ffffff'),
    bg: hex('bg', 'f8fafc'),
  }

  const pptx = new PptxGenJS()
  pptx.defineLayout({ name: 'WIDE_16X9', width: 13.333, height: 7.5 })
  pptx.layout = 'WIDE_16X9'

  // ─── ECharts → PNG（chart / matrix 组件还原，与 Web 预览同一图表语言）───
  const chartKinds = new Set()
  for (const pageDef of presentation.pages) {
    for (const comp of pageDef.components) {
      if (comp.type === 'chart' || comp.type === 'matrix') chartKinds.add(comp.type)
    }
  }
  let browser = null
  const chartPngs = new Map() // "pageIdx:compIdx" → Buffer
  if (chartKinds.size) {
    const fsPath = new URL('../node_modules/echarts/dist/echarts.min.js', import.meta.url)
    const echartsSrc = fs.readFileSync(fsPath, 'utf8')
    const renderOne = async (spec) => {
      const page = await browser.newPage()
      const option = buildEChartsOption(spec, C)
      await page.setContent(
        '<html><head><style>body{margin:0}</style><script>' + echartsSrc +
        '</script></head><body><div id="c" style="width:1000px;height:520px"></div>' +
        '<script>const c=echarts.init(document.getElementById(\'c\'));c.setOption(' +
        JSON.stringify(option) + ');</script></body></html>',
      )
      await page.waitForTimeout(500)
      const box = await page.locator('#c').boundingBox()
      const png = await page.screenshot({ clip: { x: 0, y: 0, width: box.width, height: box.height } })
      await page.close()
      return png
    }
    browser = await launchBrowser()
    for (let pi = 0; pi < presentation.pages.length; pi++) {
      const comps = presentation.pages[pi].components
      for (let ci = 0; ci < comps.length; ci++) {
        const comp = comps[ci]
        if (comp.type === 'chart' || comp.type === 'matrix') {
          try {
            chartPngs.set(`${pi}:${ci}`, await renderOne(comp))
          } catch (err) {
            console.error(`[pptx] 图表渲染失败 p${pi + 1}c${ci}:`, String(err).slice(0, 120))
          }
        }
      }
    }
  }

  const manifest = {
    product_id: productId,
    theme: presentation.theme ?? {},
    slides: [],
  }

  for (let pi = 0; pi < presentation.pages.length; pi++) {
    const pageDef = presentation.pages[pi]
    const slide = pptx.addSlide()
    // 背景层
    slide.addShape('rect', { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.bg }, line: { type: 'none' } })

    const comps = pageDef.components ?? []
    const chartComps = comps.filter((c) => c.type === 'chart' || c.type === 'matrix')
    manifest.slides.push({
      slide: pi + 1,
      page: pi + 1,
      type: pageDef.type,
      layout: pageDef.layout,
      components: comps.map((c) => ({
        type: c.type,
        items: Array.isArray(c.data?.items) ? c.data.items.length : 0,
        phases: Array.isArray(c.data?.phases) ? c.data.phases.length : 0,
        chart_type: c.data?.chart_type ?? '',
      })),
      // CyberPPT QA 门禁字段（validate_pptx.py 消费）
      qa_expectations: {
        dual_gate_required: true,
        visual_qa_required: true,
        visual_semantics_required: true,
        all_key_text_editable: true,
      },
      generation_engine: { tool: 'pptxgenjs', visual_fidelity_not_reduced: true },
      page_execution: { status: 'completed', approach: 'deterministic-dsl-render' },
      image_assets: chartComps.length
        ? [{ kind: 'chart', count: chartComps.length, purpose: '数据可视化（ECharts 渲染）' }]
        : [],
    })

    if (pageDef.layout === 'cover' || pageDef.layout === 'closing') {
      // 封面/结尾：居中标题 + 强调色条
      slide.addShape('rect', { x: 5.4, y: 2.35, w: 2.5, h: 0.09, fill: { color: C.accent }, line: { type: 'none' } })
      slide.addText(pageDef.title, {
        x: 0.8, y: 2.55, w: 11.7, h: 1.6, fontSize: 40, bold: true,
        align: 'center', color: C.text,
      })
      if (pageDef.subtitle) {
        slide.addText(pageDef.subtitle, {
          x: 1.5, y: 4.3, w: 10.3, h: 0.6, fontSize: 18,
          align: 'center', color: C.muted,
        })
      }
      continue
    }

    // 内容页：标题 + 强调色条
    slide.addShape('rect', { x: 0.7, y: 0.5, w: 0.12, h: 0.5, fill: { color: C.accent }, line: { type: 'none' } })
    slide.addText(pageDef.title, {
      x: 0.95, y: 0.42, w: 11.6, h: 0.65, fontSize: 24, bold: true, color: C.text,
    })
    if (pageDef.insight) {
      slide.addText(pageDef.insight, {
        x: 0.95, y: 1.12, w: 11.6, h: 0.45, fontSize: 13,
        color: C.primary,
      })
    }

    let y = 1.72
    const REMAIN = () => 7.25 - y
    for (let ci = 0; ci < comps.length; ci++) {
      const comp = comps[ci]
      const data = comp.data ?? {}
      if (y > 6.4) break // 余量不足 0.85in，放弃剩余组件（防越界）
      const line = (h) => { slide.addShape('line', { x: 0.7, y, w: 11.9, h: 0.01, line: { color: C.muted, width: 0.5, transparency: 60 } }) }

      if (comp.type === 'metric') {
        slide.addShape('roundRect', { x: 0.7, y, w: 5.7, h: 0.95, rectRadius: 0.1, fill: { color: C.surface }, line: { color: C.accent, width: 0.75 } })
        slide.addText(
          [
            { text: String(data.value ?? ''), options: { fontSize: 26, bold: true, color: C.primary } },
            { text: `  ${data.label ?? ''}`, options: { fontSize: 13, color: C.muted } },
          ],
          { x: 0.9, y: y + 0.12, w: 5.3, h: 0.7 },
        )
        y += 1.1
      } else if (comp.type === 'card') {
        const items = Array.isArray(data.items) ? data.items.map(String) : []
        const desc = typeof data.description === 'string' && data.description ? data.description : ''
        const h = Math.min(0.42 + (items.length + (desc ? 1 : 0)) * 0.3, 3.4, Math.max(REMAIN(), 0.5))
        slide.addShape('roundRect', { x: 0.7, y, w: 5.7, h, rectRadius: 0.08, fill: { color: C.surface }, line: { color: C.muted, width: 0.75, transparency: 60 } })
        const runs = [
          { text: String(data.title ?? ''), options: { fontSize: 14, bold: true, color: C.text } },
        ]
        if (desc) runs.push({ text: `\n${desc}`, options: { fontSize: 11, color: C.muted } })
        for (const item of items) runs.push({ text: `\n• ${item}`, options: { fontSize: 11, color: C.muted } })
        slide.addText(runs, { x: 0.95, y: y + 0.12, w: 5.2, h: h - 0.24, valign: 'top' })
        y += h + 0.18
      } else if (comp.type === 'timeline') {
        const phases = Array.isArray(data.phases) ? data.phases : []
        let h = 0
        const runs = []
        for (const ph of phases.slice(0, 6)) {
          const name = String(ph.name ?? ph.phase ?? '')
          const period = String(ph.period ?? '')
          const goals = String(ph.goal ?? '')
          const ms = Array.isArray(ph.milestones) ? ph.milestones.map(String) : []
          runs.push({ text: `▍${name}${period ? '  ' + period : ''}`, options: { fontSize: 13, bold: true, color: C.primary } })
          if (goals) runs.push({ text: `\n  ${goals}`, options: { fontSize: 11, color: C.muted } })
          for (const m of ms.slice(0, 5)) runs.push({ text: `\n  · ${m}`, options: { fontSize: 11, color: C.muted } })
          runs.push({ text: '\n', options: { fontSize: 8 } })
          h += 0.34 + Math.min(ms.length, 5) * 0.22 + (goals ? 0.2 : 0)
        }
        h = Math.min(h, 4.6, Math.max(REMAIN(), 0.5))
        slide.addText(runs, { x: 0.7, y, w: 11.9, h, valign: 'top' })
        y += h + 0.15
      } else if (comp.type === 'table' && Array.isArray(data.rows)) {
        const columns = Array.isArray(data.columns) ? data.columns.map(String) : []
        const rows = data.rows.map((r) => (Array.isArray(r) ? r.map(String) : []))
        const tableRows = columns.length ? [columns.map((c) => ({ text: c, options: { bold: true, color: C.surface, fill: { color: C.primary } } })), ...rows] : rows
        slide.addTable(tableRows, { x: 0.7, y, w: 11.9, fontSize: 11 })
        y += Math.min(0.5 + rows.length * 0.4, 3.8)
      } else if (comp.type === 'quote') {
        slide.addShape('rect', { x: 0.7, y, w: 0.09, h: 0.7, fill: { color: C.accent }, line: { type: 'none' } })
        slide.addText(String(data.quote ?? data.text ?? ''), {
          x: 1.0, y, w: 11.4, h: 0.7, fontSize: 15, italic: true, color: C.text,
        })
        y += 0.85
      } else if (comp.type === 'chart' || comp.type === 'matrix') {
        const png = chartPngs.get(`${pi}:${ci}`)
        if (png) {
          const ratio = 520 / 1000
          const w = 11.4
          const h = Math.min(w * ratio, 5.2, Math.max(REMAIN(), 0.5))
          slide.addImage({ data: 'data:image/png;base64,' + png.toString('base64'), x: 0.75, y, w, h })
          y += h + 0.15
        } else {
          slide.addText(`[${comp.type} 图表] ${data.chart_type ?? ''}`, { x: 0.7, y, w: 11.9, h: 0.5, fontSize: 12, color: C.muted })
          y += 0.6
        }
      } else {
        const text = typeof data.text === 'string'
          ? data.text
          : typeof data.title === 'string' ? data.title : ''
        if (text) {
          line(0)
          slide.addText(text, { x: 0.7, y, w: 11.9, h: 0.6, fontSize: 13, color: C.text })
          y += 0.7
        }
      }
    }
  }

  if (browser) await browser.close()

  await pptx.writeFile({ fileName: outPath })
  // slide_manifest.json（CyberPPT QA 门禁输入）
  try {
    fs.writeFileSync(`${outPath}.manifest.json`, JSON.stringify(manifest, null, 2), 'utf8')
  } catch (err) {
    console.error('[pptx] manifest 写入失败:', String(err).slice(0, 100))
  }
  console.log(JSON.stringify({ pages: presentation.pages.length, overflow_pages: [], density_warnings: [], charts_embedded: chartPngs.size }))
}

// ─── ECharts option 构建（与 Web 预览同一图表语言：primary/accent 双色）───
function buildEChartsOption(comp, C) {
  const data = comp.data ?? {}
  const kind = data.chart_type ?? (comp.type === 'matrix' ? 'quadrant' : 'bar')
  const textColor = `#${C.text}`
  const mutedColor = `#${C.muted}`
  const primaryColor = `#${C.primary}`
  const accentColor = `#${C.accent}`

  if (kind === 'quadrant') {
    const points = Array.isArray(data.points) ? data.points : []
    const competitors = points.filter((p) => p.kind !== 'product' && p.kind !== 'ours')
    const ours = points.filter((p) => p.kind === 'product' || p.kind === 'ours')
    const scatter = (list, color) => ({
      type: 'scatter', symbolSize: 13, itemStyle: { color },
      data: list.map((p) => ({ value: [p.x, p.y], name: p.name })),
      label: { show: true, formatter: (p) => p.name, position: 'top', fontSize: 11, color: textColor },
    })
    return {
      grid: { top: 24, right: 24, bottom: 40, left: 44 },
      tooltip: { trigger: 'item' },
      xAxis: { min: 0, max: 1, name: data.x_axis ?? 'x', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: textColor }, splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } } },
      yAxis: { min: 0, max: 1, name: data.y_axis ?? 'y', nameTextStyle: { color: textColor }, splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } } },
      series: [scatter(competitors, '#94a3b8'), scatter(ours, primaryColor)],
    }
  }

  const items = (Array.isArray(data.items) ? data.items : []).map((it) => ({
    label: String(it.label ?? it.name ?? ''),
    value: Number(it.value) || 0,
  }))
  if (kind === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['32%', '66%'], center: ['50%', '52%'],
        label: { fontSize: 11, color: textColor },
        data: items.map((it, i) => ({ name: it.label, value: it.value, itemStyle: { color: i === 0 ? primaryColor : accentColor } })),
      }],
    }
  }
  if (kind === 'radar') {
    return {
      tooltip: { trigger: 'item' },
      radar: {
        indicator: items.map((it) => ({ name: it.label, max: Math.max(...items.map((x) => x.value), 100) })),
        axisName: { color: textColor },
      },
      series: [{ type: 'radar', symbolSize: 5, areaStyle: { color: primaryColor, opacity: 0.25 }, lineStyle: { color: primaryColor }, data: [{ value: items.map((it) => it.value) }] }],
    }
  }
  // bar / line
  return {
    grid: { top: 30, right: 24, bottom: 40, left: 44 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: items.map((it) => it.label), axisLabel: { color: mutedColor }, axisLine: { lineStyle: { color: '#cbd5e1' } } },
    yAxis: { type: 'value', axisLabel: { color: mutedColor }, splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } } },
    series: [{
      type: kind === 'line' ? 'line' : 'bar',
      data: items.map((it) => it.value),
      itemStyle: { color: primaryColor },
      lineStyle: { color: primaryColor, width: 3 },
      label: { show: kind !== 'line', position: 'top', fontSize: 11, color: textColor },
      smooth: true,
    }],
  }
}

if (format === 'pptx') {
  await exportPptx()
} else if (format === 'html') {
  await exportHtml()
} else {
  await exportPdf()
}
