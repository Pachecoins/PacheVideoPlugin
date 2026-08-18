from __future__ import annotations

from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from typing import Literal
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
import yt_dlp


VERSION = "0.5.1"
DATA_DIR = Path(os.getenv("PACHEVIDEO_DATA_DIR", "/data")).resolve()
DOWNLOAD_DIR = DATA_DIR / "downloads"
DB_PATH = DATA_DIR / "pachevideo.sqlite3"
FFMPEG = os.getenv("PACHEVIDEO_FFMPEG") or shutil.which("ffmpeg")
PUBLIC_BASE_URL = os.getenv("PACHEVIDEO_PUBLIC_BASE_URL", "").rstrip("/")
ALLOWED_HOSTS = {
    value.strip().lower()
    for value in os.getenv("PACHEVIDEO_ALLOWED_HOSTS", "").split(",")
    if value.strip()
}
ALLOWED_ORIGINS = [
    value.strip()
    for value in os.getenv("PACHEVIDEO_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if value.strip()
]
MAX_FILE_BYTES = int(os.getenv("PACHEVIDEO_MAX_FILE_BYTES", str(2 * 1024**3)))
MAX_DURATION_SECONDS = int(os.getenv("PACHEVIDEO_MAX_DURATION_SECONDS", "10800"))
JOB_TTL_SECONDS = int(os.getenv("PACHEVIDEO_JOB_TTL_SECONDS", "3600"))
HISTORY_TTL_SECONDS = int(os.getenv("PACHEVIDEO_HISTORY_TTL_SECONDS", str(60 * 60 * 24 * 90)))
WORKERS = max(1, int(os.getenv("PACHEVIDEO_WORKERS", "2")))
RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("PACHEVIDEO_RATE_LIMIT_PER_MINUTE", "8")))
MAX_ACTIVE_JOBS = max(1, int(os.getenv("PACHEVIDEO_MAX_ACTIVE_JOBS", "40")))
FREE_ACTIVE_JOBS = max(1, int(os.getenv("PACHEVIDEO_FREE_ACTIVE_JOBS", "1")))
PRO_ACTIVE_JOBS = max(1, int(os.getenv("PACHEVIDEO_PRO_ACTIVE_JOBS", "3")))
ACCOUNT_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("PACHEVIDEO_ACCOUNT_RATE_LIMIT_PER_MINUTE", "25")))
DISK_HEADROOM_MULTIPLIER = max(1.0, float(os.getenv("PACHEVIDEO_DISK_HEADROOM_MULTIPLIER", "1.2")))
DOWNLOAD_ATTEMPTS = max(1, int(os.getenv("PACHEVIDEO_DOWNLOAD_ATTEMPTS", "3")))
MAX_PROCESSING_SECONDS = max(60, int(os.getenv("PACHEVIDEO_MAX_PROCESSING_SECONDS", "3600")))
RETRY_BASE_SECONDS = max(0.0, float(os.getenv("PACHEVIDEO_RETRY_BASE_SECONDS", "1.5")))
RETRY_MAX_SECONDS = max(RETRY_BASE_SECONDS, float(os.getenv("PACHEVIDEO_RETRY_MAX_SECONDS", "20")))
FREE_DOWNLOAD_RATE_LIMIT = max(0, int(os.getenv("PACHEVIDEO_FREE_DOWNLOAD_RATE_LIMIT", "2000000")))
PRO_CONCURRENT_FRAGMENTS = max(1, int(os.getenv("PACHEVIDEO_PRO_CONCURRENT_FRAGMENTS", "4")))
PRO_BATCH_MAX_ITEMS = max(1, int(os.getenv("PACHEVIDEO_PRO_BATCH_MAX_ITEMS", "20")))
INTERNAL_PROXY_TOKEN = os.getenv("PACHEVIDEO_INTERNAL_TOKEN", "").strip()
SESSION_COOKIE_NAME = "pachevideo_session"
SESSION_TTL_SECONDS = max(86_400, int(os.getenv("PACHEVIDEO_SESSION_TTL_SECONDS", str(180 * 86_400))))
COOKIE_SECURE = os.getenv("PACHEVIDEO_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
MP_ACCESS_TOKEN = os.getenv("PACHEVIDEO_MP_ACCESS_TOKEN", "").strip()
MP_BACK_URL = os.getenv("PACHEVIDEO_MP_BACK_URL", "").strip()
MP_SUBSCRIPTION_AMOUNT = float(os.getenv("PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT", "9999.99"))
MP_SUBSCRIPTION_CURRENCY = os.getenv("PACHEVIDEO_MP_SUBSCRIPTION_CURRENCY", "ARS").strip() or "ARS"
SUPABASE_URL = os.getenv("PACHEVIDEO_SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.getenv("PACHEVIDEO_SUPABASE_ANON_KEY", "").strip()
TERMS_VERSION = "2026-08-17"

# One-use launch gifts. Only hashes are kept in the repository and database.
LAUNCH_GIFT_CODE_HASHES = (
    "575f2d166b434f83298d3873f25f77863af086427bb6b01d65ca8ae502383ddf",
    "5b19e2628450634b698ce117dee53ae15ab85672a11ca38312a8b37265540af3",
    "2125b2e5923e24875402760f40fe3e375a10137cc26c03ac35018fe5d343786f",
    "74b34e3133d881fbb0186642852a3a02caa265ae1df02af10595895f62d0419d",
    "076b86485465540e1fe55c3cafdab967288b377f6c3e53b26f6cf4c9ca143421",
    "c6a55b4cba5baca2bf5d6b6f0dca200a8f6df0d6d1b99141400278f8053740b0",
    "c164551e54e6b9f0d1d30eb61cc74ca08cbf1d07d0d265259c088f7c2bb096a6",
    "adf021a43e2666df71f9c3965ab3aa6e3762ad851d3783bb1431e134588699ba",
    "9576201c4392a5e5a251f2e470fd438acfc5d28b2da5ae79e5ab79d690ed190b",
    "18048e761fca467d16e9339510a13fadb85ed720f6aa679d0a26150dcc630103",
    "a9a49d5537518c5216fa803f782ee2c177f80965486a9f3a7561ce3439ae6d9a",
    "1dbbaad78ab5734dd19aecb56fd7ea571a2b18f349486f6e6ead15c438cdbc09",
    "ad1c463af3d39851740ef4e0e5d1ceb1a2466394842368ace6a65799440cc922",
    "bad1bad8b0cce06db6db16a64e5fe670d51a57c3ca7e1800bfe5c3fbd6b8eacf",
    "7f40b99fa4e55cda9ce86b90be221d58585be626e487de07142bf01491a58124",
    "22dfd652a8e4b503c2544282e2cda1b5d92fc18d4c19fd011ee0a5a8d2a59350",
    "5c6e513b58e082164adcf66152067607eb53519651b6cc6d2ef7b1fdb77c91f7",
    "62b62b507fd2ca172b4d1c2acaabe01562571f5e4138cef82ca331889e65c962",
    "35dc48828469c6336a4fe9bf8ca64c0221ab5c67fe339c5390ec3ceeaa3351f8",
    "740215fecdf4e86332740086b81e137f628a0ce6221254199b7e838e51f55573",
    "2c1e1c669ec5de052271e0c957f2219ab0022ab1a09d9ef7a8f7d2b020846cfb",
    "168e302ef50b56229014feafa0d98f9a09b7a8405c75c15c18549b6c178711de",
    "0fd65e465271701b98df5b4d9e28ec9fe845c593cc0da5e3eeb0cef0fcaf9f8e",
    "8b6ac15fb9afd8d21c3fff2d3b169cfac28db970a046ea9d3c24f5f972314ac8",
)

FREE_VIDEO_QUALITIES = {"480", "720", "1080"}
# An anonymous session exists only to preserve the UI. Download credits are
# granted after the email identity is verified, never by minting cookies.
ANONYMOUS_FREE_VIDEO_LIMIT = 0
REGISTERED_FREE_VIDEO_LIMIT = 5
TRANSIENT_ERROR_MARKERS = (
    "http error 403",
    "http error 408",
    "http error 409",
    "http error 425",
    "http error 429",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
    "connection refused",
    "remote end closed",
    "temporary failure",
    "temporarily unavailable",
    "unable to download",
    "fragment",
    "requested format is not available",
)
PERMANENT_ERROR_MARKERS = (
    "unsupported url",
    "private video",
    "video unavailable",
    "login required",
    "sign in to confirm your age",
    "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot",
    "not a bot",
    "copyright",
)

executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="pachevideo")
rate_windows: dict[str, deque[float]] = defaultdict(deque)
account_rate_windows: dict[str, deque[float]] = defaultdict(deque)
rate_lock = threading.Lock()
stop_cleanup = threading.Event()


class CreateJob(BaseModel):
    url: HttpUrl
    mode: Literal["video", "audio"] = "video"
    quality: Literal["max", "2160", "1440", "1080", "720", "480"] = "1080"
    audioKbps: Literal["320", "256", "192", "128"] = "320"
    requestId: str | None = None
    requestToken: str | None = None


class CreateBatch(BaseModel):
    urls: list[HttpUrl]
    mode: Literal["video", "audio"] = "video"
    quality: Literal["max", "2160", "1440", "1080", "720", "480"] = "1080"
    audioKbps: Literal["320", "256", "192", "128"] = "320"
    requestId: str | None = None
    requestToken: str | None = None


class StartSubscription(BaseModel):
    returnUrl: HttpUrl | None = None


class RedeemGiftCode(BaseModel):
    code: str


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                mode TEXT NOT NULL,
                quality TEXT NOT NULL,
                audio_kbps TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                file_path TEXT,
                file_name TEXT,
                thumbnail_url TEXT,
                token_hash TEXT NOT NULL,
                error TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                plan TEXT NOT NULL DEFAULT 'free',
                account_id TEXT,
                request_id TEXT,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS network_identities (
                network_hash TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_ledger (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                network_hash TEXT,
                job_id TEXT,
                event TEXT NOT NULL,
                credits INTEGER NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
            """
        )
        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        migrations = {
            "attempt": "ALTER TABLE jobs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0",
            "max_attempts": "ALTER TABLE jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3",
            "plan": "ALTER TABLE jobs ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'",
            "account_id": "ALTER TABLE jobs ADD COLUMN account_id TEXT",
            "request_id": "ALTER TABLE jobs ADD COLUMN request_id TEXT",
            "thumbnail_url": "ALTER TABLE jobs ADD COLUMN thumbnail_url TEXT",
        }
        for column, statement in migrations.items():
            if column not in existing_columns:
                connection.execute(statement)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                plan TEXT NOT NULL DEFAULT 'free',
                pro_gift INTEGER NOT NULL DEFAULT 0,
                free_video_uses INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        account_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(accounts)").fetchall()
        }
        account_migrations = {
            "auth_provider_id": "ALTER TABLE accounts ADD COLUMN auth_provider_id TEXT",
            "email": "ALTER TABLE accounts ADD COLUMN email TEXT",
            "pro_gift": "ALTER TABLE accounts ADD COLUMN pro_gift INTEGER NOT NULL DEFAULT 0",
            "terms_accepted_at": "ALTER TABLE accounts ADD COLUMN terms_accepted_at REAL",
            "terms_version": "ALTER TABLE accounts ADD COLUMN terms_version TEXT",
        }
        for column, statement in account_migrations.items():
            if column not in account_columns:
                connection.execute(statement)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visitor_sessions (
                token_hash TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gift_codes (
                code_hash TEXT PRIMARY KEY,
                redeemed_at REAL,
                redeemed_by_account_id TEXT,
                FOREIGN KEY (redeemed_by_account_id) REFERENCES accounts(id)
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO gift_codes (code_hash) VALUES (?)",
            ((value,) for value in LAUNCH_GIFT_CODE_HASHES),
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                provider_subscription_id TEXT UNIQUE,
                status TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_account_expires ON visitor_sessions(account_id, expires_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_subscriptions_account_updated ON subscriptions(account_id, updated_at DESC)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_auth_provider ON accounts(auth_provider_id) WHERE auth_provider_id IS NOT NULL"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_request_id ON jobs(request_id) WHERE request_id IS NOT NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_ledger_account_created ON credit_ledger(account_id, created_at)"
        )
        connection.execute("PRAGMA optimize")


def update_job(job_id: str, **changes: object) -> None:
    if not changes:
        return
    columns = ", ".join(f"{key} = ?" for key in changes)
    values = list(changes.values()) + [job_id]
    with database() as connection:
        connection.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)


def get_job(job_id: str) -> sqlite3.Row | None:
    with database() as connection:
        return connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def public_job(row: sqlite3.Row, token: str | None = None) -> dict[str, object]:
    retrying = row["status"] == "retrying"
    result: dict[str, object] = {
        "id": row["id"],
        "mode": row["mode"],
        "status": "downloading" if retrying else row["status"],
        "progress": row["progress"],
        "message": "Preparando tu archivo…" if retrying else row["message"],
        "detail": "" if retrying else row["detail"],
        "fileName": row["file_name"],
        # `error` stores provider diagnostics for operators. Never expose it to
        # a browser: extractor output can contain internal URLs and file paths.
        "error": row["detail"] if row["status"] == "error" else None,
        "attempt": None if retrying else row["attempt"],
        "maxAttempts": None if retrying else row["max_attempts"],
        "plan": row["plan"],
        "expiresAt": row["expires_at"],
    }
    if row["status"] == "complete" and token:
        base = PUBLIC_BASE_URL
        path = f"/api/jobs/{row['id']}/download?token={token}"
        result["downloadUrl"] = f"{base}{path}" if base else path
    return result


def source_network(raw_url: str) -> str:
    host = (urlparse(raw_url).hostname or "").lower()
    if host == "youtu.be" or host.endswith("youtube.com"):
        return "youtube"
    if host.endswith("instagram.com"):
        return "instagram"
    if host.endswith("tiktok.com"):
        return "tiktok"
    if host.endswith("facebook.com") or host.endswith("fb.watch"):
        return "facebook"
    return "web"


def public_thumbnail(value: object) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.hostname else None


def validate_public_url(raw_url: str) -> None:
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("La URL no es válida")
    if parsed.username or parsed.password:
        raise ValueError("La URL no puede incluir credenciales")
    if ALLOWED_HOSTS and not any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_HOSTS):
        raise ValueError("Esta fuente todavía no está habilitada")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or default_port, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValueError("No se pudo resolver el dominio") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("La URL apunta a una red no permitida")


def format_selector(mode: str, quality: str) -> str:
    if mode == "audio":
        return "bestaudio[ext=webm]/bestaudio/best"
    if quality == "max":
        return (
            "bestvideo[ext=mp4]+bestaudio[ext=webm]/"
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/best"
        )
    height = int(quality)
    return (
        f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=webm]/"
        f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
    )


def compatibility_selector(mode: str, quality: str) -> str:
    """Prefer a single-file stream when a source rejects DASH media URLs."""
    if mode == "audio" or quality == "max":
        return "best[ext=mp4]/best"
    height = int(quality)
    return f"best[ext=mp4][height<={height}]/best[height<={height}]/best"


def session_token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def request_client_ip(request: Request) -> str:
    """Use forwarded client IPs only from our authenticated web proxy."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    supplied_proxy_headers = bool(forwarded or request.headers.get("cf-connecting-ip"))
    supplied_token = request.headers.get("x-pachevideo-internal-token", "")
    proxy_authenticated = bool(INTERNAL_PROXY_TOKEN) and secrets.compare_digest(supplied_token, INTERNAL_PROXY_TOKEN)
    if supplied_proxy_headers and not proxy_authenticated:
        raise HTTPException(status_code=403, detail="Encabezado de proxy no autorizado")
    candidate = forwarded if proxy_authenticated else (request.client.host if request.client else "unknown")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


def network_identity(request: Request) -> str:
    """Pseudonymous containment key; raw IP, UA and fingerprint are never stored."""
    client_ip = request_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:512]
    fingerprint = request.headers.get("x-pachevideo-fingerprint", "")[:128]
    material = f"{client_ip}\x1f{user_agent}\x1f{fingerprint}"
    return sha256(material.encode("utf-8")).hexdigest()


def anonymous_account_from_request(request: Request) -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    now = time.time()
    with database() as connection:
        return connection.execute(
            """
            SELECT accounts.* FROM visitor_sessions
            JOIN accounts ON accounts.id = visitor_sessions.account_id
            WHERE visitor_sessions.token_hash = ? AND visitor_sessions.expires_at > ?
            """,
            (session_token_hash(token), now),
        ).fetchone()


def supabase_user_from_request(request: Request) -> dict[str, str] | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="El acceso por email todavía no está configurado")
    user_request = UrlRequest(
        f"{SUPABASE_URL}/auth/v1/user",
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_ANON_KEY,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(user_request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {401, 403}:
            raise HTTPException(status_code=401, detail="Tu sesión venció. Volvé a ingresar.") from error
        raise HTTPException(status_code=502, detail="No pudimos validar tu cuenta") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="No pudimos validar tu cuenta") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="El servicio de cuentas respondió de forma inválida")
    provider_id = str(payload.get("id") or "")
    email = str(payload.get("email") or "").strip().lower()
    if not provider_id or not valid_email(email):
        raise HTTPException(status_code=401, detail="La cuenta no tiene un email válido")
    return {"id": provider_id, "email": email}


def registered_account_from_request(request: Request) -> sqlite3.Row | None:
    user = supabase_user_from_request(request)
    if not user:
        return None
    now = time.time()
    anonymous = anonymous_account_from_request(request)
    with database() as connection:
        account = connection.execute(
            "SELECT * FROM accounts WHERE auth_provider_id = ?",
            (user["id"],),
        ).fetchone()
        if account:
            if account["email"] != user["email"]:
                connection.execute(
                    "UPDATE accounts SET email = ?, updated_at = ? WHERE id = ?",
                    (user["email"], now, account["id"]),
                )
                account = connection.execute("SELECT * FROM accounts WHERE id = ?", (account["id"],)).fetchone()
            return account
        if anonymous:
            connection.execute(
                """
                UPDATE accounts
                SET auth_provider_id = ?, email = ?, free_video_uses = 0, updated_at = ?
                WHERE id = ?
                """,
                (user["id"], user["email"], now, anonymous["id"]),
            )
            connection.execute(
                "DELETE FROM visitor_sessions WHERE account_id = ?",
                (anonymous["id"],),
            )
            return connection.execute("SELECT * FROM accounts WHERE id = ?", (anonymous["id"],)).fetchone()
        account_id = uuid4().hex
        connection.execute(
            """
            INSERT INTO accounts (id, plan, free_video_uses, created_at, updated_at, auth_provider_id, email)
            VALUES (?, 'free', 0, ?, ?, ?, ?)
            """,
            (account_id, now, now, user["id"], user["email"]),
        )
        return connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()


def account_from_request(request: Request) -> sqlite3.Row | None:
    return registered_account_from_request(request) or anonymous_account_from_request(request)


def create_anonymous_account(network_hash: str | None = None) -> tuple[sqlite3.Row, str]:
    now = time.time()
    token = secrets.token_urlsafe(32)
    with database() as connection:
        account = None
        if network_hash:
            existing = connection.execute(
                "SELECT accounts.* FROM network_identities JOIN accounts ON accounts.id = network_identities.account_id WHERE network_hash = ?",
                (network_hash,),
            ).fetchone()
            if existing:
                account = existing
        if not account:
            account_id = uuid4().hex
            connection.execute(
                "INSERT INTO accounts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (account_id, now, now),
            )
            if network_hash:
                connection.execute(
                    "INSERT INTO network_identities (network_hash, account_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (network_hash, account_id, now, now),
                )
            account = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        connection.execute(
            "INSERT INTO visitor_sessions (token_hash, account_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (session_token_hash(token), account["id"], now + SESSION_TTL_SECONDS, now),
        )
    return account, token


def free_video_limit(account: sqlite3.Row) -> int:
    return REGISTERED_FREE_VIDEO_LIMIT if account["auth_provider_id"] else ANONYMOUS_FREE_VIDEO_LIMIT


def effective_plan(account: sqlite3.Row) -> Literal["free", "pro"]:
    return "pro" if account["plan"] == "pro" or bool(account["pro_gift"]) else "free"


def account_public(account: sqlite3.Row) -> dict[str, object]:
    video_limit = free_video_limit(account)
    video_uses = int(account["free_video_uses"])
    with database() as connection:
        subscription = connection.execute(
            "SELECT status FROM subscriptions WHERE account_id = ? ORDER BY updated_at DESC LIMIT 1",
            (account["id"],),
        ).fetchone()
    return {
        "plan": effective_plan(account),
        "freeVideoUsed": video_uses >= video_limit,
        "freeVideoUses": video_uses,
        "freeVideoLimit": video_limit,
        "freeVideosRemaining": max(0, video_limit - video_uses),
        "subscriptionStatus": subscription["status"] if subscription else None,
        "authenticated": bool(account["auth_provider_id"]),
        "email": account["email"],
        "termsAccepted": bool(account["terms_accepted_at"] and account["terms_version"] == TERMS_VERSION),
    }


def require_account(request: Request) -> sqlite3.Row:
    account = account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Tu cuenta todavía se está preparando automáticamente.")
    return account


def require_registered_account(request: Request) -> sqlite3.Row:
    account = registered_account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Ingresá con tu email para activar Video Pro")
    return account


def require_terms_accepted(account: sqlite3.Row) -> None:
    if not account["terms_accepted_at"] or account["terms_version"] != TERMS_VERSION:
        raise HTTPException(status_code=403, detail="Aceptá los Términos y la Política de Privacidad para continuar.")


def valid_email(value: str) -> bool:
    local, separator, domain = value.strip().partition("@")
    return bool(separator and local and "." in domain and " " not in value)


def mercado_pago_request(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    if not MP_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Las suscripciones todavía no están configuradas")
    body = json.dumps(payload).encode() if payload is not None else None
    request = UrlRequest(
        f"https://api.mercadopago.com/{path.lstrip('/')}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="No pudimos comunicarnos con el sistema de cobro") from error
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="El sistema de cobro respondió de forma inválida")
    return data


def subscription_back_url(payload: StartSubscription) -> str:
    """Use the configured production URL or a tightly scoped local-preview URL."""
    if MP_BACK_URL:
        return MP_BACK_URL
    if payload.returnUrl is None:
        raise HTTPException(status_code=503, detail="Falta configurar la URL de retorno de PacheVideo")

    candidate = urlparse(str(payload.returnUrl))
    hostname = (candidate.hostname or "").lower()
    is_local = candidate.scheme == "http" and hostname in {"localhost", "127.0.0.1"}
    is_cloudflare_preview = candidate.scheme == "https" and hostname.endswith(".trycloudflare.com")
    if not (is_local or is_cloudflare_preview):
        raise HTTPException(status_code=503, detail="Falta configurar la URL pública definitiva de PacheVideo")
    return f"{candidate.scheme}://{candidate.netloc}/app"


def enforce_plan_limits(mode: str, quality: str, plan: str) -> None:
    if mode == "video" and quality not in FREE_VIDEO_QUALITIES and plan != "pro":
        raise ValueError("2K, 4K y calidad máxima están disponibles con Video Pro")


def is_retryable_download_error(error: Exception) -> bool:
    message = str(error).lower()
    if any(marker in message for marker in PERMANENT_ERROR_MARKERS):
        return False
    return isinstance(error, (TimeoutError, ConnectionError, FileNotFoundError, yt_dlp.utils.DownloadError)) or any(
        marker in message for marker in TRANSIENT_ERROR_MARKERS
    )


DOWNLOAD_ERROR_MESSAGES = {
    "fuente_no_soportada": "Esta fuente todavía no es compatible con PacheVideo.",
    "contenido_privado": "El contenido requiere acceso privado y no se puede preparar desde PacheVideo.",
    "contenido_no_disponible": "Este contenido ya no está disponible o no se puede acceder públicamente.",
    "limite_de_tamano": "El archivo supera el tamaño máximo permitido.",
    "limite_de_duracion": "El contenido supera la duración máxima permitida.",
    "error_temporal": "No pudimos preparar el archivo ahora. Probá nuevamente más tarde.",
    "error_desconocido": "No pudimos preparar este archivo. Probá con otra fuente compatible.",
}


def download_error_category(error: Exception) -> str:
    """Classify provider errors without returning provider diagnostics to clients."""
    message = str(error).lower()
    if any(marker in message for marker in ("unsupported url", "no suitable extractor", "unsupported site")):
        return "fuente_no_soportada"
    if any(marker in message for marker in ("private video", "private content", "login required", "sign in to confirm your age")):
        return "contenido_privado"
    if any(marker in message for marker in ("video unavailable", "content unavailable", "deleted", "not a bot", "copyright")):
        return "contenido_no_disponible"
    if any(marker in message for marker in ("max filesize", "max_filesize", "file is larger", "file too large")):
        return "limite_de_tamano"
    if any(marker in message for marker in ("supera el límite", "maximum duration", "duration limit")):
        return "limite_de_duracion"
    if any(marker in message for marker in TRANSIENT_ERROR_MARKERS):
        return "error_temporal"
    return "error_desconocido"


def public_download_error(error: Exception) -> str:
    return DOWNLOAD_ERROR_MESSAGES[download_error_category(error)]


def retry_delay_seconds(attempt: int) -> float:
    return min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1)))


def ensure_processing_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("La descarga superó el tiempo máximo de procesamiento")


def clear_attempt_files(folder: Path) -> None:
    if not folder.exists():
        return
    for item in folder.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)


def locate_output(folder: Path, mode: str) -> Path:
    extension = ".mp3" if mode == "audio" else ".mp4"
    preferred = sorted(folder.glob(f"*{extension}"), key=lambda item: item.stat().st_mtime, reverse=True)
    candidates = preferred or sorted(
        (item for item in folder.iterdir() if item.is_file() and not item.name.endswith(".part")),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No se encontró el archivo procesado")
    return candidates[0]


def inspect_media_codecs(path: Path, ffmpeg: str) -> tuple[str, str | None]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    diagnostic = result.stderr.lower()
    video = re.search(r"video:\s*([a-z0-9_]+)", diagnostic)
    audio = re.search(r"audio:\s*([a-z0-9_]+)", diagnostic)
    if not video:
        raise RuntimeError("No pudimos verificar el formato del video")
    return video.group(1), audio.group(1) if audio else None


def ensure_mobile_compatible_mp4(path: Path, ffmpeg: str | None) -> Path:
    """Return an MP4 with H.264/AAC streams that plays across major devices."""
    if not ffmpeg:
        raise RuntimeError("FFmpeg es necesario para preparar un video compatible")
    video_codec, audio_codec = inspect_media_codecs(path, ffmpeg)
    copy_video = video_codec in {"h264", "avc1"}
    copy_audio = audio_codec is None or audio_codec in {"aac", "mp4a"}
    target = path.with_suffix(".mp4")
    temporary = path.parent / f".{uuid4().hex}.compatible.mp4"
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-map_metadata",
        "0",
        "-sn",
        "-dn",
    ]
    if copy_video:
        command.extend(["-c:v", "copy"])
    else:
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            ]
        )
    if copy_audio:
        command.extend(["-c:a", "copy"])
    else:
        command.extend(["-c:a", "aac", "-b:a", "192k"])
    command.extend(
        [
            "-tag:v",
            "avc1",
            "-movflags",
            "+faststart",
            "-max_muxing_queue_size",
            "4096",
            str(temporary),
        ]
    )
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not temporary.is_file():
            raise RuntimeError("No pudimos convertir el video a un formato compatible")
        if path != target:
            path.unlink(missing_ok=True)
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def run_download(
    job_id: str,
    raw_url: str,
    mode: str,
    quality: str,
    audio_kbps: str,
    plan: Literal["free", "pro"] = "free",
    account_id: str | None = None,
) -> None:
    folder = DOWNLOAD_DIR / job_id
    deadline = time.monotonic() + MAX_PROCESSING_SECONDS
    try:
        folder.mkdir(parents=True, exist_ok=False)
        update_job(
            job_id,
            status="downloading",
            progress=1,
            message="Analizando el contenido…",
            attempt=1,
            max_attempts=DOWNLOAD_ATTEMPTS,
        )

        def match_filter(info: dict, *, incomplete: bool) -> str | None:
            ensure_processing_deadline(deadline)
            duration = info.get("duration")
            if duration and duration > MAX_DURATION_SECONDS:
                return f"El contenido supera el límite de {MAX_DURATION_SECONDS // 60} minutos"
            return None

        def progress_hook(data: dict) -> None:
            ensure_processing_deadline(deadline)
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                progress = min(94, downloaded / total * 94) if total else 3
                speed = data.get("speed") or 0
                detail = f"{speed / 1048576:.1f} MB/s" if speed else ""
                update_job(job_id, progress=progress, message="Descargando…", detail=detail)
            elif status == "finished":
                update_job(job_id, status="processing", progress=95, message="Procesando el archivo…")

        postprocessors: list[dict[str, str]] = []
        if mode == "audio":
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_kbps,
                }
            )

        def options_for_attempt(attempt: int) -> dict[str, object]:
            use_compatibility_format = attempt > 1 and mode == "video"
            options: dict[str, object] = {
                "format": (
                    compatibility_selector(mode, quality)
                    if use_compatibility_format
                    else format_selector(mode, quality)
                ),
                "outtmpl": str(folder / "%(title).160B.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "max_filesize": MAX_FILE_BYTES,
                "match_filter": match_filter,
                "progress_hooks": [progress_hook],
                "postprocessors": postprocessors,
                "socket_timeout": 30,
                "retries": 5,
                "fragment_retries": 5,
                "extractor_retries": 3,
                "file_access_retries": 3,
            }
            if plan == "free" and FREE_DOWNLOAD_RATE_LIMIT:
                options["ratelimit"] = FREE_DOWNLOAD_RATE_LIMIT
            if plan == "pro":
                options["concurrent_fragment_downloads"] = PRO_CONCURRENT_FRAGMENTS
            if mode == "video":
                options["merge_output_format"] = "mp4"
                # Prefer Opus when separate streams work, then encode to AAC for
                # compatibility. Later attempts use a single-file MP4 fallback.
                if not use_compatibility_format:
                    options["postprocessor_args"] = {
                        "merger+ffmpeg": ["-c:a", "aac", "-b:a", "192k"],
                    }
            if FFMPEG:
                options["ffmpeg_location"] = FFMPEG
            return options

        info: dict | None = None
        output: Path | None = None
        last_error: Exception | None = None
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            ensure_processing_deadline(deadline)
            if attempt > 1:
                clear_attempt_files(folder)
                update_job(
                    job_id,
                    status="retrying",
                    progress=1,
                    attempt=attempt,
                    message="Preparando tu archivo…",
                    detail="",
                )
            else:
                update_job(job_id, attempt=attempt)

            try:
                with yt_dlp.YoutubeDL(options_for_attempt(attempt)) as downloader:
                    info = downloader.extract_info(raw_url, download=True)
                    output = locate_output(folder, mode)
                if mode == "video":
                    update_job(job_id, status="processing", progress=96, message="Preparando para tu dispositivo…")
                    output = ensure_mobile_compatible_mp4(output, FFMPEG)
                break
            except Exception as error:
                last_error = error
                if attempt >= DOWNLOAD_ATTEMPTS or not is_retryable_download_error(error):
                    raise
                delay = retry_delay_seconds(attempt)
                update_job(
                    job_id,
                    status="retrying",
                    message="Preparando tu archivo…",
                    detail="",
                )
                if delay:
                    ensure_processing_deadline(deadline)
                    if time.monotonic() + delay >= deadline:
                        raise TimeoutError("La descarga superó el tiempo máximo de procesamiento")
                    time.sleep(delay)

        if info is None or output is None:
            raise last_error or RuntimeError("La descarga no pudo iniciarse")
        ensure_processing_deadline(deadline)
        if output.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("El archivo supera el límite permitido")
        update_job(
            job_id,
            status="complete",
            progress=100,
            message="Descarga lista",
            detail=str(info.get("title") or output.name),
            file_path=str(output),
            file_name=output.name,
            thumbnail_url=public_thumbnail(info.get("thumbnail")),
            attempt=attempt,
            expires_at=time.time() + JOB_TTL_SECONDS,
        )
    except Exception as error:
        shutil.rmtree(folder, ignore_errors=True)
        if plan == "free" and mode == "video" and account_id:
            with database() as connection:
                connection.execute(
                    """
                    UPDATE accounts
                    SET free_video_uses = CASE WHEN free_video_uses > 0 THEN free_video_uses - 1 ELSE 0 END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (time.time(), account_id),
                )
                connection.execute(
                    """
                    INSERT INTO credit_ledger (id, account_id, job_id, event, credits, created_at)
                    VALUES (?, ?, ?, 'video_refunded', 1, ?)
                    """,
                    (uuid4().hex, account_id, job_id, time.time()),
                )
        update_job(
            job_id,
            status="error",
            message="No pudimos preparar el archivo",
            detail=public_download_error(error),
            error=str(error),
            expires_at=time.time() + JOB_TTL_SECONDS,
        )


def recover_incomplete_jobs() -> None:
    """Resume accepted jobs after an API restart without charging quota twice."""
    with database() as connection:
        rows = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('queued', 'downloading', 'processing', 'retrying')
            ORDER BY created_at
            """
        ).fetchall()
        connection.execute(
            """
            UPDATE jobs
            SET status = 'queued', progress = 0, message = 'En cola…', detail = '', error = NULL
            WHERE status IN ('queued', 'downloading', 'processing', 'retrying')
            """
        )
    for row in rows:
        shutil.rmtree(DOWNLOAD_DIR / row["id"], ignore_errors=True)
        executor.submit(
            run_download,
            row["id"],
            row["source_url"],
            row["mode"],
            row["quality"],
            row["audio_kbps"],
            row["plan"],
            row["account_id"],
        )


def cleanup_expired() -> None:
    while not stop_cleanup.wait(60):
        now = time.time()
        with database() as connection:
            rows = connection.execute(
                "SELECT id FROM jobs WHERE expires_at < ? AND status IN ('complete', 'error') AND file_path IS NOT NULL",
                (now,),
            ).fetchall()
            connection.execute(
                "UPDATE jobs SET file_path = NULL WHERE expires_at < ? AND status IN ('complete', 'error')",
                (now,),
            )
            connection.execute(
                "DELETE FROM jobs WHERE created_at < ? AND status IN ('complete', 'error')",
                (now - HISTORY_TTL_SECONDS,),
            )
            connection.execute("DELETE FROM visitor_sessions WHERE expires_at < ?", (now,))
        for row in rows:
            shutil.rmtree(DOWNLOAD_DIR / row["id"], ignore_errors=True)


def consume_rate_limit(client: str) -> None:
    now = time.time()
    with rate_lock:
        for key, entries in list(rate_windows.items()):
            while entries and entries[0] < now - 60:
                entries.popleft()
            if not entries:
                rate_windows.pop(key, None)
        window = rate_windows[client]
        if len(window) >= RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Esperá un minuto.")
        window.append(now)


def consume_account_rate_limit(account_id: str) -> None:
    now = time.time()
    with rate_lock:
        for key, entries in list(account_rate_windows.items()):
            while entries and entries[0] < now - 60:
                entries.popleft()
            if not entries:
                account_rate_windows.pop(key, None)
        window = account_rate_windows[account_id]
        if len(window) >= ACCOUNT_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Esta cuenta alcanzó el límite de solicitudes por minuto.")
        window.append(now)


def enforce_active_job_capacity(incoming: int = 1) -> None:
    """Keep a burst of accepted jobs from exhausting the worker host.

    This is deliberately server-wide. Per-IP limits are useful, but a botnet can
    rotate addresses; the API must also retain enough headroom for jobs already
    running or waiting in the local executor.
    """
    with database() as connection:
        active = connection.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status IN ('queued', 'downloading', 'processing', 'retrying')
            """
        ).fetchone()[0]
    if active + incoming > MAX_ACTIVE_JOBS:
        raise HTTPException(
            status_code=503,
            detail="Hay muchas descargas en curso. Tu archivo se podrá preparar en unos minutos.",
            headers={"Retry-After": "60"},
        )


def enforce_account_job_capacity(account_id: str, plan: Literal["free", "pro"]) -> None:
    limit = PRO_ACTIVE_JOBS if plan == "pro" else FREE_ACTIVE_JOBS
    with database() as connection:
        active = connection.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE account_id = ? AND status IN ('downloading', 'processing', 'retrying')
            """,
            (account_id,),
        ).fetchone()[0]
    if active >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Tu plan permite hasta {limit} descarga{'s' if limit != 1 else ''} simultánea{'s' if limit != 1 else ''}.",
        )


def enforce_disk_capacity(incoming: int = 1) -> None:
    with database() as connection:
        pending = connection.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'downloading', 'processing', 'retrying')"
        ).fetchone()[0]
    required = int(MAX_FILE_BYTES * (pending + incoming) * DISK_HEADROOM_MULTIPLIER)
    if shutil.disk_usage(DOWNLOAD_DIR).free < required:
        raise HTTPException(
            status_code=503,
            detail="No hay espacio suficiente para preparar otra descarga en este momento.",
            headers={"Retry-After": "300"},
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    recover_incomplete_jobs()
    cleanup_thread = threading.Thread(target=cleanup_expired, daemon=True, name="cleanup")
    cleanup_thread.start()
    yield
    stop_cleanup.set()
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="PacheVideo API", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "version": VERSION,
        "ytDlp": yt_dlp.version.__version__,
        "ffmpeg": bool(FFMPEG),
        "workers": WORKERS,
        "downloadAttempts": DOWNLOAD_ATTEMPTS,
        "retryMaxSeconds": RETRY_MAX_SECONDS,
        "freeDownloadRateLimit": FREE_DOWNLOAD_RATE_LIMIT,
        "proBatchMaxItems": PRO_BATCH_MAX_ITEMS,
        "maxActiveJobs": MAX_ACTIVE_JOBS,
        "billingConfigured": bool(MP_ACCESS_TOKEN and MP_BACK_URL),
        "authConfigured": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
    }


@app.get("/api/account")
def account(request: Request) -> JSONResponse:
    current = account_from_request(request)
    if current:
        return JSONResponse(account_public(current), headers={"Cache-Control": "no-store"})
    current, token = create_anonymous_account(network_identity(request))
    response = JSONResponse(account_public(current), headers={"Cache-Control": "no-store"})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/account/terms")
def accept_terms(request: Request) -> dict[str, object]:
    current = require_registered_account(request)
    now = time.time()
    with database() as connection:
        connection.execute(
            "UPDATE accounts SET terms_accepted_at = ?, terms_version = ?, updated_at = ? WHERE id = ?",
            (now, TERMS_VERSION, now, current["id"]),
        )
        updated = connection.execute("SELECT * FROM accounts WHERE id = ?", (current["id"],)).fetchone()
    return account_public(updated)


@app.post("/api/billing/subscriptions")
def start_subscription(payload: StartSubscription, request: Request) -> dict[str, object]:
    raise HTTPException(status_code=404, detail="Video Pro se activa únicamente con un código de invitación")


@app.post("/api/billing/mercadopago/webhook")
async def mercado_pago_webhook(request: Request) -> dict[str, bool]:
    """Synchronize the subscription state from Mercado Pago's canonical API.

    The notification body itself is never trusted to grant access: it only tells
    us which subscription to retrieve with the private server credential.
    """
    try:
        body = await request.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        return {"ok": True}
    topic = str(body.get("type") or request.query_params.get("type") or "")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    provider_id = str(data.get("id") or request.query_params.get("data.id") or "")
    if topic != "subscription_preapproval" or not provider_id:
        return {"ok": True}

    with database() as connection:
        known = connection.execute(
            "SELECT account_id FROM subscriptions WHERE provider_subscription_id = ?",
            (provider_id,),
        ).fetchone()
    if not known:
        return {"ok": True}

    provider = mercado_pago_request("GET", f"/preapproval/{provider_id}")
    if str(provider.get("external_reference") or "") != known["account_id"]:
        return {"ok": True}
    status = str(provider.get("status") or "pending").lower()
    plan: Literal["free", "pro"] = "pro" if status == "authorized" else "free"
    now = time.time()
    with database() as connection:
        connection.execute(
            "UPDATE subscriptions SET status = ?, updated_at = ? WHERE provider_subscription_id = ?",
            (status, now, provider_id),
        )
        connection.execute(
            """
            UPDATE accounts
            SET plan = CASE WHEN pro_gift = 1 THEN 'pro' ELSE ? END,
                updated_at = ?
            WHERE id = ?
            """,
            (plan, now, known["account_id"]),
        )
    return {"ok": True}


@app.post("/api/gifts/redeem")
def redeem_gift_code(payload: RedeemGiftCode, request: Request) -> dict[str, object]:
    """Redeem a launch gift exactly once for the signed-in recipient."""
    current = require_registered_account(request)
    code = payload.code.strip().upper().replace(" ", "")
    if not code.startswith("PV-GIFT-") or len(code) > 80:
        raise HTTPException(status_code=400, detail="El código de regalo no es válido")
    code_hash = sha256(code.encode()).hexdigest()
    now = time.time()
    with database() as connection:
        gift = connection.execute(
            "SELECT redeemed_by_account_id FROM gift_codes WHERE code_hash = ?",
            (code_hash,),
        ).fetchone()
        if not gift:
            raise HTTPException(status_code=404, detail="El código de regalo no existe")
        if gift["redeemed_by_account_id"]:
            raise HTTPException(status_code=409, detail="Este código de regalo ya fue usado")
        claimed = connection.execute(
            """
            UPDATE gift_codes
            SET redeemed_at = ?, redeemed_by_account_id = ?
            WHERE code_hash = ? AND redeemed_by_account_id IS NULL
            """,
            (now, current["id"], code_hash),
        ).rowcount
        if not claimed:
            raise HTTPException(status_code=409, detail="Este código de regalo ya fue usado")
        connection.execute(
            "UPDATE accounts SET plan = 'pro', pro_gift = 1, updated_at = ? WHERE id = ?",
            (now, current["id"]),
        )
        updated = connection.execute("SELECT * FROM accounts WHERE id = ?", (current["id"],)).fetchone()
    return account_public(updated)


@app.get("/api/history")
def download_history(request: Request) -> dict[str, object]:
    current = require_registered_account(request)
    if effective_plan(current) != "pro":
        raise HTTPException(status_code=403, detail="El historial está incluido en Video Pro")
    with database() as connection:
        rows = connection.execute(
            """
            SELECT id, source_url, mode, quality, status, detail, file_name, thumbnail_url, file_path, created_at
            FROM jobs
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (current["id"],),
        ).fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "network": source_network(row["source_url"]),
                "mode": row["mode"],
                "quality": row["quality"],
                "status": row["status"],
                "title": row["detail"] or row["file_name"] or "Archivo preparado",
                "thumbnailUrl": row["thumbnail_url"],
                "available": bool(row["file_path"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
    }


def validate_request_identity(request_id: str | None, request_token: str | None) -> None:
    if bool(request_id) != bool(request_token):
        raise HTTPException(status_code=400, detail="La solicitud de descarga es inválida")
    if request_id and (
        len(request_id) > 80
        or len(request_id) < 16
        or not all(character.isalnum() or character in "-_" for character in request_id)
    ):
        raise HTTPException(status_code=400, detail="La solicitud de descarga es inválida")
    if request_token and (
        len(request_token) > 180
        or len(request_token) < 32
        or not all(character.isalnum() or character in "-_" for character in request_token)
    ):
        raise HTTPException(status_code=400, detail="La solicitud de descarga es inválida")


def enqueue_job(
    payload: CreateJob | CreateBatch,
    raw_url: str,
    account: sqlite3.Row,
    plan: Literal["free", "pro"],
    network_hash: str,
    request_id: str | None = None,
    request_token: str | None = None,
) -> dict[str, object]:
    try:
        validate_public_url(raw_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    try:
        enforce_plan_limits(payload.mode, payload.quality, plan)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    token = request_token or secrets.token_urlsafe(32)
    token_hash = sha256(token.encode()).hexdigest()
    if request_id:
        with database() as connection:
            existing = connection.execute(
                "SELECT * FROM jobs WHERE request_id = ? AND account_id = ?",
                (request_id, account["id"]),
            ).fetchone()
        if existing:
            if not secrets.compare_digest(existing["token_hash"], token_hash):
                raise HTTPException(status_code=409, detail="La solicitud de descarga ya existe")
            return {**public_job(existing, token), "token": token}

    job_id = uuid4().hex
    now = time.time()
    with database() as connection:
        if plan == "free" and payload.mode == "video":
            if not account["auth_provider_id"]:
                raise HTTPException(
                    status_code=403,
                    detail="Registrate gratis con tu email para obtener 5 videos en 1080p.",
                )
            video_limit = free_video_limit(account)
            consumed = connection.execute(
                """
                UPDATE accounts SET free_video_uses = free_video_uses + 1, updated_at = ?
                WHERE id = ? AND free_video_uses < ?
                """,
                (now, account["id"], video_limit),
            ).rowcount
            if not consumed:
                detail = (
                    f"Ya usaste tus {video_limit} videos gratis. Activá Video Pro para continuar."
                    if account["auth_provider_id"]
                    else "Ya usaste tu video de prueba. Registrate gratis y obtené 5 videos en 1080p."
                )
                raise HTTPException(
                    status_code=403,
                    detail=detail,
                )
        connection.execute(
            """
            INSERT INTO jobs (
                id, source_url, mode, quality, audio_kbps, status, progress,
                message, token_hash, attempt, max_attempts, plan, account_id, request_id, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, 'queued', 0, 'En cola…', ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                raw_url,
                payload.mode,
                payload.quality,
                payload.audioKbps,
                token_hash,
                DOWNLOAD_ATTEMPTS,
                plan,
                account["id"],
                request_id,
                now,
                now + JOB_TTL_SECONDS,
            ),
        )
        if plan == "free" and payload.mode == "video":
            connection.execute(
                """
                INSERT INTO credit_ledger (id, account_id, network_hash, job_id, event, credits, created_at)
                VALUES (?, ?, ?, ?, 'video_reserved', -1, ?)
                """,
                (uuid4().hex, account["id"], network_hash, job_id, now),
            )
    executor.submit(
        run_download,
        job_id,
        raw_url,
        payload.mode,
        payload.quality,
        payload.audioKbps,
        plan,
        account["id"],
    )
    row = get_job(job_id)
    return {**public_job(row, token), "token": token}


@app.post("/api/jobs", status_code=202)
def create_job(payload: CreateJob, request: Request) -> dict[str, object]:
    client = request_client_ip(request)
    consume_rate_limit(client)
    account = require_account(request)
    plan = effective_plan(account)
    consume_account_rate_limit(account["id"])
    enforce_account_job_capacity(account["id"], plan)
    enforce_active_job_capacity()
    enforce_disk_capacity()
    validate_request_identity(payload.requestId, payload.requestToken)
    return enqueue_job(
        payload,
        str(payload.url),
        account,
        plan,
        network_identity(request),
        payload.requestId,
        payload.requestToken,
    )


@app.post("/api/jobs/batch", status_code=202)
def create_batch(payload: CreateBatch, request: Request) -> dict[str, object]:
    client = request_client_ip(request)
    consume_rate_limit(client)
    account = require_account(request)
    if effective_plan(account) != "pro":
        raise HTTPException(status_code=403, detail="Las listas de enlaces son una función de Video Pro")
    consume_account_rate_limit(account["id"])
    enforce_account_job_capacity(account["id"], "pro")
    validate_request_identity(payload.requestId, payload.requestToken)
    urls = list(dict.fromkeys(str(item) for item in payload.urls))
    if not urls:
        raise HTTPException(status_code=400, detail="Pegá al menos un enlace")
    if len(urls) > PRO_BATCH_MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"Video Pro permite hasta {PRO_BATCH_MAX_ITEMS} enlaces por lista")
    enforce_active_job_capacity(len(urls))
    enforce_disk_capacity(len(urls))

    jobs: list[dict[str, object]] = []
    for index, raw_url in enumerate(urls):
        request_id = f"{payload.requestId}-{index}" if payload.requestId else None
        request_token = (
            sha256(f"{payload.requestToken}:{index}".encode()).hexdigest()
            if payload.requestToken
            else None
        )
        jobs.append(enqueue_job(payload, raw_url, account, "pro", network_identity(request), request_id, request_token))
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, token: str) -> dict[str, object]:
    row = get_job(job_id)
    if not row or not secrets.compare_digest(row["token_hash"], sha256(token.encode()).hexdigest()):
        raise HTTPException(status_code=404, detail="Trabajo inexistente")
    return public_job(row, token)


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, token: str) -> FileResponse:
    row = get_job(job_id)
    if not row or not secrets.compare_digest(row["token_hash"], sha256(token.encode()).hexdigest()):
        raise HTTPException(status_code=404, detail="Archivo inexistente")
    if row["status"] != "complete":
        raise HTTPException(status_code=409, detail="El archivo todavía no está listo")
    if not row["file_path"]:
        raise HTTPException(status_code=410, detail="El archivo ya no está disponible")
    path = Path(row["file_path"])
    if not path.is_file() or DOWNLOAD_DIR not in path.resolve().parents:
        raise HTTPException(status_code=410, detail="El archivo ya no está disponible")
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "video/mp4"
    return FileResponse(path, filename=row["file_name"], media_type=media_type)
