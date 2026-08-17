import { backendBase } from "../../../backend";

export async function POST(request: Request) {
  try {
    const response = await fetch(`${backendBase}/api/billing/mercadopago/webhook${new URL(request.url).search}`, {
      method: "POST",
      headers: {
        "Content-Type": request.headers.get("content-type") || "application/json",
        "X-Signature": request.headers.get("x-signature") || "",
        "X-Request-Id": request.headers.get("x-request-id") || "",
      },
      body: await request.text(),
      signal: AbortSignal.timeout(12000),
    });
    return new Response(await response.text(), { status: response.status });
  } catch {
    // Mercado Pago will retry a non-2xx delivery. Returning 503 is intentional.
    return Response.json({ ok: false }, { status: 503 });
  }
}
