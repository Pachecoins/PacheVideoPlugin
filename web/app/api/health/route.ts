import { backendBase } from "../backend";

export async function GET() {
  try {
    const response = await fetch(`${backendBase}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { ok: false, detail: "El servidor de procesamiento no está disponible" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}

