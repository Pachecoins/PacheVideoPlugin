export const backendBase = (
  process.env.PACHEVIDEO_API_URL || "http://127.0.0.1:8080"
).replace(/\/$/, "");

export function jsonHeaders() {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

export function trustedProxyHeaders(request: Request) {
  const clientIp = request.headers.get("cf-connecting-ip") || "";
  const internalToken = process.env.PACHEVIDEO_INTERNAL_TOKEN || "";
  return {
    // A local preview has no authenticated proxy. Never forward a client IP
    // unless the API can verify the internal proxy token.
    ...(clientIp && internalToken ? { "X-Forwarded-For": clientIp } : {}),
    ...(internalToken ? { "X-PacheVideo-Internal-Token": internalToken } : {}),
  };
}
