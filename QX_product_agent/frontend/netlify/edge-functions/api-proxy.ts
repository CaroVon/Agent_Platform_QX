/**
 * Netlify Edge Function —— API 代理
 */
export default async function handler(request: Request) {
  try {
    const backend = Deno.env.get("BACKEND_URL")

    // Step 1: Return diagnostic info
    if (!backend) {
      return new Response(
        JSON.stringify({ detail: "BACKEND_URL not set" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      )
    }

    const url = new URL(request.url)
    const target = new URL(backend)
    url.host = target.host
    url.protocol = target.protocol
    if (target.port) url.port = target.port

    // Strip problematic headers, set correct Host
    const headers = new Headers()
    for (const [key, value] of request.headers.entries()) {
      if (key.toLowerCase() === "host") continue
      if (key.toLowerCase() === "transfer-encoding") continue
      headers.set(key, value)
    }
    headers.set("Host", target.host)

    // GET/HEAD: no body
    const method = request.method.toUpperCase()
    const hasBody = method !== "GET" && method !== "HEAD"
    const proxyRequest = new Request(url, {
      method,
      headers,
      body: hasBody ? request.body : undefined,
    })

    const response = await fetch(proxyRequest)
    return response
  } catch (error) {
    return new Response(
      JSON.stringify({
        detail: `edgefn-error: ${error instanceof Error ? error.message : String(error)}`,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )
  }
}
