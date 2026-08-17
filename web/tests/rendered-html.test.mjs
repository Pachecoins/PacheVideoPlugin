import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("redirects the public root directly to the downloader", async () => {
  const response = await render();
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "/app");
});

test("server-renders the downloader at /app", async () => {
  const response = await render("/app");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>PacheVideo App/);
  assert.match(html, /logo\.png/);
  assert.match(html, /Descargá\. Convertí\./);
  assert.match(html, /Preparar descarga/);
  assert.match(html, />Inicio<\/a>/);
  assert.match(html, /Recuperando tu sesión/);
  assert.match(html, /Comprobando cuenta/);
  assert.match(html, /5 videos gratis al registrarte/);
  assert.match(html, /Audio sin consumir créditos/);
  assert.match(html, /Para descargas más rápidas, actualizate a Video Pro/);
  assert.match(html, /2K, 4K, máxima calidad, listas de enlaces y procesamiento prioritario/);
  assert.match(html, /Suscribirme por \$9\.999,99/);
  assert.doesNotMatch(html, /\$10\.000/);
  assert.doesNotMatch(html, /Confirmo que el contenido es mío|type="checkbox"/i);
});

test("legacy Pro page no longer exposes a demo entitlement", async () => {
  const response = await render("/pro");
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "/app#planes");
});

test("downloader recovers automatically without a manual retry control", async () => {
  const source = await readFile(new URL("../app/components/downloader-app.tsx", import.meta.url), "utf8");
  const authSource = await readFile(new URL("../app/lib/supabase-browser.ts", import.meta.url), "utf8");
  assert.match(source, /canRecoverAutomatically/);
  assert.match(source, /pollFailures\.current = Math\.min\(30/);
  assert.match(source, /la conexión se recupera automáticamente/i);
  assert.match(source, /requestId/);
  assert.match(source, /requestToken/);
  assert.match(source, /disabled=!\{?proCandidate\}?|disabled=\{!proCandidate\}/);
  assert.match(source, /\/api\/account/);
  assert.match(source, /\/api\/jobs\/batch/);
  assert.match(source, /Lista Pro/);
  assert.match(source, /Hasta 20 enlaces/);
  assert.match(source, /account\.plan !== "pro"/);
  assert.match(source, /\/api\/billing\/subscription/);
  assert.match(await readFile(new URL("../app/api/billing/subscription/route.ts", import.meta.url), "utf8"), /new URL\("\/app", request\.url\)/);
  assert.match(source, /account\.plan === "pro"/);
  assert.match(source, /signInWithOtp/);
  assert.match(source, /type AuthMode = "signin" \| "signup"/);
  assert.match(source, /shouldCreateUser: authMode === "signup"/);
  assert.match(source, /Iniciar sesión/);
  assert.match(source, /Enviar enlace de acceso/);
  assert.match(source, /Recuperando tu sesión/);
  assert.match(authSource, /flowType: "implicit"/);
  assert.match(authSource, /persistSession: true/);
  assert.match(authSource, /autoRefreshToken: true/);
  assert.match(authSource, /detectSessionInUrl: true/);
  assert.match(source, /Authorization: `Bearer \$\{accessToken\}`/);
  assert.match(source, /freeVideosRemaining/);
  assert.match(source, /Registrarme y obtener 5 videos/);
  assert.match(source, /Ya usaste tus.*videos gratis/);
  assert.match(source, /window\.location\.assign\(job\.downloadUrl!/);
  assert.match(source, /Descargar archivo/);
  assert.doesNotMatch(source, /Código de acceso Video Pro|Ingresá tu código|Reintentando descarga|Reintentar ahora|Nuevo intento/);
  assert.doesNotMatch(source, /proAccessKey|PACHE-PRO-DEMO|window\.prompt/);
});

test("job status keeps downloads on the same public web origin", async () => {
  const statusRoute = await readFile(new URL("../app/api/jobs/[id]/route.ts", import.meta.url), "utf8");
  const downloadRoute = await readFile(new URL("../app/api/jobs/[id]/download/route.ts", import.meta.url), "utf8");
  assert.match(statusRoute, /\/api\/jobs\/\$\{encodeURIComponent\(id\)\}\/download\?token=/);
  assert.doesNotMatch(statusRoute, /directDownloadUrl/);
  assert.match(downloadRoute, /Content-Disposition/);
  assert.match(downloadRoute, /Accept-Ranges/);
  assert.match(downloadRoute, /Content-Range/);
  assert.match(downloadRoute, /request\.headers\.get\("Range"\)/);
  assert.doesNotMatch(downloadRoute, /AbortSignal\.timeout/);
  const downloaderSource = await readFile(new URL("../app/components/downloader-app.tsx", import.meta.url), "utf8");
  assert.match(downloaderSource, /download=\{job\.fileName/);
  assert.match(downloaderSource, /Android\/i\.test\(navigator\.userAgent\)/);
});
