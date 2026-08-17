import { backendBase, trustedProxyHeaders } from "../backend";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${backendBase}/api/account`, {
      headers: {
        ...trustedProxyHeaders(request),
        Cookie: request.headers.get("cookie") || "",
        Authorization: request.headers.get("authorization") || "",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const headers = new Headers({
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    const setCookie = response.headers.get("set-cookie");
    if (setCookie) headers.set("set-cookie", setCookie);
    return new Response(await response.text(), { status: response.status, headers });
  } catch {
    return Response.json(
      { detail: "No pudimos inicializar tu cuenta" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
