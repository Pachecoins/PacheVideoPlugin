import { backendBase, jsonHeaders, trustedProxyHeaders } from "../../backend";

export async function POST(request: Request) {
  const rawBody = await request.text();
  if (!rawBody || rawBody.length > 8192) {
    return Response.json({ detail: "Solicitud de vista previa inválida" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backendBase}/api/discovery/preview`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
        ...trustedProxyHeaders(request),
        Cookie: request.headers.get("cookie") || "",
        Authorization: request.headers.get("authorization") || "",
      },
      body: rawBody,
      signal: AbortSignal.timeout(25_000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { detail: "La vista previa no está disponible" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
