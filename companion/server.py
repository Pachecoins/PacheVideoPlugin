"""Local yt-dlp/FFmpeg companion for the PacheVideo Premiere UXP panel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import uuid
from urllib.parse import urlparse

import yt_dlp


HOST = "127.0.0.1"
PORT = int(os.environ.get("PACHEVIDEO_PORT", "18765"))
OUTPUT_FOLDER = Path(os.environ.get("PACHEVIDEO_OUTPUT", "~/Downloads/PacheVideo")).expanduser().resolve()
VERSION = "0.2.1"


def find_ffmpeg() -> str | None:
    configured = os.environ.get("PACHEVIDEO_FFMPEG")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend(
            [
                bundle_root / "ffmpeg",
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
        f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
    )


def locate_output(ydl: yt_dlp.YoutubeDL, info: dict, mode: str) -> Path:
    prepared = Path(ydl.prepare_filename(info))
    expected = prepared.with_suffix(".mp3" if mode == "audio" else ".mp4")
    if expected.exists():
        return expected
    if prepared.exists():
        return prepared

    title_prefix = prepared.stem
    matches = sorted(
        OUTPUT_FOLDER.glob(f"{title_prefix}.*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    raise FileNotFoundError("yt-dlp terminó, pero no se encontró el archivo generado.")


def run_download(job: Job) -> None:
    try:
        update_job(job, status="downloading", progress=1, message="Analizando el video…")

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

        options = {
            "format": format_selector(job.mode, job.quality),
            "outtmpl": str(OUTPUT_FOLDER / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "postprocessors": postprocessors,
        }
        if job.mode == "video":
            options["merge_output_format"] = "mp4"
        if FFMPEG:
            options["ffmpeg_location"] = FFMPEG

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(job.url, download=True)
            output = locate_output(ydl, info, job.mode)

        update_job(
            job,
            status="complete",
            progress=100,
            message="✓ Descarga completada",
            detail=info.get("title") or output.name,
            filePath=str(output.resolve()),
            folder=str(output.parent.resolve()),
        )
    except Exception as error:
        update_job(
            job,
            status="error",
            message="Error de descarga",
            detail=str(error),
            error=str(error),
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "PacheVideoHelper/0.1"

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "version": VERSION,
                    "ytDlp": yt_dlp.version.__version__,
                    "ffmpeg": FFMPEG,
                    "outputFolder": str(OUTPUT_FOLDER),
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
        if self.path != "/downloads":
            self.send_json(404, {"error": "Ruta inexistente"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32768:
                raise ValueError("Cuerpo de solicitud inválido")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
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

            job = Job(
                id=uuid.uuid4().hex,
                url=url,
                mode=mode,
                quality=quality,
                audioKbps=audio_kbps,
            )
            with jobs_lock:
                jobs[job.id] = job
            threading.Thread(target=run_download, args=(job,), daemon=True).start()
            self.send_json(202, {"id": job.id})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})


def main() -> None:
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    if not FFMPEG:
        raise SystemExit(
            "No se encontró FFmpeg. Instalalo o definí PACHEVIDEO_FFMPEG con su ruta."
        )
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as error:
        print(f"No se pudo abrir {HOST}:{PORT}: {error}")
        return
    print(f"PacheVideo Helper {VERSION}")
    print(f"Escuchando en http://{HOST}:{PORT}")
    print(f"Descargas: {OUTPUT_FOLDER}")
    print(f"FFmpeg: {FFMPEG}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando helper…")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
