import { backendBase } from "../backend";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${backendBase}/api/history`, {
      headers: {
        Cookie: request.headers.get("cookie") || "",
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
    return Response.json(
      { detail: "No pudimos cargar tu historial" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
