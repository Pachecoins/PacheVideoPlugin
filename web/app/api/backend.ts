export const backendBase = (
  process.env.PACHEVIDEO_API_URL || "http://127.0.0.1:8080"
).replace(/\/$/, "");

export function jsonHeaders() {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

