#!/usr/bin/env node
/**
 * ============================================================
 * UI 冒烟测试（productize 前端产品化验证）
 * ============================================================
 * 验证 8 个模块路由渲染 + 侧边栏折叠交互 + 无控制台错误。
 *
 * 用法:
 *   node scripts/ui-smoke.mjs [--base-url http://localhost:5173]
 *
 * stdout 输出 JSON 报告: {"routes": [...], "sidebar_collapse": true, "console_errors": N}
 */

import { chromium } from 'playwright'
import fs from 'node:fs'

const getArg = (name, fallback) => {
  const idx = process.argv.indexOf(name)
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : fallback
}
const baseUrl = getArg('--base-url', 'http://localhost:5173')
const LOCAL_LIBS = `${process.env.HOME}/.local/playwright-libs/usr/lib/x86_64-linux-gnu`

const ROUTES = [
  { path: '/workspace', expect: 'Describe the product you want' },
  { path: '/research', expect: 'Research Hub' },
  { path: '/prd', expect: 'PRD Studio' },
  { path: '/design', expect: 'Design Studio' },
  { path: '/presentation', expect: 'Presentation' },
  { path: '/knowledge', expect: 'Knowledge Base' },
  { path: '/templates', expect: 'Templates' },
  { path: '/settings', expect: 'Settings' },
]

async function main() {
  const env = fs.existsSync(LOCAL_LIBS)
    ? { ...process.env, LD_LIBRARY_PATH: `${LOCAL_LIBS}:${process.env.LD_LIBRARY_PATH ?? ''}` }
    : process.env
  const browser = await chromium.launch({ env })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => consoleErrors.push(String(err)))

  const results = []

  // ─── 路由渲染检查 ────────────────────────────────────────
  for (const route of ROUTES) {
    try {
      await page.goto(`${baseUrl}${route.path}`, { waitUntil: 'networkidle', timeout: 30000 })
      await page.waitForTimeout(600)
      const h1 = await page.locator('h1').first().textContent().catch(() => '')
      const ok = (h1 ?? '').includes(route.expect)
      results.push({ path: route.path, h1: (h1 ?? '').slice(0, 30), ok })
    } catch (err) {
      results.push({ path: route.path, h1: '', ok: false, error: String(err).slice(0, 120) })
    }
  }

  // ─── 侧边栏折叠交互 ──────────────────────────────────────
  let sidebarCollapse = false
  try {
    await page.goto(`${baseUrl}/workspace`, { waitUntil: 'networkidle' })
    const aside = page.locator('aside')
    const widthBefore = (await aside.boundingBox())?.width ?? 0
    const toggle = page.locator('aside button[title="折叠侧边栏"]')
    if ((await toggle.count()) > 0) {
      await toggle.click()
      await page.waitForTimeout(400)
      const widthAfter = (await aside.boundingBox())?.width ?? 0
      sidebarCollapse = widthAfter < widthBefore
      // 还原：折叠后按钮 title 变为「展开侧边栏」
      const restore = page.locator('aside button[title="展开侧边栏"]')
      if ((await restore.count()) > 0) await restore.click()
    }
  } catch (err) {
    consoleErrors.push(`sidebar test: ${err}`)
  }

  await browser.close()
  console.log(
    JSON.stringify({
      routes: results,
      sidebar_collapse: sidebarCollapse,
      console_errors: consoleErrors.length,
      errors: consoleErrors.slice(0, 5),
    }),
  )
  const failed = results.filter((r) => !r.ok)
  process.exit(failed.length > 0 || consoleErrors.length > 0 || !sidebarCollapse ? 1 : 0)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
