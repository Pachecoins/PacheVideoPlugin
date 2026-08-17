import { backendBase, jsonHeaders } from "../../backend";

export async function POST(request: Request) {
  const returnUrl = new URL("/app", request.url).toString();
  try {
    const response = await fetch(`${backendBase}/api/billing/subscriptions`, {
      method: "POST",
      headers: {
        ...jsonHeaders(),
        Cookie: request.headers.get("cookie") || "",
        Authorization: request.headers.get("authorization") || "",
      },
      body: JSON.stringify({ returnUrl }),
      signal: AbortSignal.timeout(15000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { detail: "No pudimos iniciar la suscripción" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
