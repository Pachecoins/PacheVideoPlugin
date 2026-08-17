import { backendBase } from "../../../backend";

export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const token = new URL(request.url).searchParams.get("token");
  if (!/^[a-f0-9]{32}$/.test(id) || !token) {
    return Response.json({ detail: "Archivo inexistente" }, { status: 404 });
  }

  try {
    const upstreamHeaders = new Headers();
    const range = request.headers.get("Range");
    if (range) upstreamHeaders.set("Range", range);

    const response = await fetch(
      `${backendBase}/api/jobs/${encodeURIComponent(id)}/download?token=${encodeURIComponent(token)}`,
      {
        // A download can legitimately take more than 30 seconds on mobile data.
        // Do not abort a response that is already streaming to the device.
        headers: upstreamHeaders,
      },
    );
    const headers = new Headers();
    for (const name of [
      "Accept-Ranges",
      "Content-Disposition",
      "Content-Length",
      "Content-Range",
      "Content-Type",
    ]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("Cache-Control", "no-store");
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return Response.json(
      { detail: "No pudimos recuperar el archivo" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
