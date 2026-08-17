import { backendBase, jsonHeaders } from "../../backend";

export async function POST(request: Request) {
  const rawBody = await request.text();
  if (!rawBody || rawBody.length > 4096) {
    return Response.json({ detail: "Código inválido" }, { status: 400 });
  }
  try {
    const response = await fetch(`${backendBase}/api/gifts/redeem`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
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
      { detail: "No pudimos aplicar el código ahora" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
