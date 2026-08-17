import { backendBase, jsonHeaders, trustedProxyHeaders } from "../backend";

export async function POST(request: Request) {
  const rawBody = await request.text();
  if (!rawBody || rawBody.length > 32768) {
    return Response.json({ detail: "Solicitud inválida" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backendBase}/api/jobs`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
        ...trustedProxyHeaders(request),
        Cookie: request.headers.get("cookie") || "",
        Authorization: request.headers.get("authorization") || "",
      },
      body: rawBody,
      signal: AbortSignal.timeout(15000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { detail: "El servidor de procesamiento no está disponible" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
