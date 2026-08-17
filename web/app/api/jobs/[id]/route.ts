import { backendBase } from "../../backend";

export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const token = new URL(request.url).searchParams.get("token");
  if (!/^[a-f0-9]{32}$/.test(id) || !token) {
    return Response.json({ detail: "Trabajo inexistente" }, { status: 404 });
  }
  try {
    const response = await fetch(
      `${backendBase}/api/jobs/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`,
      { cache: "no-store", signal: AbortSignal.timeout(8000) },
    );
    const payload = await response.json().catch(() => null) as Record<string, unknown> | null;
    if (!payload) {
      return Response.json({ detail: "Respuesta inválida del servidor" }, { status: 502 });
    }
    if (response.ok && payload.status === "complete" && payload.downloadUrl) {
      payload.downloadUrl = new URL(
        `/api/jobs/${encodeURIComponent(id)}/download?token=${encodeURIComponent(token)}`,
        request.url,
      ).toString();
    }
    return Response.json(payload, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { detail: "Se interrumpió la conexión con el servidor" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
