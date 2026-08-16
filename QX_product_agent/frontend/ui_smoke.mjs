// UI smoke test: visit key pages, collect console errors, take screenshots
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = 'http://localhost:5173'
const OUT = '/home/administrator/dev/agents/outputs/ui_smoke'
fs.mkdirSync(OUT, { recursive: true })

const pages = [
  ['/', 'dashboard'],
  ['/workspace', 'workspace'],
  ['/research', 'research'],
  ['/prd', 'prd'],
  ['/design', 'design'],
  ['/presentation', 'presentation'],
  ['/knowledge', 'knowledge'],
  ['/templates', 'templates'],
  ['/settings', 'settings'],
]

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const results = []
for (const [path, name] of pages) {
  const page = await ctx.newPage()
  const errors = []
  const warnings = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
    if (msg.type() === 'warning') warnings.push(msg.text())
  })
  page.on('pageerror', (err) => errors.push('PAGEERROR: ' + err.message))
  const t0 = Date.now()
  try {
    await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 30000 })
  } catch (e) {
    results.push({ path, name, loadMs: Date.now() - t0, error: 'LOADFAIL: ' + e.message.slice(0, 120), errors: [], warnings: [] })
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }).catch(() => {})
    await page.close()
    continue
  }
  const loadMs = Date.now() - t0
  await page.waitForTimeout(1500)
  const bodyText = (await page.locator('body').innerText().catch(() => '')).slice(0, 400).replace(/\n+/g, ' | ')
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }).catch(() => {})
  results.push({ path, name, loadMs, error: null, errors, warnings, bodyText })
  await page.close()
}

// Check a real project workspace page (first completed project from API)
try {
  const res = await fetch('http://localhost:8000/api/v1/projects?skip=0&limit=1')
  const list = await res.json()
  const pid = Array.isArray(list) ? list[0]?.id : list[0]?.project_id
  if (pid) {
    const page = await ctx.newPage()
    const errors = []
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
    page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message))
    const t0 = Date.now()
    await page.goto(`${BASE}/projects/${pid}/workspace`, { waitUntil: 'networkidle', timeout: 45000 }).catch((e) => errors.push('LOADFAIL: ' + e.message.slice(0, 120)))
    await page.waitForTimeout(2500)
    await page.screenshot({ path: `${OUT}/project_workspace.png`, fullPage: true }).catch(() => {})
    results.push({ path: `/projects/${pid}/workspace`, name: 'project_workspace', loadMs: Date.now() - t0, errors, bodyText: (await page.locator('body').innerText().catch(() => '')).slice(0, 500).replace(/\n+/g, ' | ') })
    await page.close()
  }
} catch (e) {
  results.push({ path: 'n/a', name: 'project_workspace', error: 'FETCHFAIL: ' + e.message, errors: [] })
}

await browser.close()
fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2))
for (const r of results) {
  console.log('='.repeat(80))
  console.log(`${r.name} (${r.path}) load=${r.loadMs}ms ${r.error ? 'ERROR: ' + r.error : ''}`)
  if (r.errors?.length) console.log('  console errors:', r.errors.slice(0, 6).join(' ;; '))
  if (r.bodyText) console.log('  body:', r.bodyText.slice(0, 300))
}
