"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authIsConfigured, getSupabaseBrowserClient } from "../lib/supabase-browser";

type Mode = "video" | "audio";
type AuthMode = "signin" | "signup";
type DownloadKind = "single" | "batch";
type Job = {
  id: string;
  token: string;
  mode?: Mode;
  status: "queued" | "downloading" | "processing" | "complete" | "error";
  progress: number;
  message: string;
  detail?: string;
  fileName?: string;
  downloadUrl?: string;
  error?: string;
  attempt?: number;
  maxAttempts?: number;
  plan?: "free" | "pro";
};

type Account = {
  plan: "free" | "pro";
  freeVideoUses: number;
  freeVideoLimit: number;
  freeVideosRemaining: number;
  subscriptionStatus?: string | null;
  authenticated: boolean;
  email?: string | null;
};

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function randomKey(byteLength: number) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function automaticRetrySeconds(failures: number) {
  return Math.min(15, 2 ** Math.min(Math.max(0, failures - 1), 4));
}

function canRecoverAutomatically(error: unknown) {
  if (!(error instanceof ApiError)) return true;
  return error.status === 408 || error.status === 425 || error.status === 429 || error.status >= 500;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function readJson(response: Response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(payload.detail || "No pudimos comunicarnos con el servidor", response.status);
  }
  return payload;
}

export default function DownloaderApp() {
  const [mode, setMode] = useState<Mode>("video");
  const [url, setUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");
  const [downloadKind, setDownloadKind] = useState<DownloadKind>("single");
  const [quality, setQuality] = useState("1080");
  const [audioKbps, setAudioKbps] = useState("320");
  const [account, setAccount] = useState<Account | null>(null);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [batchJobs, setBatchJobs] = useState<Job[]>([]);
  const [formError, setFormError] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [authMessage, setAuthMessage] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [startingDownload, setStartingDownload] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const batchPollTimers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const pollFailures = useRef(0);
  const authConfigured = authIsConfigured();

  const loadAccount = useCallback(async (token = "") => {
    try {
      const response = await fetch("/api/account", {
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const nextAccount = (await readJson(response)) as Account;
      setAccount(nextAccount);
    } catch {
      setFormError("No pudimos inicializar tu cuenta. Recargá la página.");
    }
  }, []);

  useEffect(() => {
    const scheduledBatchPolls = batchPollTimers.current;
    navigator.serviceWorker?.register("/sw.js").catch(() => undefined);
    const auth = getSupabaseBrowserClient();
    let unsubscribeAuth: (() => void) | undefined;
    if (auth) {
      void auth.auth.getSession()
        .then(({ data, error }) => {
          if (error) throw error;
          const token = data.session?.access_token || "";
          setAccessToken(token);
          if (data.session && window.location.hash.includes("access_token")) {
            window.history.replaceState(null, document.title, `${window.location.pathname}${window.location.search}`);
          }
          void loadAccount(token);
        })
        .catch(() => void loadAccount());
      const { data } = auth.auth.onAuthStateChange((_event, session) => {
        const token = session?.access_token || "";
        setAccessToken(token);
        void loadAccount(token);
      });
      unsubscribeAuth = () => data.subscription.unsubscribe();
    } else {
      void loadAccount();
    }
    fetch("/api/health", { cache: "no-store" })
      .then((response) => setServerOnline(response.ok))
      .catch(() => setServerOnline(false));
    return () => {
      unsubscribeAuth?.();
      if (pollTimer.current) clearTimeout(pollTimer.current);
      scheduledBatchPolls.forEach((timer) => clearTimeout(timer));
      scheduledBatchPolls.clear();
    };
  }, [loadAccount]);

  async function poll(jobId: string, token: string) {
    try {
      const response = await fetch(
        `/api/jobs/${encodeURIComponent(jobId)}?token=${encodeURIComponent(token)}`,
        { cache: "no-store" },
      );
      const next = (await readJson(response)) as Job;
      pollFailures.current = 0;
      setJob({ ...next, token });
      if (next.status === "complete" && next.plan === "free" && next.mode === "video") {
        setAccount((current) => current ? {
          ...current,
          freeVideoUses: Math.min(current.freeVideoLimit, current.freeVideoUses + 1),
          freeVideosRemaining: Math.max(0, current.freeVideosRemaining - 1),
        } : current);
      }
      if (next.status !== "complete" && next.status !== "error") {
        pollTimer.current = setTimeout(() => poll(jobId, token), 900);
      }
    } catch (error) {
      if (canRecoverAutomatically(error)) {
        pollFailures.current = Math.min(30, pollFailures.current + 1);
        const retryIn = automaticRetrySeconds(pollFailures.current);
        setJob((current) => current ? {
          ...current,
          message: "Seguimos preparando tu archivo…",
          detail: "No hace falta hacer nada: la conexión se recupera automáticamente.",
        } : current);
        pollTimer.current = setTimeout(() => poll(jobId, token), retryIn * 1000);
        return;
      }
      setJob((current) => current ? {
        ...current,
        status: "error",
        message: "La descarga ya no está disponible",
        detail: error instanceof Error ? error.message : "No pudimos recuperar esta descarga.",
        error: String(error),
      } : current);
    }
  }

  function scheduleBatchPoll(jobId: string, token: string, delay = 900) {
    const timer = window.setTimeout(() => {
      batchPollTimers.current.delete(timer);
      void pollBatch(jobId, token);
    }, delay);
    batchPollTimers.current.add(timer);
  }

  async function pollBatch(jobId: string, token: string) {
    try {
      const response = await fetch(
        `/api/jobs/${encodeURIComponent(jobId)}?token=${encodeURIComponent(token)}`,
        { cache: "no-store" },
      );
      const next = (await readJson(response)) as Job;
      const nextWithToken = { ...next, token };
      setBatchJobs((current) => current.map((item) => item.id === jobId ? nextWithToken : item));
      if (next.status !== "complete" && next.status !== "error") {
        scheduleBatchPoll(jobId, token);
      }
    } catch (error) {
      if (canRecoverAutomatically(error)) {
        setBatchJobs((current) => current.map((item) => item.id === jobId ? {
          ...item,
          message: "Seguimos preparando este archivo…",
          detail: "No hace falta hacer nada: la conexión se recupera automáticamente.",
        } : item));
        scheduleBatchPoll(jobId, token, 2000);
        return;
      }
      setBatchJobs((current) => current.map((item) => item.id === jobId ? {
        ...item,
        status: "error",
        message: "La descarga ya no está disponible",
        detail: error instanceof Error ? error.message : "No pudimos recuperar esta descarga.",
        error: String(error),
      } : item));
    }
  }

  async function startDownload() {
    setFormError("");
    if (!account) {
      setFormError("Tu cuenta se está preparando automáticamente.");
      return;
    }
    if (mode === "video" && account.plan !== "pro" && account.freeVideosRemaining <= 0) {
      setFormError(account.authenticated
        ? `Ya usaste tus ${account.freeVideoLimit} videos gratis. Activá Video Pro para continuar.`
        : "Ya usaste tu video de prueba. Registrate gratis y obtené 5 videos en 1080p.");
      return;
    }
    setJob(null);
    setBatchJobs([]);
    pollFailures.current = 0;
    setStartingDownload(true);
    const requestId = randomKey(16);
    const requestToken = randomKey(32);
    let startFailures = 0;
    try {
      while (true) {
        try {
          const response = await fetch("/api/jobs", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
            },
            body: JSON.stringify({
              url,
              mode,
              quality: mode === "video" ? quality : "max",
              audioKbps,
              requestId,
              requestToken,
            }),
          });
          const created = (await readJson(response)) as Job;
          setJob(created);
          void poll(created.id, created.token);
          return;
        } catch (error) {
          if (!canRecoverAutomatically(error)) throw error;
          startFailures = Math.min(30, startFailures + 1);
          setJob({
            id: "pending",
            token: "",
            mode,
            status: "queued",
            progress: 1,
            message: "Preparando tu descarga…",
            detail: "No hace falta volver a tocar el botón.",
            plan: account.plan,
          });
          await wait(automaticRetrySeconds(startFailures) * 1000);
        }
      }
    } catch (error) {
      setJob(null);
      setFormError(error instanceof Error ? error.message : "No pudimos crear la descarga");
    } finally {
      setStartingDownload(false);
    }
  }

  async function startBatchDownload() {
    setFormError("");
    if (!account) {
      setFormError("Tu cuenta se está preparando automáticamente.");
      return;
    }
    if (account.plan !== "pro") {
      setFormError("Las listas de enlaces están incluidas en Video Pro.");
      return;
    }
    const urls = Array.from(new Set(batchUrls.split(/\s+/).map((item) => item.trim()).filter(Boolean)));
    if (!urls.length) {
      setFormError("Pegá al menos un enlace para preparar tu lista.");
      return;
    }
    if (urls.length > 20) {
      setFormError("Video Pro permite hasta 20 enlaces por lista.");
      return;
    }
    setJob(null);
    setBatchJobs([]);
    setStartingDownload(true);
    const requestId = randomKey(16);
    const requestToken = randomKey(32);
    let startFailures = 0;
    try {
      while (true) {
        try {
          const response = await fetch("/api/jobs/batch", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
            },
            body: JSON.stringify({
              urls,
              mode,
              quality: mode === "video" ? quality : "max",
              audioKbps,
              requestId,
              requestToken,
            }),
          });
          const created = (await readJson(response)) as { jobs?: Job[] };
          if (!created.jobs?.length) throw new Error("No pudimos crear la lista");
          setBatchJobs(created.jobs);
          created.jobs.forEach((createdJob) => void pollBatch(createdJob.id, createdJob.token));
          return;
        } catch (error) {
          if (!canRecoverAutomatically(error)) throw error;
          startFailures = Math.min(30, startFailures + 1);
          await wait(automaticRetrySeconds(startFailures) * 1000);
        }
      }
    } catch (error) {
      setBatchJobs([]);
      setFormError(error instanceof Error ? error.message : "No pudimos crear la lista");
    } finally {
      setStartingDownload(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await (downloadKind === "batch" ? startBatchDownload() : startDownload());
  }

  async function startSubscription() {
    setFormError("");
    if (!account) {
      setFormError("Tu cuenta se está preparando automáticamente.");
      return;
    }
    if (account.plan === "pro") return;
    if (!account.authenticated || !accessToken) {
      setFormError("Ingresá con tu email antes de activar Video Pro.");
      document.querySelector("#cuenta")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    try {
      const response = await fetch("/api/billing/subscription", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: "{}",
      });
      const payload = await readJson(response) as { checkoutUrl?: string };
      if (!payload.checkoutUrl) throw new Error("No pudimos abrir el pago");
      window.location.assign(payload.checkoutUrl);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "No pudimos iniciar la suscripción");
    }
  }

  async function requestAccessLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const auth = getSupabaseBrowserClient();
    if (!auth) {
      setAuthMessage("El registro está listo; falta conectar el servicio de email.");
      return;
    }
    setAuthBusy(true);
    setAuthMessage("");
    const { error } = await auth.auth.signInWithOtp({
      email: loginEmail.trim(),
      options: {
        shouldCreateUser: authMode === "signup",
        emailRedirectTo: `${window.location.origin}/app`,
      },
    });
    setAuthBusy(false);
    setAuthMessage(error
      ? authMode === "signin"
        ? "No encontramos esa cuenta o no pudimos enviar el enlace. Revisá el email."
        : "No pudimos crear la cuenta. Revisá el email."
      : authMode === "signin"
        ? "Te enviamos un enlace para volver a entrar. Revisá tu correo."
        : "Te enviamos un enlace para confirmar tu cuenta. Revisá tu correo.");
  }

  async function signOut() {
    const auth = getSupabaseBrowserClient();
    if (!auth) return;
    await auth.auth.signOut();
    setAccessToken("");
    setAuthMessage("Sesión cerrada.");
    await loadAccount();
  }

  async function pasteUrl() {
    try {
      const pasted = (await navigator.clipboard.readText()).trim();
      if (downloadKind === "batch") {
        setBatchUrls((current) => current ? `${current.trim()}\n${pasted}` : pasted);
      } else {
        setUrl(pasted);
      }
    } catch {
      setFormError("El navegador no permitió leer el portapapeles. Pegá el enlace manualmente.");
    }
  }

  function focusRegistration() {
    document.querySelector("#cuenta")?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => document.querySelector<HTMLInputElement>("#account-email")?.focus(), 250);
  }

  const batchBusy = batchJobs.some((item) => !["complete", "error"].includes(item.status));
  const busy = startingDownload || (!!job && !["complete", "error"].includes(job.status)) || batchBusy;
  const proCandidate = account?.plan === "pro";
  const videoQuotaExhausted = mode === "video" && !!account && !proCandidate && account.freeVideosRemaining <= 0;
  const freeQuotaCopy = account?.authenticated
    ? `Te quedan ${account.freeVideosRemaining} de ${account.freeVideoLimit} videos gratis hasta 1080p`
    : "1 video de prueba + 5 videos gratis al registrarte";

  return (
    <main className="site-shell">
      <nav className="topbar" aria-label="Navegación principal">
        <Link className="brand" href="/" prefetch={false} aria-label="PacheVideo, volver al inicio">
          <span className="brand-mark">P</span>
          <span>PACHEVIDEO</span>
        </Link>
        <div className="app-topbar-actions">
          <Link className="back-home-link" href="/" prefetch={false}>Inicio</Link>
          <span className={`server-pill ${serverOnline === false ? "offline" : ""}`}>
            <i /> {serverOnline === null ? "Conectando…" : serverOnline ? "Servidor disponible" : "Servidor sin conexión"}
          </span>
        </div>
      </nav>

      <section className="app-hero" id="inicio">
        <div className="eyebrow">TU VIDEO, LISTO EN SEGUNDOS</div>
        <h1>Descargá. Convertí.<br /><span>Seguí creando.</span></h1>
        <p className="lede">
          Pegá el enlace, elegí el formato y nosotros hacemos el resto.
          Sin instalar nada y desde cualquier dispositivo.
        </p>

        <section className={`account-panel ${account?.authenticated ? "signed-in" : ""}`} id="cuenta" aria-labelledby="account-title">
          <div>
            <span className="account-kicker">TU CUENTA</span>
            <h2 id="account-title">{account === null
              ? "Recuperando tu sesión…"
              : account.authenticated
                ? `Hola, ${account.email}`
                : authMode === "signin"
                  ? "Volvé a entrar a tu cuenta"
                  : "Registrate gratis y descargá 5 videos"}</h2>
            <p>{account === null
              ? "Estamos comprobando si ya habías iniciado sesión en este dispositivo."
              : account.authenticated
                ? account.plan === "pro"
                  ? "Video Pro está vinculado a tu email y funciona en todos tus dispositivos."
                  : `${account.freeVideosRemaining} de ${account.freeVideoLimit} videos gratis disponibles hasta 1080p.`
                : authMode === "signin"
                  ? "Usá el mismo email de tu cuenta para conservar tu plan y tus descargas disponibles."
                  : "Hasta 1080p, sin tarjeta. Tu cuenta nueva recibe 5 videos gratis."}</p>
          </div>
          {account === null ? (
            <div className="session-loading" role="status" aria-live="polite">
              <i aria-hidden="true" /> Comprobando cuenta
            </div>
          ) : account.authenticated ? (
            <button className="account-secondary" type="button" onClick={() => void signOut()}>Cerrar sesión</button>
          ) : (
            <form className="account-form" onSubmit={requestAccessLink}>
              <div className="account-auth-tabs" aria-label="Acceso a la cuenta">
                <button
                  className={authMode === "signin" ? "active" : ""}
                  type="button"
                  aria-pressed={authMode === "signin"}
                  onClick={() => { setAuthMode("signin"); setAuthMessage(""); }}
                >Iniciar sesión</button>
                <button
                  className={authMode === "signup" ? "active" : ""}
                  type="button"
                  aria-pressed={authMode === "signup"}
                  onClick={() => { setAuthMode("signup"); setAuthMessage(""); }}
                >Crear cuenta</button>
              </div>
              <label className="account-email-label" htmlFor="account-email">Email</label>
              <div className="account-form-row">
                <input
                  id="account-email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="tu@email.com"
                  value={loginEmail}
                  onChange={(event) => setLoginEmail(event.target.value)}
                  required
                />
                <button type="submit" disabled={authBusy || !authConfigured}>
                  {authBusy ? "Enviando…" : authMode === "signin" ? "Enviar enlace de acceso" : "Crear cuenta gratis"}
                </button>
              </div>
            </form>
          )}
          {!authConfigured && <small>Registro preparado · falta conectar el servicio de email.</small>}
          {authMessage && <small role="status">{authMessage}</small>}
        </section>

        <div className={`trial-strip ${proCandidate ? "pro-mode-strip" : ""}`} aria-label="Beneficios del plan">
          <div>
            <span>{proCandidate ? "VIDEO PRO ACTIVO" : "PLAN GRATIS"}</span>
            <strong>{proCandidate ? "2K, 4K y máxima calidad habilitadas" : freeQuotaCopy}</strong>
          </div>
          <a href={account?.authenticated ? "#planes" : "#cuenta"}>{proCandidate ? "Ver tu plan" : account?.authenticated ? "Ver planes" : "Registrarme"}</a>
        </div>

        {proCandidate && <p className="pro-preview-note" role="status">Video Pro activo · sin anuncios · procesamiento prioritario</p>}

        <form className="download-card" onSubmit={submit}>
          <div className="mode-switch" role="group" aria-label="Formato de descarga">
            <button className={mode === "video" ? "active" : ""} type="button" onClick={() => setMode("video")} disabled={busy}>Video</button>
            <button className={mode === "audio" ? "active" : ""} type="button" onClick={() => setMode("audio")} disabled={busy}>Audio</button>
          </div>

          {proCandidate && (
            <div className="download-kind-switch" role="group" aria-label="Tipo de descarga">
              <button className={downloadKind === "single" ? "active" : ""} type="button" onClick={() => setDownloadKind("single")} disabled={busy}>Un enlace</button>
              <button className={downloadKind === "batch" ? "active" : ""} type="button" onClick={() => setDownloadKind("batch")} disabled={busy}>Lista Pro</button>
            </div>
          )}

          {downloadKind === "batch" && proCandidate ? (
            <div className="batch-input-wrap">
              <label htmlFor="batch-urls">Lista de enlaces</label>
              <div className="batch-url-row">
                <textarea
                  id="batch-urls"
                  inputMode="url"
                  autoComplete="off"
                  placeholder={"https://youtube.com/...\nhttps://instagram.com/...\nhttps://facebook.com/..."}
                  value={batchUrls}
                  onChange={(event) => setBatchUrls(event.target.value)}
                  disabled={busy}
                  required
                />
                <button className="paste-button" type="button" onClick={pasteUrl} disabled={busy}>Pegar</button>
              </div>
              <p>Hasta 20 enlaces, uno por línea. Podés mezclar YouTube, Instagram, Facebook y otras fuentes compatibles.</p>
            </div>
          ) : (
            <>
              <label htmlFor="source-url">Enlace del contenido</label>
              <div className="url-row">
                <input
                  id="source-url"
                  type="url"
                  inputMode="url"
                  autoComplete="url"
                  placeholder="https://ejemplo.com/video"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  disabled={busy}
                  required
                />
                <button className="paste-button" type="button" onClick={pasteUrl} disabled={busy}>Pegar</button>
              </div>
            </>
          )}

          <div className="options-grid">
            {mode === "video" ? (
              <label>
                <span>Calidad</span>
                <select value={quality} onChange={(event) => setQuality(event.target.value)} disabled={busy}>
                  <option value="1080">Full HD · 1080p</option>
                  <option value="720">HD · 720p</option>
                  <option value="480">480p</option>
              <option value="1440" disabled={!proCandidate}>2K · 1440p{!proCandidate ? " · Video Pro" : ""}</option>
              <option value="2160" disabled={!proCandidate}>4K · 2160p{!proCandidate ? " · Video Pro" : ""}</option>
              <option value="max" disabled={!proCandidate}>Máxima disponible{!proCandidate ? " · Video Pro" : ""}</option>
                </select>
              </label>
            ) : (
              <label>
                <span>Calidad de audio</span>
                <select value={audioKbps} onChange={(event) => setAudioKbps(event.target.value)} disabled={busy}>
                  <option value="320">320 kbps</option>
                  <option value="256">256 kbps</option>
                  <option value="192">192 kbps</option>
                  <option value="128">128 kbps</option>
                </select>
              </label>
            )}
            <label>
              <span>Formato</span>
              <select value={mode === "video" ? "mp4" : "mp3"} disabled aria-label="Formato final">
                {mode === "video" ? <option value="mp4">MP4</option> : <option value="mp3">MP3</option>}
              </select>
            </label>
          </div>

          <div className="pro-unlock">
            <div>
              <strong>{proCandidate ? "Video Pro activo" : "Video Pro"}</strong>
              <span>{proCandidate ? "Máxima velocidad, calidad y listas de hasta 20 enlaces habilitadas." : "2K, 4K, máxima calidad, listas de enlaces y procesamiento prioritario."}</span>
            </div>
            {!proCandidate && <button className="pro-preview-link" type="button" onClick={() => void startSubscription()}>Suscribirme</button>}
          </div>

          <button
            className="primary-action"
            type={videoQuotaExhausted ? "button" : "submit"}
            disabled={!account || busy || serverOnline === false}
            onClick={videoQuotaExhausted ? () => account?.authenticated ? void startSubscription() : focusRegistration() : undefined}
          >
            {!account
              ? "Preparando tu cuenta…"
              : busy
              ? "Preparando…"
              : videoQuotaExhausted
                ? account?.authenticated ? "Activar Video Pro para continuar" : "Registrarme y obtener 5 videos"
                : downloadKind === "batch" ? "Preparar lista" : "Preparar descarga"} <span>→</span>
          </button>
          {!proCandidate && (
            <p className="speed-upgrade-note">* Para descargas más rápidas, actualizate a Video Pro.</p>
          )}
          {formError && <p className="form-error" role="alert">{formError}</p>}
        </form>

        {job && (
          <section className={`job-card ${job.status}`} aria-live="polite">
            <div className="job-heading">
              <div>
                <span className="job-kicker">{job.status === "complete" ? "ARCHIVO DISPONIBLE" : job.status === "error" ? "CONTENIDO NO DISPONIBLE" : "PROCESANDO EN EL SERVIDOR"}</span>
                <strong>{job.message}</strong>
              </div>
              <span className="job-percent">
                {`${Math.round(job.progress || 0)}%`}
              </span>
            </div>
            <div className="progress-track"><i style={{ width: `${Math.max(2, job.progress || 0)}%` }} /></div>
            {job.detail && <p>{job.detail}</p>}
            {job.status === "complete" && job.downloadUrl && (
              <a
                className="download-link"
                href={job.downloadUrl}
                download={job.fileName || "pachevideo-archivo"}
                target="_self"
                rel="noopener"
                onClick={(event) => {
                  // Android's PWA shell can ignore the HTML download attribute.
                  // Desktop browsers keep the native download behavior instead.
                  if (/Android/i.test(navigator.userAgent)) {
                    event.preventDefault();
                    window.location.assign(job.downloadUrl!);
                  }
                }}
              >
                Descargar archivo
              </a>
            )}
          </section>
        )}

        {batchJobs.length > 0 && (
          <section className="batch-jobs" aria-live="polite" aria-label="Estado de tu lista de descargas">
            <div className="batch-jobs-heading">
              <div>
                <span>LISTA VIDEO PRO</span>
                <strong>{batchJobs.filter((item) => item.status === "complete").length} de {batchJobs.length} archivos listos</strong>
              </div>
              <small>Podés descargar cada archivo cuando esté disponible.</small>
            </div>
            {batchJobs.map((item, index) => (
              <article className={`batch-job ${item.status}`} key={item.id}>
                <div className="batch-job-heading">
                  <span>{index + 1}</span>
                  <div>
                    <strong>{item.detail || item.message}</strong>
                    <small>{item.status === "complete" ? "Archivo disponible" : item.status === "error" ? "No disponible" : item.message}</small>
                  </div>
                  <b>{Math.round(item.progress || 0)}%</b>
                </div>
                <div className="progress-track"><i style={{ width: `${Math.max(2, item.progress || 0)}%` }} /></div>
                {item.status === "complete" && item.downloadUrl && (
                  <a
                    className="download-link"
                    href={item.downloadUrl}
                    download={item.fileName || `pachevideo-archivo-${index + 1}`}
                    target="_self"
                    rel="noopener"
                    onClick={(event) => {
                      if (/Android/i.test(navigator.userAgent)) {
                        event.preventDefault();
                        window.location.assign(item.downloadUrl!);
                      }
                    }}
                  >
                    Descargar archivo {index + 1}
                  </a>
                )}
                {item.status === "error" && item.detail && <p>{item.detail}</p>}
              </article>
            ))}
          </section>
        )}

        <div className="trust-row" aria-label="Beneficios">
          <span>✓ Sin instalaciones</span>
          <span>✓ Funciona en celular</span>
          <span>✓ Procesamiento seguro</span>
        </div>

        {!proCandidate && (
          <aside className="ad-slot" aria-label="Publicidad">
            <span className="ad-label">PUBLICIDAD</span>
            <div>
              <strong>Espacio publicitario</strong>
              <p>Los anuncios aparecen únicamente en el plan Gratis.</p>
            </div>
          </aside>
        )}

        <section className="plans-section" id="planes" aria-labelledby="plans-title">
          <div className="section-heading">
            <span>PLANES SIMPLES</span>
            <h2 id="plans-title">Elegí cómo querés descargar</h2>
            <p>Creá tu cuenta gratis y recibí 5 videos hasta 1080p. Pasate a Video Pro para 2K, 4K y máxima calidad.</p>
          </div>

          <div className="plans-grid">
            <article className="plan-card">
              <span className="plan-name">GRATIS</span>
              <div className="plan-price"><strong>$0</strong><span>para siempre</span></div>
              <ul>
                <li><i aria-hidden="true">✓</i> Audio sin consumir créditos</li>
                <li><i aria-hidden="true">✓</i> 5 videos gratis hasta 1080p al registrarte</li>
                <li><i aria-hidden="true">✓</i> Acceso desde celular y computadora</li>
                <li className="muted-feature"><i aria-hidden="true">·</i> Incluye anuncios</li>
              </ul>
              {account?.authenticated
                ? <span className="plan-status">{proCandidate ? "Incluido antes de pasar a Pro" : `${account.freeVideosRemaining} de ${account.freeVideoLimit} disponibles`}</span>
                : <a className="plan-status" href="#cuenta">Crear cuenta gratis</a>}
            </article>

            <article className="plan-card featured">
              <span className="popular-pill">MÁS ELEGIDO</span>
              <span className="plan-name">PACHEVIDEO PRO</span>
              <div className="plan-price"><strong>$9.999,99</strong><span>ARS / mes</span></div>
              <ul>
                <li><i aria-hidden="true">✓</i> Audio gratis</li>
                <li><i aria-hidden="true">✓</i> Video en 2K, 4K o máxima calidad</li>
                <li><i aria-hidden="true">✓</i> Listas de hasta 20 enlaces</li>
                <li><i aria-hidden="true">✓</i> Descargas sin cupo con uso razonable</li>
                <li><i aria-hidden="true">✓</i> Procesamiento prioritario</li>
                <li><i aria-hidden="true">✓</i> Sin anuncios</li>
              </ul>
              {proCandidate
                ? <span className="plan-status pro-status">Video Pro activo</span>
                : <button className="plan-status pro-status" type="button" onClick={() => void startSubscription()}>Suscribirme por $9.999,99</button>}
            </article>
          </div>
        </section>
      </section>
    </main>
  );
}
