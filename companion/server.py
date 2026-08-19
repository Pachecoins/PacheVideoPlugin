"""Local yt-dlp/FFmpeg companion for the PacheVideo Premiere UXP panel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import urlparse

import yt_dlp


HOST = "127.0.0.1"
PORT = int(os.environ.get("PACHEVIDEO_PORT", "18765"))
OUTPUT_FOLDER = Path(os.environ.get("PACHEVIDEO_OUTPUT", "~/Downloads/PacheVideo")).expanduser().resolve()
VERSION = "0.5.3"
DOWNLOAD_ATTEMPTS = max(1, int(os.environ.get("PACHEVIDEO_DOWNLOAD_ATTEMPTS", "10")))
RETRY_BASE_SECONDS = max(0.0, float(os.environ.get("PACHEVIDEO_RETRY_BASE_SECONDS", "1.5")))
RETRY_MAX_SECONDS = max(RETRY_BASE_SECONDS, float(os.environ.get("PACHEVIDEO_RETRY_MAX_SECONDS", "20")))
TRANSIENT_ERROR_MARKERS = (
    "http error 403",
    "http error 408",
    "http error 429",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
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
    "copyright",
)


def default_log_folder() -> Path:
    configured = os.environ.get("PACHEVIDEO_LOG_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "PacheVideo" / "logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "PacheVideo"
    return Path.home() / ".local" / "state" / "PacheVideo"


LOG_FOLDER = default_log_folder()
LOG_FILE = LOG_FOLDER / "helper.log"
LOGGER = logging.getLogger("pachevideo.helper")
SESSION_TOKEN = ""
ALLOWED_OUTPUT_FOLDERS: set[Path] = set()
ALLOWED_OUTPUT_FOLDERS_LOCK = threading.Lock()
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def session_token_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "PacheVideo" / "session.token"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PacheVideo" / "session.token"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "PacheVideo" / "session.token"


def create_session_token() -> str:
    """Create a fresh local-only secret for this helper process."""
    token = secrets.token_urlsafe(32)
    token_path = session_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token + "\n", encoding="utf-8")
    if os.name != "nt":
        token_path.chmod(0o600)
    return token


def _restricted_output_folder(path: Path) -> bool:
    normalized = str(path).replace("\\", "/").lower()
    if sys.platform == "win32":
        blocked = ("c:/windows", "c:/program files", "c:/program files (x86)")
    else:
        blocked = ("/system", "/library", "/usr", "/etc")
    return any(normalized == item or normalized.startswith(item + "/") for item in blocked)


def validate_output_folder(value: str | Path) -> Path:
    folder = Path(value).expanduser()
    if not folder.is_absolute():
        raise ValueError("La carpeta de destino debe usar una ruta absoluta")
    resolved = folder.resolve()
    if _restricted_output_folder(resolved):
        raise ValueError("No se puede usar una carpeta del sistema como destino")
    if any(part.startswith(".") for part in resolved.parts if part not in {resolved.anchor, "."}):
        raise ValueError("No se permiten carpetas ocultas como destino")
    return resolved


def allow_output_folder(value: str | Path) -> Path:
    folder = validate_output_folder(value)
    folder.mkdir(parents=True, exist_ok=True)
    with ALLOWED_OUTPUT_FOLDERS_LOCK:
        ALLOWED_OUTPUT_FOLDERS.add(folder)
    return folder


def output_folder_is_allowed(folder: Path) -> bool:
    with ALLOWED_OUTPUT_FOLDERS_LOCK:
        return folder in ALLOWED_OUTPUT_FOLDERS


def safe_output_name(file_name: str, mode: str) -> str:
    """Return a portable, bounded final filename without trusting extractor metadata."""
    extension = ".mp3" if mode == "audio" else ".mp4"
    name = str(file_name).replace("/", "_").replace("\\", "_")
    stem = Path(name).stem
    stem = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]', "_", stem)
    stem = stem.replace("..", "_").strip(" .")
    if not stem:
        stem = "pachevideo"
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    encoded = stem.encode("utf-8")[:120]
    stem = encoded.decode("utf-8", "ignore").rstrip(" .") or "pachevideo"
    return f"{stem}{extension}"


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    LOG_FOLDER.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


class YtDlpLogger:
    def debug(self, message: str) -> None:
        LOGGER.debug(message)

    def info(self, message: str) -> None:
        LOGGER.info(message)

    def warning(self, message: str) -> None:
        LOGGER.warning(message)

    def error(self, message: str) -> None:
        LOGGER.error(message)


def find_ffmpeg() -> str | None:
    configured = os.environ.get("PACHEVIDEO_FFMPEG")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend(
            [
                bundle_root / "ffmpeg.exe",
                bundle_root / "ffmpeg",
                Path(sys.executable).resolve().parent / "ffmpeg.exe",
                Path(sys.executable).resolve().parent / "ffmpeg",
                Path(sys.executable).resolve().parent.parent / "Frameworks" / "ffmpeg",
                Path(sys.executable).resolve().parent.parent / "Resources" / "ffmpeg",
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return shutil.which("ffmpeg")


FFMPEG = find_ffmpeg()


@dataclass
class Job:
    id: str
    url: str
    mode: str
    quality: str
    audioKbps: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "En cola…"
    detail: str = ""
    filePath: str | None = None
    folder: str = str(OUTPUT_FOLDER)
    error: str | None = None
    attempt: int = 0
    maxAttempts: int = DOWNLOAD_ATTEMPTS
    createdAt: float = field(default_factory=time.time)


jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()


def update_job(job: Job, **changes) -> None:
    with jobs_lock:
        for key, value in changes.items():
            setattr(job, key, value)


def format_selector(mode: str, quality: str) -> str:
    if mode == "audio":
        return "bestaudio/best"
    if quality == "max":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    height = int(quality)
    return (
        f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
    )


def compatibility_selector(mode: str, quality: str) -> str:
    if mode == "audio" or quality == "max":
        return "best[ext=mp4]/best"
    height = int(quality)
    return f"best[ext=mp4][height<={height}]/best[height<={height}]/best"


def is_youtube_source(raw_url: str) -> bool:
    """Detect YouTube hosts without matching lookalike domains."""
    hostname = (urlparse(raw_url).hostname or "").lower().rstrip(".")
    return hostname == "youtu.be" or hostname == "youtube.com" or hostname.endswith(".youtube.com")


def selector_for_attempt(raw_url: str, mode: str, quality: str, attempt: int) -> str:
    """Choose a broadly playable single-file fallback before protected DASH streams.

    Some YouTube videos expose high-resolution DASH streams that are rejected by
    the origin even though an ordinary progressive MP4 remains available.  The
    desktop client prioritizes that compatible rendition for YouTube; later
    attempts retain the same safe fallback instead of retrying a denied URL.
    """
    if is_youtube_source(raw_url):
        if mode == "audio":
            # YouTube can reject the audio-only DASH representation while its
            # progressive MP4 remains playable. FFmpeg then extracts the MP3.
            return "best[ext=mp4]/best"
        return compatibility_selector(mode, quality)
    if attempt > 1 and mode == "video":
        return compatibility_selector(mode, quality)
    return format_selector(mode, quality)


def is_retryable_download_error(error: Exception) -> bool:
    message = str(error).lower()
    if any(marker in message for marker in PERMANENT_ERROR_MARKERS):
        return False
    return isinstance(error, (TimeoutError, ConnectionError, yt_dlp.utils.DownloadError)) or any(
        marker in message for marker in TRANSIENT_ERROR_MARKERS
    )


def retry_limit_for_error(error: Exception) -> int:
    """Avoid making people wait through repeated identical origin denials."""
    if "http error 403" in str(error).lower():
        return min(DOWNLOAD_ATTEMPTS, 2)
    return DOWNLOAD_ATTEMPTS


def retry_delay_seconds(attempt: int) -> float:
    return min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1)))


def clear_attempt_files(attempt_folder: Path) -> None:
    if not attempt_folder.exists():
        return
    for candidate in attempt_folder.iterdir():
        if candidate.is_dir():
            shutil.rmtree(candidate, ignore_errors=True)
        else:
            candidate.unlink(missing_ok=True)


def unique_destination(output_folder: Path, file_name: str) -> Path:
    candidate = output_folder / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10_000):
        candidate = output_folder / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError("No se pudo elegir un nombre de archivo libre")


def locate_output(ydl: yt_dlp.YoutubeDL, info: dict, mode: str, output_folder: Path) -> Path:
    prepared = Path(ydl.prepare_filename(info))
    expected = prepared.with_suffix(".mp3" if mode == "audio" else ".mp4")
    if expected.exists():
        return expected
    if prepared.exists():
        return prepared

    title_prefix = prepared.stem
    matches = sorted(
        output_folder.glob(f"{title_prefix}.*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    raise FileNotFoundError("yt-dlp terminó, pero no se encontró el archivo generado.")


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
    if not ffmpeg:
        raise RuntimeError("FFmpeg es necesario para preparar un video compatible")
    video_codec, audio_codec = inspect_media_codecs(path, ffmpeg)
    copy_video = video_codec in {"h264", "avc1"}
    copy_audio = audio_codec is None or audio_codec in {"aac", "mp4a"}
    target = path.with_suffix(".mp4")
    temporary = path.parent / f".{uuid.uuid4().hex}.compatible.mp4"
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


def run_download(job: Job) -> None:
    attempt_folder: Path | None = None
    try:
        output_folder = Path(job.folder).expanduser().resolve()
        output_folder.mkdir(parents=True, exist_ok=True)
        attempt_folder = output_folder / f".pachevideo-{job.id}"
        attempt_folder.mkdir(parents=True, exist_ok=False)
        update_job(
            job,
            status="downloading",
            progress=1,
            message="Analizando el contenido…",
            attempt=1,
            maxAttempts=DOWNLOAD_ATTEMPTS,
        )

        def progress_hook(data: dict) -> None:
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                progress = (downloaded / total * 94) if total else max(job.progress, 3)
                speed = data.get("speed") or 0
                eta = data.get("eta")
                speed_text = f"{speed / 1048576:.1f} MB/s" if speed else ""
                eta_text = f"ETA {eta}s" if eta is not None else ""
                detail = " · ".join(part for part in (speed_text, eta_text) if part)
                update_job(job, progress=progress, message="Descargando…", detail=detail)
            elif status == "finished":
                update_job(job, progress=95, status="processing", message="Procesando con FFmpeg…")

        postprocessors = []
        if job.mode == "audio":
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": job.audioKbps,
                }
            )

        def options_for_attempt(attempt: int) -> dict[str, object]:
            selected_format = selector_for_attempt(job.url, job.mode, job.quality, attempt)
            use_compatibility_format = selected_format == compatibility_selector(job.mode, job.quality)
            options: dict[str, object] = {
                "format": selected_format,
                "outtmpl": str(attempt_folder / "%(title).120B.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "logger": YtDlpLogger(),
                "progress_hooks": [progress_hook],
                "postprocessors": postprocessors,
                "socket_timeout": 30,
                "retries": 5,
                "fragment_retries": 5,
                "extractor_retries": 3,
                "file_access_retries": 3,
            }
            if job.mode == "video":
                options["merge_output_format"] = "mp4"
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
            if attempt > 1:
                clear_attempt_files(attempt_folder)
                update_job(
                    job,
                    status="retrying",
                    progress=1,
                    attempt=attempt,
                    message="Preparando tu archivo…",
                    detail="",
                )
            else:
                update_job(job, attempt=attempt)

            try:
                with yt_dlp.YoutubeDL(options_for_attempt(attempt)) as ydl:
                    info = ydl.extract_info(job.url, download=True)
                    output = locate_output(ydl, info, job.mode, attempt_folder)
                if job.mode == "video":
                    update_job(job, progress=96, status="processing", message="Preparando para tu dispositivo…")
                    output = ensure_mobile_compatible_mp4(output, FFMPEG)
                break
            except Exception as error:
                last_error = error
                if attempt >= retry_limit_for_error(error) or not is_retryable_download_error(error):
                    if "http error 403" in str(error).lower():
                        raise RuntimeError(
                            "Esta fuente rechazó la reproducción desde la app. "
                            "Probamos formatos alternativos, pero no respondió."
                        ) from error
                    raise
                delay = retry_delay_seconds(attempt)
                update_job(
                    job,
                    status="retrying",
                    message="Preparando tu archivo…",
                    detail="",
                )
                if delay:
                    time.sleep(delay)

        if info is None or output is None:
            raise last_error or RuntimeError("La descarga no pudo iniciarse")

        final_output = unique_destination(output_folder, safe_output_name(output.name, job.mode))
        shutil.move(str(output), str(final_output))
        shutil.rmtree(attempt_folder, ignore_errors=True)

        update_job(
            job,
            status="complete",
            progress=100,
            message="✓ Descarga completada",
            detail=info.get("title") or final_output.name,
            filePath=str(final_output.resolve()),
            folder=str(final_output.parent.resolve()),
            attempt=attempt,
        )
    except Exception as error:
        LOGGER.exception("Download job %s failed", job.id)
        if attempt_folder is not None:
            shutil.rmtree(attempt_folder, ignore_errors=True)
        update_job(
            job,
            status="error",
            message="Error de descarga",
            detail=str(error),
            error=str(error),
        )


class Handler(BaseHTTPRequestHandler):
    server_version = f"PacheVideoHelper/{VERSION}"

    def log_message(self, format: str, *args) -> None:
        LOGGER.info("HTTP %s", format % args)

    def _origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        allowed = {
            item.strip()
            for item in os.environ.get("PACHEVIDEO_UXP_ORIGINS", "").split(",")
            if item.strip()
        }
        return origin in allowed

    def _host_is_valid(self) -> bool:
        return self.headers.get("Host", "") in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

    def _request_is_authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {SESSION_TOKEN}"
        return bool(SESSION_TOKEN) and secrets.compare_digest(supplied, expected)

    def _require_access(self) -> bool:
        if not self._host_is_valid():
            self.send_json(400, {"error": "Host local no válido"})
            return False
        if not self._origin_is_allowed():
            self.send_json(403, {"error": "Origen no autorizado"})
            return False
        if not self._request_is_authorized():
            self.send_json(401, {"error": "No autorizado"})
            return False
        return True

    def end_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin and self._origin_is_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if not self._host_is_valid():
            self.send_json(400, {"error": "Host local no válido"})
            return
        if not self._origin_is_allowed():
            self.send_json(403, {"error": "Origen no autorizado"})
            return
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        if not self._require_access():
            return
        if self.path == "/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "version": VERSION,
                    "ytDlp": yt_dlp.version.__version__,
                    "ffmpeg": FFMPEG,
                    "outputFolder": str(OUTPUT_FOLDER),
                    "logFile": str(LOG_FILE),
                },
            )
            return

        if self.path.startswith("/downloads/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with jobs_lock:
                job = jobs.get(job_id)
                payload = asdict(job) if job else None
            if payload is None:
                self.send_json(404, {"error": "Descarga inexistente"})
            else:
                self.send_json(200, payload)
            return

        self.send_json(404, {"error": "Ruta inexistente"})

    def do_POST(self) -> None:
        if not self._require_access():
            return
        if self.path not in {"/downloads", "/folders/allow"}:
            self.send_json(404, {"error": "Ruta inexistente"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32768:
                raise ValueError("Cuerpo de solicitud inválido")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/folders/allow":
                requested_folder = str(payload.get("outputFolder") or "").strip()
                if not requested_folder:
                    raise ValueError("Elegí una carpeta de destino")
                folder = allow_output_folder(requested_folder)
                self.send_json(200, {"outputFolder": str(folder)})
                return
            url = str(payload.get("url", "")).strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("La URL no es válida")

            mode = payload.get("mode", "video")
            quality = str(payload.get("quality", "max"))
            audio_kbps = str(payload.get("audioKbps", "320"))
            if mode not in {"video", "audio"}:
                raise ValueError("Modo inválido")
            if quality not in {"max", "2160", "1440", "1080", "720", "480"}:
                raise ValueError("Calidad de video inválida")
            if audio_kbps not in {"320", "256", "192", "128"}:
                raise ValueError("Calidad de audio inválida")

            requested_folder = str(payload.get("outputFolder") or "").strip()
            output_folder = validate_output_folder(requested_folder) if requested_folder else OUTPUT_FOLDER
            if not output_folder_is_allowed(output_folder):
                raise ValueError("Elegí la carpeta de destino desde PacheVideo antes de descargar")
            try:
                output_folder.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise ValueError(f"No se puede usar la carpeta de destino: {error}") from error

            job = Job(
                id=uuid.uuid4().hex,
                url=url,
                mode=mode,
                quality=quality,
                audioKbps=audio_kbps,
                folder=str(output_folder),
            )
            with jobs_lock:
                jobs[job.id] = job
            threading.Thread(target=run_download, args=(job,), daemon=True).start()
            self.send_json(202, {"id": job.id})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})


def main() -> None:
    global SESSION_TOKEN
    configure_logging()
    SESSION_TOKEN = create_session_token()
    if not FFMPEG:
        LOGGER.error("FFmpeg was not found")
        raise SystemExit(
            "No se encontró FFmpeg. Instalalo o definí PACHEVIDEO_FFMPEG con su ruta."
        )
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as error:
        LOGGER.exception("Could not bind %s:%s", HOST, PORT)
        return
    LOGGER.info("PacheVideo Helper %s", VERSION)
    LOGGER.info("Listening on http://%s:%s", HOST, PORT)
    LOGGER.info("Session token: %s", session_token_path())
    LOGGER.info("FFmpeg: %s", FFMPEG)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Closing helper")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
