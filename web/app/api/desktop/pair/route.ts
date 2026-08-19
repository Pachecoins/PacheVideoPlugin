import { backendBase, jsonHeaders, trustedProxyHeaders } from "../../backend";

export async function POST(request: Request) {
  const body = await request.text();
  if (!body || body.length > 1024) {
    return Response.json({ detail: "Código de conexión inválido" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backendBase}/api/desktop/pair`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
        ...trustedProxyHeaders(request),
        Authorization: request.headers.get("authorization") || "",
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "No pudimos vincular la app ahora" }, { status: 503 });
  }
}

export async function GET(request: Request) {
  const code = new URL(request.url).searchParams.get("code") || "";
  if (!code || code.length > 256) {
    return Response.json({ detail: "Código de conexión inválido" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backendBase}/api/desktop/pair?code=${encodeURIComponent(code)}`, {
      headers: trustedProxyHeaders(request),
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "No pudimos comprobar la conexión" }, { status: 503 });
  }
}
