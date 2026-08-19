"""Standalone desktop client for PacheVideo Helper."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from tkinter import filedialog
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote

import customtkinter as ctk
from PIL import Image

# The desktop executable is frozen from this directory, so imports must stay
# sibling-relative instead of requiring the source repository package layout.
from release import fetch_latest_release, is_newer_release


API_URL = os.environ.get("PACHEVIDEO_API_URL", "http://127.0.0.1:18765")
# Desktop account pairing uses the public API origin directly. The web origin
# is protected by a browser-signature challenge that correctly rejects a
# native Python client before it can receive the one-time pairing response.
CLOUD_API_URL = os.environ.get("PACHEVIDEO_CLOUD_API_URL", "https://api.pachevideo.com/api").rstrip("/")
VERSION = "0.5.8"


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return root / name


def session_token_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "PacheVideo" / "session.token"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PacheVideo" / "session.token"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "PacheVideo" / "session.token"


def desktop_token_path() -> Path:
    return session_token_path().with_name("desktop.token")


def read_desktop_token() -> str:
    try:
        return desktop_token_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_desktop_token(token: str) -> None:
    path = desktop_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def helper_token() -> str:
    token = session_token_path().read_text(encoding="utf-8").strip()
    if not token:
        raise ConnectionError("El helper todavía no creó su sesión local")
    return token


def api_json(path: str, payload: dict | None = None, timeout: float = 8) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{API_URL}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {helper_token()}",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            message = json.loads(error.read().decode("utf-8")).get("error")
        except Exception:
            message = None
        raise RuntimeError(message or f"Error HTTP {error.code}") from error
    except URLError as error:
        raise ConnectionError(str(error.reason)) from error


class CloudError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def cloud_json(path: str, token: str, payload: dict | None = None, timeout: float = 10) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{CLOUD_API_URL}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"PacheVideoDesktop/{VERSION}",
            "Authorization": f"Bearer {token}",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            message = json.loads(error.read().decode("utf-8")).get("detail") or "Error de cuenta"
        except Exception:
            message = f"Error HTTP {error.code}"
        raise CloudError(error.code, message) from error
    except URLError as error:
        raise ConnectionError(str(error.reason)) from error


class PacheVideoApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"PacheVideo {VERSION}")
        self.geometry("540x760")
        self.minsize(460, 560)
        self.configure(fg_color="#090909")
        if sys.platform == "win32":
            windows_icon = resource_path("PacheVideo.ico")
            if windows_icon.is_file():
                self.iconbitmap(str(windows_icon))

        self.events: queue.Queue[callable] = queue.Queue()
        self.current_folder: str | None = None
        self.downloading = False
        self.update_url: str | None = None
        self.update_checked = False
        self.helper_online = False
        self.account: dict | None = None
        self.cloud_token = read_desktop_token()
        self.pairing_in_progress = False
        self.auto_pair_attempted = False

        self._build_ui()
        self.after(50, self._drain_events)
        self.after(150, self.connect_helper)
        self.after(300, self.refresh_account)
        self.after(900, self.auto_connect_account)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(
            self,
            fg_color="#090909",
            corner_radius=0,
            scrollbar_button_color="#4b4b4b",
            scrollbar_button_hover_color="#8f1bd4",
        )
        content.grid(row=0, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(24, 12), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        logo = Image.open(resource_path("logo.png"))
        self.logo_image = ctk.CTkImage(light_image=logo, dark_image=logo, size=(52, 52))
        ctk.CTkLabel(header, text="", image=self.logo_image).grid(row=0, column=0, rowspan=2, padx=(0, 14))
        ctk.CTkLabel(
            header,
            text="PACHEVIDEO",
            text_color="#d4af37",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(
            header,
            text="Video Downloader",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=1, column=1, sticky="nw")
        self.helper_dot = ctk.CTkLabel(header, text="●", text_color="#e94560", font=ctk.CTkFont(size=18))
        self.helper_dot.grid(row=0, column=2, rowspan=2, padx=(12, 0))

        account_card = ctk.CTkFrame(content, fg_color="#151515", corner_radius=16, border_width=1, border_color="#292929")
        account_card.grid(row=1, column=0, padx=28, pady=(0, 10), sticky="ew")
        account_card.grid_columnconfigure(0, weight=1)
        self.account_title = ctk.CTkLabel(account_card, text="Cuenta no conectada", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.account_title.grid(row=0, column=0, padx=18, pady=(15, 3), sticky="ew")
        self.account_detail = ctk.CTkLabel(
            account_card,
            text="Conectá tu cuenta Video Pro para habilitar descargas sin límite de velocidad.",
            text_color="#a7a7a7", anchor="w", justify="left", wraplength=360,
        )
        self.account_detail.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.account_button = ctk.CTkButton(
            account_card, text="Conectar cuenta", width=145, fg_color="#d4af37", text_color="#15110a",
            hover_color="#e6c65b", command=self.connect_account,
        )
        self.account_button.grid(row=0, column=1, rowspan=2, padx=(8, 18), pady=14, sticky="e")

        form = ctk.CTkFrame(content, fg_color="#151515", corner_radius=16, border_width=1, border_color="#292929")
        form.grid(row=2, column=0, padx=28, pady=10, sticky="ew")
        form.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(form, text="URL del video", anchor="w").grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 6), sticky="ew"
        )
        self.url_box = ctk.CTkTextbox(
            form,
            height=92,
            fg_color="#0e0e0e",
            border_width=1,
            border_color="#353535",
            corner_radius=10,
            wrap="word",
        )
        self.url_box.grid(row=1, column=0, columnspan=2, padx=18, sticky="ew")
        self.paste_button = ctk.CTkButton(
            form,
            text="Pegar URL",
            width=100,
            fg_color="#242424",
            hover_color="#333333",
            command=self.paste_url,
        )
        self.paste_button.grid(row=2, column=1, padx=18, pady=(8, 14), sticky="e")

        ctk.CTkLabel(form, text="Carpeta de destino", anchor="w").grid(
            row=3, column=0, columnspan=2, padx=18, pady=(0, 6), sticky="ew"
        )
        folder_row = ctk.CTkFrame(form, fg_color="transparent")
        folder_row.grid(row=4, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="ew")
        folder_row.grid_columnconfigure(0, weight=1)
        self.folder_entry = ctk.CTkEntry(
            folder_row,
            placeholder_text="~/Downloads/PacheVideo",
            fg_color="#0e0e0e",
            border_color="#353535",
        )
        self.folder_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            folder_row,
            text="Elegir…",
            width=92,
            fg_color="#242424",
            hover_color="#333333",
            command=self.choose_folder,
        ).grid(row=0, column=1)

        ctk.CTkLabel(form, text="Formato", anchor="w").grid(row=5, column=0, padx=(18, 8), pady=(0, 6), sticky="ew")
        ctk.CTkLabel(form, text="Calidad", anchor="w").grid(row=5, column=1, padx=(8, 18), pady=(0, 6), sticky="ew")
        self.mode_menu = ctk.CTkOptionMenu(
            form,
            values=["Video · MP4", "Audio · MP3"],
            fg_color="#7016a8",
            button_color="#8c1bd1",
            command=self.mode_changed,
        )
        self.mode_menu.grid(row=6, column=0, padx=(18, 8), sticky="ew")
        self.quality_menu = ctk.CTkOptionMenu(
            form,
            values=["Máxima", "2160p", "1440p", "1080p", "720p", "480p"],
            fg_color="#242424",
            button_color="#343434",
        )
        self.quality_menu.grid(row=6, column=1, padx=(8, 18), sticky="ew")

        self.download_button = ctk.CTkButton(
            form,
            text="Descargar",
            height=46,
            corner_radius=10,
            fg_color="#8f1bd4",
            hover_color="#a72aeb",
            font=ctk.CTkFont(size=15, weight="bold"),
            state="disabled",
            command=self.start_download,
        )
        self.download_button.grid(row=7, column=0, columnspan=2, padx=18, pady=18, sticky="ew")
        self.speed_note = ctk.CTkLabel(
            form,
            text="Plan gratis: hasta 2 MB/s. Con Video Pro descargás a máxima velocidad.",
            text_color="#b8a45a", justify="center", wraplength=420,
        )
        self.speed_note.grid(row=8, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")

        progress = ctk.CTkFrame(content, fg_color="#151515", corner_radius=16, border_width=1, border_color="#292929")
        progress.grid(row=3, column=0, padx=28, pady=10, sticky="ew")
        progress.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            progress,
            text="Conectando con PacheVideo Helper…",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.status_label.grid(row=0, column=0, padx=18, pady=(18, 6), sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(progress, progress_color="#b63bf3", fg_color="#303030")
        self.progress_bar.grid(row=1, column=0, padx=18, sticky="ew")
        self.progress_bar.set(0)
        self.detail_label = ctk.CTkLabel(
            progress,
            text="El Helper procesa yt-dlp y FFmpeg en segundo plano.",
            text_color="#929292",
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.detail_label.grid(row=2, column=0, padx=18, pady=(8, 12), sticky="ew")
        self.folder_button = ctk.CTkButton(
            progress,
            text="Abrir carpeta de descargas",
            fg_color="#242424",
            hover_color="#333333",
            state="disabled",
            command=self.open_folder,
        )
        self.folder_button.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew")

        history_card = ctk.CTkFrame(content, fg_color="#151515", corner_radius=16, border_width=1, border_color="#292929")
        history_card.grid(row=4, column=0, padx=28, pady=10, sticky="ew")
        history_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(history_card, text="Cola e historial local", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 3), sticky="ew"
        )
        self.queue_label = ctk.CTkLabel(
            history_card, text="Todavía no hay descargas en esta computadora.", text_color="#929292", anchor="w",
            justify="left", wraplength=430,
        )
        self.queue_label.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")

        footer = ctk.CTkFrame(content, fg_color="transparent")
        footer.grid(row=5, column=0, padx=28, pady=(8, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, text=f"PacheVideo {VERSION}", text_color="#626262").grid(row=0, column=0, sticky="w")
        self.update_button = ctk.CTkButton(
            footer,
            text="Buscar actualización",
            width=156,
            fg_color="transparent",
            text_color="#d4af37",
            hover_color="#2b2412",
            command=self.manual_update_check,
        )
        self.update_button.grid(row=0, column=1, padx=(0, 10), sticky="e")
        ctk.CTkButton(
            footer,
            text="Reconectar",
            width=90,
            fg_color="transparent",
            text_color="#bd74df",
            hover_color="#1d1d1d",
            command=self.connect_helper,
        ).grid(row=0, column=2, sticky="e")

    def _post(self, callback) -> None:
        self.events.put(callback)

    def _drain_events(self) -> None:
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        self.after(50, self._drain_events)

    def _run(self, target) -> None:
        threading.Thread(target=target, daemon=True).start()

    def set_status(self, title: str, detail: str = "", progress: float | None = None) -> None:
        self.status_label.configure(text=title)
        if detail:
            self.detail_label.configure(text=detail)
        if progress is not None:
            self.progress_bar.set(max(0, min(1, progress / 100)))

    def set_online(self, online: bool) -> None:
        self.helper_online = online
        self.helper_dot.configure(text_color="#4caf50" if online else "#e94560")
        if not self.downloading:
            pro = bool(self.account and self.account.get("plan") == "pro")
            self.download_button.configure(state="normal" if online and pro else "disabled")

    def refresh_account(self) -> None:
        if not self.cloud_token:
            self._post(lambda: self.show_account(None))
            return

        def worker() -> None:
            try:
                account = cloud_json("/desktop/account", self.cloud_token, timeout=8)
                self._post(lambda: self.show_account(account))
            except CloudError as error:
                if error.status in {401, 403}:
                    try:
                        desktop_token_path().unlink(missing_ok=True)
                    except OSError:
                        pass
                    self.cloud_token = ""
                    self._post(lambda: self.show_account(None, "Volvé a conectar tu cuenta para usar la app."))
                else:
                    self._post(lambda: self.show_account(None, "No pudimos verificar tu cuenta. Intentá reconectar."))
            except Exception:
                self._post(lambda: self.show_account(None, "No pudimos verificar tu cuenta. Intentá reconectar."))

        self._run(worker)

    def show_account(self, account: dict | None, message: str = "") -> None:
        self.account = account
        pro = bool(account and account.get("plan") == "pro")
        if pro:
            email = str(account.get("email") or "Cuenta conectada")
            self.account_title.configure(text="VIDEO PRO ACTIVO", text_color="#d4af37")
            self.account_detail.configure(text=f"{email} · Máxima velocidad, historial y descargas locales habilitadas.")
            self.account_button.configure(text="Cuenta conectada", state="disabled", fg_color="#2b2412", text_color="#d4af37")
            self.speed_note.configure(text="Video Pro activo: máxima velocidad local habilitada.", text_color="#d4af37")
        else:
            self.account_title.configure(text="Cuenta Video Pro requerida", text_color="#f0f0f0")
            self.account_detail.configure(text=message or "Conectá tu cuenta Video Pro para habilitar descargas locales. Plan gratis: hasta 2 MB/s en la web.")
            self.account_button.configure(text="Conectar cuenta", state="normal", fg_color="#d4af37", text_color="#15110a")
            self.speed_note.configure(text="Plan gratis: hasta 2 MB/s. Con Video Pro descargás a máxima velocidad.", text_color="#b8a45a")
        self.set_online(self.helper_online)

    def connect_account(self) -> None:
        if self.pairing_in_progress:
            return
        code = "pvpair_" + secrets.token_urlsafe(32)
        self.pairing_in_progress = True
        self.account_button.configure(text="Esperando…", state="disabled")
        self.account_detail.configure(text="Se abrió PacheVideo en el navegador. Iniciá sesión y confirmá la conexión; la app se habilitará sola.")
        webbrowser.open(f"https://pachevideo.com/app?desktopPairing={quote(code)}")

        def worker() -> None:
            deadline = time.monotonic() + 310
            try:
                while time.monotonic() < deadline:
                    try:
                        paired = cloud_json(f"/desktop/pair?code={quote(code)}", "", timeout=8)
                        token = str(paired.get("accessToken") or "")
                        account = paired.get("account")
                        if not token or not isinstance(account, dict):
                            raise RuntimeError("La conexión devolvió una respuesta inválida")
                        save_desktop_token(token)
                        self.cloud_token = token
                        self._post(lambda account=account: self.show_account(account))
                        self._post(lambda: self.set_status("Cuenta conectada", "Video Pro listo para descargar en esta computadora.", 0))
                        return
                    except CloudError as error:
                        if error.status not in {404, 409}:
                            raise
                    time.sleep(1)
                self._post(lambda: self.show_account(None, "La conexión venció. Tocá Conectar cuenta para intentarlo de nuevo."))
            except Exception as error:
                self._post(lambda: self.show_account(None, str(error)))
            finally:
                self.pairing_in_progress = False

        self._run(worker)

    def auto_connect_account(self) -> None:
        """Use the browser's existing PacheVideo session when available.

        Browsers intentionally do not expose their cookies to desktop programs.
        Opening the same-origin pairing page keeps that boundary intact while
        completing immediately for a user who is already signed in.
        """
        if self.auto_pair_attempted or self.pairing_in_progress or (self.account and self.account.get("plan") == "pro"):
            return
        self.auto_pair_attempted = True
        self.connect_account()

    def refresh_queue(self) -> None:
        def worker() -> None:
            try:
                payload = api_json("/downloads", timeout=5)
                items = payload.get("items") if isinstance(payload, dict) else []
                self._post(lambda: self.show_queue(items if isinstance(items, list) else []))
            except Exception:
                return
        self._run(worker)

    def show_queue(self, items: list[dict]) -> None:
        if not items:
            self.queue_label.configure(text="Todavía no hay descargas en esta computadora.")
            return
        rows: list[str] = []
        for item in items[:6]:
            status = str(item.get("status") or "en cola")
            progress = int(float(item.get("progress") or 0))
            name = str(item.get("url") or "Archivo").split("?", 1)[0][-56:]
            rows.append(f"{status.upper()} · {progress}% · {name}")
        self.queue_label.configure(text="\n".join(rows))

    def connect_helper(self) -> None:
        self.download_button.configure(state="disabled")
        self.set_status("Conectando con PacheVideo Helper…", "Puerto local 18765", 0)

        def worker() -> None:
            last_error: Exception | None = None
            for attempt in range(18):
                try:
                    health = api_json("/health", timeout=2)
                    self._post(
                        lambda: (
                            self.set_online(True),
                            self.set_status(
                                "Listo para descargar",
                                f"Descargas: {health.get('outputFolder', '')}",
                                0,
                            ),
                            self.set_default_folder(health.get("outputFolder", "")),
                            self.refresh_queue(),
                        )
                    )
                    self._run(self.check_for_update)
                    return
                except Exception as error:
                    last_error = error
                    if attempt == 0:
                        self.start_helper()
                    time.sleep(0.35)
            message = str(last_error) if last_error else "Sin respuesta"
            self._post(
                lambda: (
                    self.set_online(False),
                    self.set_status("Helper desconectado", message, 0),
                )
            )

        self._run(worker)

    def check_for_update(self, manual: bool = False) -> None:
        if self.update_checked and not manual:
            return
        self.update_checked = True
        if manual:
            self._post(lambda: self.update_button.configure(text="Buscando…", state="disabled"))
        try:
            release = fetch_latest_release()
            if not release:
                if manual:
                    self._post(lambda: self.update_button.configure(text="No pudimos comprobar", state="normal", text_color="#e9a2ae"))
                return
            version, url = release
            if not is_newer_release(version, VERSION):
                if manual:
                    self._post(lambda: self.update_button.configure(text="✓ Estás al día", state="normal", text_color="#7be39a"))
                return
            self.update_url = url
            self._post(lambda: self.update_button.configure(text="Descargar actualización", state="normal", text_color="#d4af37", command=self.open_update))
        except Exception:
            # An update check must never affect downloading or startup.
            if manual:
                self._post(lambda: self.update_button.configure(text="No pudimos comprobar", state="normal", text_color="#e9a2ae"))
            return

    def manual_update_check(self) -> None:
        self._run(lambda: self.check_for_update(manual=True))

    def open_update(self) -> None:
        if self.update_url:
            webbrowser.open(self.update_url)

    def start_helper(self) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(
                    ["open", "-gja", "PacheVideo Helper"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return

            if sys.platform == "win32":
                executable_dir = Path(sys.executable).resolve().parent
                candidates = [
                    executable_dir / "PacheVideoHelper.exe",
                    executable_dir.parent / "PacheVideoHelper" / "PacheVideoHelper.exe",
                ]
                if not getattr(sys, "frozen", False):
                    candidates.insert(0, Path(__file__).with_name("server.py"))

                for candidate in candidates:
                    if not candidate.is_file():
                        continue
                    command = [str(candidate)]
                    if candidate.suffix.lower() == ".py":
                        command.insert(0, sys.executable)
                    subprocess.Popen(
                        command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        creationflags=(
                            getattr(subprocess, "CREATE_NO_WINDOW", 0)
                            | getattr(subprocess, "DETACHED_PROCESS", 0)
                        ),
                        close_fds=True,
                    )
        except OSError:
            pass

    def paste_url(self) -> None:
        try:
            value = self.clipboard_get().strip()
        except Exception:
            return
        self.url_box.delete("1.0", "end")
        self.url_box.insert("1.0", value)

    def set_default_folder(self, folder: str) -> None:
        if folder and not self.folder_entry.get().strip():
            self.folder_entry.insert(0, folder)

    def choose_folder(self) -> None:
        initial = self.folder_entry.get().strip() or str(Path.home() / "Downloads")
        selected = filedialog.askdirectory(parent=self, initialdir=initial, mustexist=False)
        if selected:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, selected)

    def mode_changed(self, selected: str) -> None:
        if selected.startswith("Audio"):
            values = ["320 kbps", "256 kbps", "192 kbps", "128 kbps"]
        else:
            values = ["Máxima", "2160p", "1440p", "1080p", "720p", "480p"]
        self.quality_menu.configure(values=values)
        self.quality_menu.set(values[0])

    def start_download(self) -> None:
        if not self.account or self.account.get("plan") != "pro":
            self.set_status("Conectá una cuenta Video Pro", "La app de escritorio se habilita con tu cuenta Pro.", 0)
            self.connect_account()
            return
        url = self.url_box.get("1.0", "end").strip()
        if not url.startswith(("http://", "https://")):
            self.set_status("Ingresá una URL válida", "Debe comenzar con http:// o https://", 0)
            return

        audio = self.mode_menu.get().startswith("Audio")
        quality_text = self.quality_menu.get()
        payload = {
            "url": url,
            "mode": "audio" if audio else "video",
            "quality": "max" if audio or quality_text == "Máxima" else quality_text.replace("p", ""),
            "audioKbps": quality_text.replace(" kbps", "") if audio else "320",
            "outputFolder": self.folder_entry.get().strip(),
        }
        self.downloading = True
        self.current_folder = None
        self.download_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        self.set_status("Iniciando descarga…", "Preparando yt-dlp", 1)

        def worker() -> None:
            try:
                api_json("/folders/allow", {"outputFolder": payload["outputFolder"]}, timeout=8)
                create_errors = 0
                while True:
                    try:
                        created = api_json("/downloads", payload, timeout=15)
                        break
                    except ConnectionError:
                        create_errors = min(30, create_errors + 1)
                        retry_in = min(15, 2 ** min(create_errors - 1, 4))
                        self._post(
                            lambda: self.set_status(
                                "Preparando tu descarga…",
                                "No hace falta volver a tocar el botón.",
                            )
                        )
                        time.sleep(retry_in)
                job_id = created["id"]
                self.refresh_queue()
                poll_errors = 0
                while True:
                    try:
                        job = api_json(f"/downloads/{job_id}", timeout=8)
                        poll_errors = 0
                    except ConnectionError:
                        poll_errors = min(30, poll_errors + 1)
                        retry_in = min(15, 2 ** min(poll_errors - 1, 4))
                        self._post(
                            lambda: self.set_status(
                                "Seguimos preparando tu archivo…",
                                "La conexión se recupera automáticamente.",
                            )
                        )
                        time.sleep(retry_in)
                        continue
                    self._post(
                        lambda job=job: (
                            self.set_status(
                                job.get("message", "Descargando…"),
                                job.get("detail", ""),
                                float(job.get("progress", 0)),
                            ),
                            self.refresh_queue(),
                        )
                    )
                    if job.get("status") == "complete":
                        self.current_folder = job.get("folder")
                        self._post(self.download_complete)
                        return
                    if job.get("status") == "error":
                        raise RuntimeError(job.get("error") or job.get("detail") or "Error de descarga")
                    time.sleep(0.65)
            except Exception as error:
                message = str(error)
                self._post(lambda: self.download_failed(message))

        self._run(worker)

    def download_complete(self) -> None:
        self.downloading = False
        self.set_online(True)
        self.download_button.configure(state="normal")
        self.folder_button.configure(state="normal" if self.current_folder else "disabled")
        self.set_status("Descarga completada", self.current_folder or "Archivo guardado", 100)
        self.refresh_queue()

    def download_failed(self, message: str) -> None:
        self.downloading = False
        self.download_button.configure(state="normal")
        self.set_status("No se pudo descargar", message, 0)
        self.refresh_queue()

    def open_folder(self) -> None:
        if not self.current_folder:
            return
        if sys.platform == "win32":
            os.startfile(self.current_folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self.current_folder])
        else:
            subprocess.Popen(["xdg-open", self.current_folder])


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    PacheVideoApp().mainloop()


if __name__ == "__main__":
    main()
