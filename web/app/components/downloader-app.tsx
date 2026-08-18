"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authIsConfigured, getSupabaseBrowserClient } from "../lib/supabase-browser";

type Mode = "video" | "audio";
type DownloadKind = "single" | "batch";
const PENDING_GIFT_CODE_KEY = "pachevideo_pending_gift_code";
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
  proBadge?: "bro" | "mage" | null;
  authenticated: boolean;
  email?: string | null;
  termsAccepted: boolean;
};

type HistoryItem = {
  id: string;
  network: "youtube" | "instagram" | "tiktok" | "facebook" | "web";
  mode: Mode;
  quality: string;
  status: Job["status"];
  title: string;
  thumbnailUrl?: string | null;
  available: boolean;
  createdAt: number;
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

function NetworkIcon({ network }: { network: HistoryItem["network"] }) {
  if (network === "instagram") return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.3" cy="6.8" r="1" /></svg>;
  if (network === "tiktok") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3v11.1a4.1 4.1 0 1 1-3.2-4V7.4A7.1 7.1 0 1 0 17 14V8.2c1.1 1 2.5 1.6 4 1.6V6.6A4.2 4.2 0 0 1 17 3h-3Z" /></svg>;
  if (network === "facebook") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.7 21v-8h2.7l.4-3h-3.1V8.1c0-.9.3-1.5 1.6-1.5H17V3.9c-.3 0-1.2-.1-2.3-.1-2.3 0-3.9 1.4-3.9 4V10H8v3h2.8v8h2.9Z" /></svg>;
  if (network === "youtube") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 7.2a2.8 2.8 0 0 0-2-2C17.8 4.7 12 4.7 12 4.7s-5.8 0-7.5.5a2.8 2.8 0 0 0-2 2C2 8.9 2 12 2 12s0 3.1.5 4.8a2.8 2.8 0 0 0 2 2c1.7.5 7.5.5 7.5.5s5.8 0 7.5-.5a2.8 2.8 0 0 0 2-2C22 15.1 22 12 22 12s0-3.1-.5-4.8ZM10 15.5v-7l6 3.5-6 3.5Z" /></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.2 3.6 8.5S14.4 18.1 12 20.5C9.6 18.1 8.4 15.3 8.4 12S9.6 5.9 12 3.5Z" /></svg>;
}

function BroSeal() {
  return <span className="bro-seal" aria-label="Reconocimiento especial: Bro">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.1 9.1c.6-1.8 1.5-3.4 2.8-4.9l1.4 1.1-1.1 2.1 1.8 1.1 2.1-1.3c1.6.9 2.8 2.2 3.7 3.8l-1.5 1.2 1.6 1.5c-.8 2.9-2.8 4.8-5.9 5.7l-3.4-.8-3.2-2.8.6-2.1-1.7-1.6 1.8-2.9 2.4.8Z" /><path d="M10.4 12.2c1.2-.6 2.5-.7 3.8-.2" /></svg>
    <span>BRO</span>
  </span>;
}

function MageSeal() {
  return <span className="mage-seal" aria-label="Reconocimiento especial: Mago">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 13 8-10 8 10H4Z" /><path d="M5.5 13h13v3.2c-3.8 1.9-9.2 1.9-13 0V13ZM17.7 6.5l2.6-1.2M18.6 9.2l2.7.8" /><rect x="14.8" y="15.2" width="4.4" height="5.6" rx=".7" transform="rotate(12 17 18)" /><path d="m16.3 16.8 1.8 2.1" /></svg>
    <span>MAGO</span>
  </span>;
}

function networkLabel(network: HistoryItem["network"]) {
  return { instagram: "Instagram", tiktok: "TikTok", facebook: "Facebook", youtube: "Video", web: "Web" }[network];
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
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [registrationPrompt, setRegistrationPrompt] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [giftCode, setGiftCode] = useState("");
  const [giftMessage, setGiftMessage] = useState("");
  const [giftBusy, setGiftBusy] = useState(false);
  const [startingDownload, setStartingDownload] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const batchPollTimers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const pollFailures = useRef(0);
  const pendingGiftRedeeming = useRef(false);
  const authConfigured = authIsConfigured();

  const loadAccount = useCallback(async (token = "") => {
    try {
      const response = await fetch("/api/account", {
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const nextAccount = (await readJson(response)) as Account;
      // Backward compatibility for the API currently running in production.
      // This request is invisible to the user and will be unnecessary once
      // the VPS deploy of the no-gate backend is complete.
      if (token && nextAccount.authenticated && !nextAccount.termsAccepted) {
        const legacyAcceptance = await fetch("/api/account/terms", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: "{}",
        });
        if (legacyAcceptance.ok) {
          setAccount((await readJson(legacyAcceptance)) as Account);
          return;
        }
      }
      setAccount(nextAccount);
    } catch {
      setFormError("No pudimos inicializar tu cuenta. Recargá la página.");
    }
  }, []);

  const loadHistory = useCallback(async (token: string) => {
    if (!token) return;
    setHistoryBusy(true);
    try {
      const response = await fetch("/api/history", {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const payload = (await readJson(response)) as { items?: HistoryItem[] };
      setHistory(payload.items || []);
    } finally {
      setHistoryBusy(false);
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

  useEffect(() => {
    const code = window.sessionStorage.getItem(PENDING_GIFT_CODE_KEY)?.trim();
    if (!code || !accessToken || !account?.authenticated || pendingGiftRedeeming.current) return;

    pendingGiftRedeeming.current = true;
    window.sessionStorage.removeItem(PENDING_GIFT_CODE_KEY);
    void (async () => {
      try {
        const response = await fetch("/api/gifts/redeem", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
          body: JSON.stringify({ code }),
        });
        const updated = (await readJson(response)) as Account;
        setAccount(updated);
        setGiftCode("");
        setGiftMessage("Código aplicado: Video Pro queda activo sin vencimiento.");
      } catch (error) {
        setGiftMessage(error instanceof Error ? error.message : "No pudimos aplicar el código.");
      } finally {
        pendingGiftRedeeming.current = false;
      }
    })();
  }, [accessToken, account?.authenticated]);

  useEffect(() => {
    if (account?.plan === "pro" && accessToken) {
      void loadHistory(accessToken);
    } else if (account?.plan !== "pro") {
      setHistory([]);
    }
  }, [account?.plan, accessToken, loadHistory]);

  // Links from the public site focus the only access field: the same email
  // flow creates a new account or restores an existing one.
  useEffect(() => {
    const intent = new URLSearchParams(window.location.search).get("auth");
    if (intent !== "signup") return;
    window.setTimeout(() => {
      document.querySelector("#cuenta")?.scrollIntoView({ behavior: "smooth", block: "center" });
      document.querySelector<HTMLInputElement>("#account-email")?.focus();
    }, 100);
  }, []);

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
      if (next.status === "complete" && accessToken) void loadHistory(accessToken);
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
      if (next.status === "complete" && accessToken) void loadHistory(accessToken);
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

  async function requestAccessLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const auth = getSupabaseBrowserClient();
    if (!auth) {
      setAuthMessage("El registro está listo; falta conectar el servicio de email.");
      return;
    }
    setAuthBusy(true);
    setAuthMessage("");
    setRegistrationPrompt("");
    const pendingGiftCode = giftCode.trim().toUpperCase().replace(/\s+/g, "");
    if (pendingGiftCode) window.sessionStorage.setItem(PENDING_GIFT_CODE_KEY, pendingGiftCode);
    const result = await Promise.race([
      auth.auth.signInWithOtp({
        email: loginEmail.trim(),
        options: {
          shouldCreateUser: true,
          emailRedirectTo: `${window.location.origin}/app`,
        },
      }).then(({ error }) => ({ error, timedOut: false })),
      wait(20_000).then(() => ({
        error: new Error("El correo está demorando más de lo normal."),
        timedOut: true,
      })),
    ]);
    setAuthBusy(false);
    setAuthMessage(result.timedOut
      ? "El correo está demorando más de lo normal. Revisá que SMTP esté guardado en Supabase y probá de nuevo."
      : result.error
      ? "No pudimos enviar el enlace. Revisá el email e intentá otra vez."
      : "Te enviamos un enlace de acceso. Revisá tu correo.");
  }

  async function redeemGiftCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken) return;
    setGiftBusy(true);
    setGiftMessage("");
    try {
      const response = await fetch("/api/gifts/redeem", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ code: giftCode }),
      });
      const updated = (await readJson(response)) as Account;
      setAccount(updated);
      setGiftCode("");
      setGiftMessage("Código aplicado: Video Pro queda activo sin vencimiento.");
    } catch (error) {
      setGiftMessage(error instanceof Error ? error.message : "No pudimos aplicar el código.");
    } finally {
      setGiftBusy(false);
    }
  }

  async function signOut() {
    const auth = getSupabaseBrowserClient();
    if (!auth) return;
    await auth.auth.signOut();
    setAccessToken("");
    setRegistrationPrompt("");
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
    const field = account?.authenticated ? "#gift-code" : "#account-email";
    window.setTimeout(() => document.querySelector<HTMLInputElement>(field)?.focus(), 250);
  }

  const batchBusy = batchJobs.some((item) => !["complete", "error"].includes(item.status));
  const busy = startingDownload || (!!job && !["complete", "error"].includes(job.status)) || batchBusy;
  const proCandidate = account?.plan === "pro";
  const activeQueueCount = (job && !["complete", "error"].includes(job.status) ? 1 : 0)
    + batchJobs.filter((item) => !["complete", "error"].includes(item.status)).length;
  const videoQuotaExhausted = mode === "video" && !!account && !proCandidate && account.freeVideosRemaining <= 0;
  const freeQuotaCopy = account?.authenticated
    ? `Te quedan ${account.freeVideosRemaining} de ${account.freeVideoLimit} videos gratis hasta 1080p`
    : "1 video de prueba + 5 videos gratis al registrarte";

  return (
    <main className={`site-shell ${proCandidate ? "pro-active" : ""}`}>
      <nav className="topbar" aria-label="Navegación principal">
        <Link className="brand" href="/" prefetch={false} aria-label="PacheVideo, volver al inicio">
          <img className="brand-logo" src="/logo.png" alt="" />
          <span>PACHEVIDEO</span>
        </Link>
        <div className="app-topbar-actions">
          <Link className="back-home-link" href="/" prefetch={false}>Inicio</Link>
          <span className={`server-pill ${serverOnline === false ? "offline" : ""}`}>
            <i /> {serverOnline === null ? "Conectando…" : serverOnline ? "Servidor disponible" : "Servidor sin conexión"}
          </span>
        </div>
      </nav>

      <section className="desktop-promo" aria-label="Descargar PacheVideo Desktop">
        <span className="desktop-promo-icon" aria-hidden="true">↧</span>
        <span><b>PacheVideo para Windows</b><small>Instalalo para máximo rendimiento en tus descargas.</small></span>
        <a className="desktop-download-primary" href="https://github.com/Pachecoins/PacheVideoPlugin/releases/download/v0.5.2/PacheVideo-Setup-Windows-x64.exe">Descargar para Windows <i aria-hidden="true">→</i></a>
        <small className="desktop-mac-note">¿Usás Mac? Consultanos para instalarlo.</small>
      </section>

      <section className="app-hero" id="inicio">
        <div className="eyebrow">TU VIDEO, LISTO EN SEGUNDOS</div>
        <h1>Descargá. Convertí.<br /><span>Seguí creando.</span></h1>
        <p className="lede">
          Pegá el enlace, elegí el formato y nosotros hacemos el resto.
          Sin instalar nada y desde cualquier dispositivo.
        </p>

        <section className={`account-panel ${account?.authenticated ? "signed-in" : ""} ${proCandidate ? "pro-account" : ""}`} id="cuenta" aria-labelledby="account-title">
          <div>
            <span className="account-kicker">TU CUENTA</span>
            <h2 id="account-title">{account === null
              ? "Recuperando tu sesión…"
              : account.authenticated
                ? `Hola, ${account.email}`
                : "Ingresá con tu email"}</h2>
            {proCandidate && <span className="pro-badge">VIDEO PRO · ACTIVO</span>}
            {account?.proBadge === "bro" && <BroSeal />}
            {account?.proBadge === "mage" && <MageSeal />}
            <p>{account === null
              ? "Estamos comprobando si ya habías iniciado sesión en este dispositivo."
              : account.authenticated
                ? account.plan === "pro"
                  ? "Video Pro está vinculado a tu email y funciona en todos tus dispositivos."
                  : `${account.freeVideosRemaining} de ${account.freeVideoLimit} videos gratis disponibles hasta 1080p.`
                : "Si es tu primera vez, recibís 5 videos gratis. Si ya tenés cuenta, recuperás tu plan."}</p>
          </div>
          {account === null ? (
            <div className="session-loading" role="status" aria-live="polite">
              <i aria-hidden="true" /> Comprobando cuenta
            </div>
          ) : account.authenticated ? (
            <div className="account-signed-actions">
              {!proCandidate && (
                <form className="gift-form" onSubmit={redeemGiftCode}>
                  <input
                    id="gift-code"
                    aria-label="Código de regalo Video Pro"
                    placeholder="Código de regalo"
                    value={giftCode}
                    onChange={(event) => setGiftCode(event.target.value)}
                    disabled={giftBusy}
                    required
                  />
                  <button type="submit" disabled={giftBusy}>{giftBusy ? "Aplicando…" : "Canjear"}</button>
                </form>
              )}
              <button className="account-secondary" type="button" onClick={() => void signOut()}>Cerrar sesión</button>
              {giftMessage && <small role="status">{giftMessage}</small>}
            </div>
          ) : (
            <form className="account-form" onSubmit={requestAccessLink}>
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
                  {authBusy ? "Enviando…" : giftCode.trim() ? "Crear cuenta y activar" : "Continuar"}
                </button>
              </div>
              <label className="account-email-label" htmlFor="registration-gift-code">Código de invitación <small>(opcional)</small></label>
              <input
                id="registration-gift-code"
                type="text"
                autoComplete="off"
                placeholder="PV-GIFT-..."
                value={giftCode}
                onChange={(event) => setGiftCode(event.target.value)}
                disabled={authBusy}
              />
              <small className="account-auth-message">¿Tenés un código? Pegalo ahora: se activará automáticamente después de confirmar tu email.</small>
              {registrationPrompt && <small className="account-auth-warning" role="alert">{registrationPrompt}</small>}
              {authMessage && <small className="account-auth-message" role="status">{authMessage}</small>}
            </form>
          )}
          {!authConfigured && <small>Registro preparado · falta conectar el servicio de email.</small>}
          <div className={`account-plan-summary ${proCandidate ? "pro-mode-strip" : ""}`} aria-label="Beneficios del plan">
            <div>
              <span>{proCandidate ? "VIDEO PRO ACTIVO" : "PLAN GRATIS"}</span>
              <strong>{proCandidate ? "2K, 4K y máxima calidad habilitadas" : freeQuotaCopy}</strong>
            </div>
            <a href={account?.authenticated ? "#planes" : "#cuenta"}>{proCandidate ? "Ver tu plan" : account?.authenticated ? "Ver planes" : "Ingresar"}</a>
          </div>
        </section>

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
                  placeholder={"https://sitio-ejemplo.com/video\nhttps://instagram.com/...\nhttps://facebook.com/..."}
                  value={batchUrls}
                  onChange={(event) => setBatchUrls(event.target.value)}
                  disabled={busy}
                  required
                />
                <button className="paste-button" type="button" onClick={pasteUrl} disabled={busy}>Pegar</button>
              </div>
              <p>Hasta 20 enlaces, uno por línea. Podés mezclar enlaces de redes y otras fuentes compatibles.</p>
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

          <div className={`pro-unlock ${proCandidate ? "pro-unlock-active" : ""}`}>
            <div>
              <strong>{proCandidate ? "Video Pro activo" : "Video Pro"}</strong>
              <span>{proCandidate ? "Máxima velocidad, calidad y listas de hasta 20 enlaces habilitadas." : "2K, 4K, máxima calidad, listas de enlaces y procesamiento prioritario."}</span>
            </div>
            {!proCandidate && <span className="pro-preview-link">Solo por invitación</span>}
          </div>

          <button
            className="primary-action"
            type={videoQuotaExhausted ? "button" : "submit"}
            disabled={!account || busy || serverOnline === false}
            onClick={videoQuotaExhausted ? focusRegistration : undefined}
          >
            {!account
              ? "Preparando tu cuenta…"
              : busy
              ? "Preparando…"
              : videoQuotaExhausted
                ? account?.authenticated ? "Ingresar código de invitación" : "Registrarme y obtener 5 videos"
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
                <span>COLA DE DESCARGAS</span>
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

        {proCandidate && (
          <section className="pro-history" aria-labelledby="history-title">
            <div className="pro-history-heading">
              <div>
                <span>HERRAMIENTAS PRO</span>
                <h2 id="history-title">Historial de descargas</h2>
              </div>
              <strong>{activeQueueCount > 0 ? `${activeQueueCount} en cola` : "Cola vacía"}</strong>
            </div>
            {historyBusy ? (
              <p className="history-empty">Actualizando tu historial…</p>
            ) : history.length ? (
              <div className="history-grid">
                {history.map((item) => (
                  <article className="history-item" key={item.id}>
                    <div className="history-thumb" aria-hidden="true">
                      {item.thumbnailUrl ? <img src={item.thumbnailUrl} alt="" /> : <NetworkIcon network={item.network} />}
                    </div>
                    <div className="history-copy">
                      <span className={`network-icon ${item.network}`} aria-label={networkLabel(item.network)}><NetworkIcon network={item.network} /> {networkLabel(item.network)}</span>
                      <strong>{item.title}</strong>
                      <small>{item.mode === "audio" ? "Audio MP3" : `${item.quality === "max" ? "Máxima calidad" : `${item.quality}p`} · MP4`} · {item.status === "complete" ? item.available ? "Disponible" : "Archivo vencido" : item.status === "error" ? "No disponible" : "En proceso"}</small>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="history-empty">Todavía no descargaste nada con Video Pro. Tus próximas descargas aparecerán acá.</p>
            )}
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

        {!proCandidate && <section className="plans-section" id="planes" aria-labelledby="plans-title">
          <div className="section-heading">
            <span>PLANES SIMPLES</span>
            <h2 id="plans-title">Elegí cómo querés descargar</h2>
            <p>Creá tu cuenta gratis y recibí 5 videos hasta 1080p. Video Pro se habilita únicamente por invitación.</p>
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
                : <a className="plan-status" href="#cuenta">Ingresar o crear cuenta</a>}
            </article>

            <article className="plan-card featured">
              <span className="popular-pill">MÁS ELEGIDO</span>
              <span className="plan-name">PACHEVIDEO PRO</span>
              <div className="plan-price"><strong>Pro</strong><span>solo por invitación</span></div>
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
                : <span className="plan-status pro-status">Activación mediante código</span>}
            </article>
          </div>
        </section>}
      </section>
    </main>
  );
}
