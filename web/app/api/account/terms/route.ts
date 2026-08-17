import { backendBase, jsonHeaders, trustedProxyHeaders } from "../../backend";

export async function POST(request: Request) {
  try {
    const response = await fetch(`${backendBase}/api/account/terms`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
        ...trustedProxyHeaders(request),
        Authorization: request.headers.get("authorization") || "",
      },
      body: "{}",
      signal: AbortSignal.timeout(8000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "No pudimos registrar la aceptación" }, { status: 503 });
  }
}
