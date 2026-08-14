/**
 * 免费 Basic Auth —— 替代 Netlify Visitor Access（付费功能）
 *
 * 设置方式：Netlify UI → Site configuration → Environment variables
 *   AUTH_USERNAME = 你的用户名
 *   AUTH_PASSWORD = 你的密码
 *
 * 修改密码：直接更新环境变量 → Trigger deploy 即可
 */

export default async function handler(request: Request, context: any) {
  const username = Deno.env.get("AUTH_USERNAME")
  const password = Deno.env.get("AUTH_PASSWORD")

  // 如果没设环境变量，跳过认证（不影响开发/未配置状态）
  if (!username || !password) {
    return context.next()
  }

  const auth = request.headers.get("authorization")

  if (auth) {
    // 解析 Basic Auth header
    const [scheme, encoded] = auth.split(" ")
    if (scheme === "Basic") {
      const decoded = atob(encoded)
      const [user, pass] = decoded.split(":")
      if (user === username && pass === password) {
        return context.next()
      }
    }
  }

  // 认证失败 → 弹出浏览器原生登录框
  return new Response("Unauthorized", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="PRD Agent", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
    },
  })
}

export const config = { path: "/*" }
