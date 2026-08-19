import { backendBase, trustedProxyHeaders } from "../../backend";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${backendBase}/api/desktop/account`, {
      headers: {
        ...trustedProxyHeaders(request),
        Authorization: request.headers.get("authorization") || "",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "No pudimos verificar tu cuenta" }, { status: 503 });
  }
}
