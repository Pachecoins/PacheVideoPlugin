from __future__ import annotations

import socket
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from server.app import main as backend
from server.app.main import (
    compatibility_selector,
    download_error_category,
    enforce_plan_limits,
    ensure_mobile_compatible_mp4,
    format_selector,
    inspect_media_codecs,
    is_retryable_download_error,
    retry_delay_seconds,
    validate_public_url,
)
import yt_dlp


class SecurityTests(unittest.TestCase):
    @unittest.skipUnless(backend.FFMPEG, "FFmpeg no está disponible")
    def test_mpeg_video_is_normalized_to_h264_aac_mp4(self) -> None:
        with TemporaryDirectory() as temp:
            source = Path(temp) / "instagram-mpeg.mp4"
            subprocess.run(
                [
                    str(backend.FFMPEG),
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=64x64:rate=2",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:sample_rate=44100",
                    "-t",
                    "1",
                    "-c:v",
                    "mpeg4",
                    "-c:a",
                    "aac",
                    str(source),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = ensure_mobile_compatible_mp4(source, backend.FFMPEG)
            codecs = inspect_media_codecs(output, backend.FFMPEG)

        self.assertEqual(output.suffix, ".mp4")
        self.assertEqual(codecs, ("h264", "aac"))

    @patch("server.app.main.subprocess.run")
    def test_media_probe_detects_incompatible_instagram_video(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stderr="Stream #0:0: Video: vp9, yuv420p\nStream #0:1: Audio: aac (LC), 44100 Hz",
        )
        self.assertEqual(inspect_media_codecs(Path("instagram.mp4"), "ffmpeg"), ("vp9", "aac"))

    def test_rejects_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "credenciales"):
            validate_public_url("https://user:secret@example.com/video")

    @patch("server.app.main.socket.getaddrinfo")
    def test_rejects_private_addresses(self, getaddrinfo) -> None:
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        with self.assertRaisesRegex(ValueError, "red no permitida"):
            validate_public_url("https://example.com/video")

    @patch("server.app.main.socket.getaddrinfo")
    def test_ssrf_validation_uses_http_default_port(self, getaddrinfo) -> None:
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))
        ]
        validate_public_url("http://example.com/video")
        self.assertEqual(getaddrinfo.call_args.args[1], 80)

    def test_forwarded_ip_requires_the_private_proxy_token(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/account",
                "headers": [(b"x-forwarded-for", b"8.8.8.8")],
                "client": ("203.0.113.1", 1234),
            }
        )
        with patch.object(backend, "INTERNAL_PROXY_TOKEN", "proxy-secret"):
            with self.assertRaises(backend.HTTPException) as blocked:
                backend.request_client_ip(request)
            self.assertEqual(blocked.exception.status_code, 403)

            trusted = backend.Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/api/account",
                    "headers": [
                        (b"x-forwarded-for", b"8.8.8.8"),
                        (b"x-pachevideo-internal-token", b"proxy-secret"),
                    ],
                    "client": ("203.0.113.1", 1234),
                }
            )
            self.assertEqual(backend.request_client_ip(trusted), "8.8.8.8")

    def test_format_selector_has_direct_fallback(self) -> None:
        self.assertTrue(format_selector("video", "1080").endswith("/best"))
        self.assertIn("bestaudio[ext=webm]", format_selector("video", "1080"))
        self.assertEqual(format_selector("audio", "max"), "bestaudio[ext=webm]/bestaudio/best")

    def test_compatibility_selector_uses_single_file_stream(self) -> None:
        self.assertEqual(
            compatibility_selector("video", "1080"),
            "best[ext=mp4][height<=1080]/best[height<=1080]/best",
        )
        self.assertEqual(compatibility_selector("audio", "max"), "best[ext=mp4]/best")

    def test_free_plan_is_capped_at_1080p(self) -> None:
        enforce_plan_limits("video", "1080", "free")
        with self.assertRaisesRegex(ValueError, "Video Pro"):
            enforce_plan_limits("video", "1440", "free")
        with self.assertRaisesRegex(ValueError, "Video Pro"):
            enforce_plan_limits("video", "max", "free")

    def test_pro_plan_unlocks_all_video_qualities(self) -> None:
        for quality in ("1440", "2160", "max"):
            enforce_plan_limits("video", quality, "pro")

    def test_audio_320_is_available_on_free(self) -> None:
        enforce_plan_limits("audio", "max", "free")

    def test_pro_is_not_unlocked_by_a_public_access_code(self) -> None:
        self.assertFalse(hasattr(backend, "PRO_ACCESS_KEYS"))

    def test_retry_classifier_separates_transient_and_permanent_errors(self) -> None:
        self.assertTrue(is_retryable_download_error(yt_dlp.utils.DownloadError("HTTP Error 503")))
        self.assertFalse(is_retryable_download_error(yt_dlp.utils.DownloadError("Private video")))
        self.assertFalse(is_retryable_download_error(yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")))
        self.assertIn("disponible", backend.public_download_error(
            yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")
        ))

    def test_download_errors_use_closed_public_catalog(self) -> None:
        cases = {
            "Unsupported URL: https://extractor.example/internal": "fuente_no_soportada",
            "Private video requires login": "contenido_privado",
            "Video unavailable": "contenido_no_disponible",
            "File is larger than max filesize": "limite_de_tamano",
            "El contenido supera el límite de 60 minutos": "limite_de_duracion",
            "HTTP Error 503: https://cdn.internal.example/file": "error_temporal",
            "Extractor /srv/private failed": "error_desconocido",
        }
        for raw, category in cases.items():
            error = yt_dlp.utils.DownloadError(raw)
            public = backend.public_download_error(error)
            self.assertEqual(download_error_category(error), category)
            self.assertEqual(public, backend.DOWNLOAD_ERROR_MESSAGES[category])
            self.assertNotIn("https://", public)
            self.assertNotIn("/srv/", public)

    def test_public_job_never_returns_stored_provider_diagnostic(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
            ):
                backend.initialize_database()
                with backend.database() as connection:
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            id, source_url, mode, quality, audio_kbps, status, progress, message, detail,
                            token_hash, error, created_at, expires_at
                        ) VALUES (?, ?, 'video', '1080', '320', 'error', 0, ?, ?, ?, ?, 0, 9999999999)
                        """,
                        (
                            "private-error",
                            "https://example.com/video",
                            "No pudimos preparar el archivo",
                            backend.DOWNLOAD_ERROR_MESSAGES["error_desconocido"],
                            "token",
                            "yt-dlp /srv/pachevideo/jobs/secret https://cdn.internal.example/file",
                        ),
                    )
                public = backend.public_job(backend.get_job("private-error"))

        self.assertEqual(public["error"], backend.DOWNLOAD_ERROR_MESSAGES["error_desconocido"])
        self.assertNotIn("/srv/", str(public))
        self.assertNotIn("cdn.internal", str(public))

    def test_retry_delay_uses_exponential_backoff(self) -> None:
        with (
            patch.object(backend, "RETRY_BASE_SECONDS", 1.5),
            patch.object(backend, "RETRY_MAX_SECONDS", 20),
        ):
            self.assertEqual([retry_delay_seconds(value) for value in (1, 2, 3)], [1.5, 3.0, 6.0])
            self.assertEqual(retry_delay_seconds(20), 20)

    def test_global_active_job_capacity_rejects_a_burst(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "MAX_ACTIVE_JOBS", 1),
            ):
                backend.initialize_database()
                with backend.database() as connection:
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            id, source_url, mode, quality, audio_kbps, status, progress,
                            message, token_hash, created_at, expires_at
                        ) VALUES ('busy', 'https://example.com/v', 'video', '1080', '320', 'queued', 0,
                                  'En cola', 'token-hash', 0, 9999999999)
                        """
                    )
                with self.assertRaises(backend.HTTPException) as blocked:
                    backend.enforce_active_job_capacity()

        self.assertEqual(blocked.exception.status_code, 503)


class DownloadRetryTests(unittest.TestCase):
    def insert_job(self, job_id: str) -> None:
        with backend.database() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, source_url, mode, quality, audio_kbps, status, progress,
                    message, token_hash, created_at, expires_at
                ) VALUES (?, ?, 'video', '1080', '320', 'queued', 0, 'En cola', ?, 0, 9999999999)
                """,
                (job_id, "https://example.com/video", "token-hash"),
            )

    def test_download_recovers_after_transient_errors(self) -> None:
        class FakeDownloader:
            calls = 0
            formats: list[str] = []

            def __init__(self, options):
                self.options = options
                self.__class__.formats.append(str(options["format"]))

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def extract_info(self, _url, download=True):
                self.__class__.calls += 1
                if self.__class__.calls < 3:
                    raise yt_dlp.utils.DownloadError("HTTP Error 503: temporarily unavailable")
                target = Path(str(self.options["outtmpl"])).parent / "resultado.mp4"
                target.write_bytes(b"video")
                return {"title": "Resultado"}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "DOWNLOAD_ATTEMPTS", 3),
                patch.object(backend, "RETRY_BASE_SECONDS", 0),
                patch.object(backend.yt_dlp, "YoutubeDL", FakeDownloader),
                patch.object(backend, "ensure_mobile_compatible_mp4", side_effect=lambda path, _ffmpeg: path),
            ):
                backend.initialize_database()
                self.insert_job("recoverable")
                backend.run_download("recoverable", "https://example.com/video", "video", "1080", "320")
                row = backend.get_job("recoverable")

        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["attempt"], 3)
        self.assertEqual(FakeDownloader.calls, 3)
        self.assertEqual(FakeDownloader.formats[1], compatibility_selector("video", "1080"))

    def test_download_stops_immediately_for_permanent_error(self) -> None:
        class FakeDownloader:
            calls = 0

            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def extract_info(self, _url, download=True):
                self.__class__.calls += 1
                raise yt_dlp.utils.DownloadError("Private video")

        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "DOWNLOAD_ATTEMPTS", 3),
                patch.object(backend, "RETRY_BASE_SECONDS", 0),
                patch.object(backend.yt_dlp, "YoutubeDL", FakeDownloader),
                patch.object(backend, "ensure_mobile_compatible_mp4", side_effect=lambda path, _ffmpeg: path),
            ):
                backend.initialize_database()
                self.insert_job("permanent")
                backend.run_download("permanent", "https://example.com/video", "video", "1080", "320")
                row = backend.get_job("permanent")

        self.assertEqual(row["status"], "error")
        self.assertEqual(row["attempt"], 1)
        self.assertEqual(FakeDownloader.calls, 1)

    def test_missing_output_is_retried(self) -> None:
        class FakeDownloader:
            calls = 0

            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def extract_info(self, _url, download=True):
                self.__class__.calls += 1
                if self.__class__.calls == 2:
                    target = Path(str(self.options["outtmpl"])).parent / "recuperado.mp4"
                    target.write_bytes(b"video")
                return {"title": "Recuperado"}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "DOWNLOAD_ATTEMPTS", 3),
                patch.object(backend, "RETRY_BASE_SECONDS", 0),
                patch.object(backend.yt_dlp, "YoutubeDL", FakeDownloader),
                patch.object(backend, "ensure_mobile_compatible_mp4", side_effect=lambda path, _ffmpeg: path),
            ):
                backend.initialize_database()
                self.insert_job("missing-output")
                backend.run_download("missing-output", "https://example.com/video", "video", "1080", "320")
                row = backend.get_job("missing-output")

        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["attempt"], 2)
        self.assertEqual(FakeDownloader.calls, 2)

    def test_pro_uses_priority_options_and_free_has_a_rate_limit(self) -> None:
        free_options: dict[str, object] = {}
        pro_options: dict[str, object] = {}

        class FakeDownloader:
            calls = 0

            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def extract_info(self, _url, download=True):
                self.__class__.calls += 1
                if self.__class__.calls == 1:
                    free_options.update(self.options)
                else:
                    pro_options.update(self.options)
                target = Path(str(self.options["outtmpl"])).parent / f"resultado-{self.__class__.calls}.mp4"
                target.write_bytes(b"video")
                return {"title": "Resultado"}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "FREE_DOWNLOAD_RATE_LIMIT", 2_000_000),
                patch.object(backend, "PRO_CONCURRENT_FRAGMENTS", 4),
                patch.object(backend.yt_dlp, "YoutubeDL", FakeDownloader),
            ):
                backend.initialize_database()
                self.insert_job("free-speed")
                self.insert_job("pro-speed")
                backend.run_download("free-speed", "https://example.com/video", "video", "1080", "320", "free")
                backend.run_download("pro-speed", "https://example.com/video", "video", "1080", "320", "pro")

        self.assertEqual(free_options["ratelimit"], 2_000_000)
        self.assertNotIn("concurrent_fragment_downloads", free_options)
        self.assertEqual(pro_options["concurrent_fragment_downloads"], 4)
        self.assertNotIn("ratelimit", pro_options)

    def test_retries_are_not_exposed_to_the_public_job_status(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
            ):
                backend.initialize_database()
                self.insert_job("hidden-retry")
                backend.update_job(
                    "hidden-retry",
                    status="retrying",
                    message="Reintentando descarga (2/3)…",
                    detail="Intento 2 de 3",
                )
                public = backend.public_job(backend.get_job("hidden-retry"))

        self.assertEqual(public["status"], "downloading")
        self.assertEqual(public["message"], "Preparando tu archivo…")
        self.assertEqual(public["detail"], "")

    def test_incomplete_jobs_resume_after_an_api_restart(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend.executor, "submit") as submit,
            ):
                backend.initialize_database()
                self.insert_job("resume-after-restart")
                backend.update_job("resume-after-restart", status="processing", progress=95)
                backend.recover_incomplete_jobs()
                row = backend.get_job("resume-after-restart")

        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["progress"], 0)
        submit.assert_called_once()


class BillingSessionTests(unittest.TestCase):
    def test_subscription_return_url_accepts_local_preview(self) -> None:
        payload = backend.StartSubscription(returnUrl="http://localhost:3000/cualquier-ruta")
        with patch.object(backend, "MP_BACK_URL", ""):
            result = backend.subscription_back_url(payload)

        self.assertEqual(result, "http://localhost:3000/app")

    def test_subscription_return_url_accepts_cloudflare_preview(self) -> None:
        payload = backend.StartSubscription(returnUrl="https://preview-name.trycloudflare.com/app?from=checkout")
        with patch.object(backend, "MP_BACK_URL", ""):
            result = backend.subscription_back_url(payload)

        self.assertEqual(result, "https://preview-name.trycloudflare.com/app")

    def test_subscription_return_url_rejects_untrusted_dynamic_host(self) -> None:
        payload = backend.StartSubscription(returnUrl="https://example.com/app")
        with (
            patch.object(backend, "MP_BACK_URL", ""),
            self.assertRaises(backend.HTTPException) as blocked,
        ):
            backend.subscription_back_url(payload)

        self.assertEqual(blocked.exception.status_code, 503)

    def test_anonymous_session_is_server_side_and_defaults_to_free(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
            ):
                backend.initialize_database()
                account, token = backend.create_anonymous_account()
                self.assertEqual(account["plan"], "free")
                self.assertEqual(account["free_video_uses"], 0)
                public = backend.account_public(account)
                with backend.database() as connection:
                    saved = connection.execute(
                        "SELECT token_hash, account_id FROM visitor_sessions"
                    ).fetchone()

        self.assertEqual(saved["token_hash"], backend.session_token_hash(token))
        self.assertEqual(saved["account_id"], account["id"])
        self.assertEqual(public["freeVideoLimit"], 0)
        self.assertEqual(public["freeVideosRemaining"], 0)

    def test_rotating_anonymous_cookies_keeps_one_network_identity_without_video_credit(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/account",
                "headers": [(b"user-agent", b"pentest-browser")],
                "client": ("198.51.100.10", 1234),
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
            ):
                backend.initialize_database()
                responses = [backend.account(request) for _ in range(10)]
                payloads = [backend.json.loads(response.body) for response in responses]
                with backend.database() as connection:
                    accounts = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
                    identities = connection.execute("SELECT COUNT(*) FROM network_identities").fetchone()[0]

        self.assertEqual(accounts, 1)
        self.assertEqual(identities, 1)
        self.assertTrue(all(payload["freeVideosRemaining"] == 0 for payload in payloads))

    def test_registering_grants_a_fresh_five_video_quota(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "auth-user-new", "email": "nuevo@example.com"},
                ),
            ):
                backend.initialize_database()
                anonymous, token = backend.create_anonymous_account()
                with backend.database() as connection:
                    connection.execute(
                        "UPDATE accounts SET free_video_uses = 1 WHERE id = ?",
                        (anonymous["id"],),
                    )
                request = backend.Request(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/api/account",
                        "headers": [(b"cookie", f"{backend.SESSION_COOKIE_NAME}={token}".encode())],
                    }
                )
                registered = backend.registered_account_from_request(request)
                public = backend.account_public(registered)
                with backend.database() as connection:
                    old_session = connection.execute(
                        "SELECT 1 FROM visitor_sessions WHERE account_id = ?",
                        (registered["id"],),
                    ).fetchone()

        self.assertEqual(registered["id"], anonymous["id"])
        self.assertEqual(registered["free_video_uses"], 0)
        self.assertEqual(public["freeVideoLimit"], 5)
        self.assertEqual(public["freeVideosRemaining"], 5)
        self.assertIsNone(old_session)

    def test_anonymous_account_must_verify_email_before_video_credit(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "validate_public_url"),
                patch.object(backend, "consume_rate_limit"),
                patch.object(backend.executor, "submit"),
            ):
                backend.initialize_database()
                account, token = backend.create_anonymous_account()
                request = backend.Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/api/jobs",
                        "headers": [(b"cookie", f"{backend.SESSION_COOKIE_NAME}={token}".encode())],
                        "client": ("203.0.113.10", 1234),
                    }
                )
                payload = backend.CreateJob(url="https://example.com/video")
                with self.assertRaises(backend.HTTPException) as blocked:
                    backend.create_job(payload, request)
                with backend.database() as connection:
                    uses = connection.execute(
                        "SELECT free_video_uses FROM accounts WHERE id = ?",
                        (account["id"],),
                    ).fetchone()["free_video_uses"]

        self.assertEqual(blocked.exception.status_code, 403)
        self.assertIn("Registrate gratis", blocked.exception.detail)
        self.assertEqual(uses, 0)

    def test_repeated_creation_request_returns_the_same_job_without_spending_quota_twice(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(backend, "validate_public_url"),
                patch.object(backend, "consume_rate_limit"),
                patch.object(backend.executor, "submit") as submit,
            ):
                backend.initialize_database()
                account, token = backend.create_anonymous_account()
                with backend.database() as connection:
                    connection.execute(
                        "UPDATE accounts SET auth_provider_id = 'idempotent-user', email = 'idempotent@example.com' WHERE id = ?",
                        (account["id"],),
                    )
                request = backend.Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/api/jobs",
                        "headers": [(b"cookie", f"{backend.SESSION_COOKIE_NAME}={token}".encode())],
                        "client": ("203.0.113.12", 1234),
                    }
                )
                payload = backend.CreateJob(
                    url="https://example.com/video",
                    requestId="a" * 32,
                    requestToken="b" * 64,
                )
                first = backend.create_job(payload, request)
                second = backend.create_job(payload, request)
                with backend.database() as connection:
                    uses = connection.execute(
                        "SELECT free_video_uses FROM accounts WHERE id = ?",
                        (account["id"],),
                    ).fetchone()["free_video_uses"]

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["token"], second["token"])
        self.assertEqual(uses, 1)
        submit.assert_called_once()

    def test_server_enforces_five_registered_videos(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/jobs",
                "headers": [(b"authorization", b"Bearer test-token")],
                "client": ("203.0.113.11", 1234),
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "auth-user-five", "email": "cinco@example.com"},
                ),
                patch.object(backend, "validate_public_url"),
                patch.object(backend, "consume_rate_limit"),
                patch.object(backend.executor, "submit"),
            ):
                backend.initialize_database()
                payload = backend.CreateJob(url="https://example.com/video")
                for _ in range(5):
                    backend.create_job(payload, request)
                with self.assertRaises(backend.HTTPException) as blocked:
                    backend.create_job(payload, request)
                account = backend.registered_account_from_request(request)
                public = backend.account_public(account)
                with backend.database() as connection:
                    ledger_count = connection.execute(
                        "SELECT COUNT(*) FROM credit_ledger WHERE account_id = ? AND event = 'video_reserved'",
                        (account["id"],),
                    ).fetchone()[0]

        self.assertEqual(blocked.exception.status_code, 403)
        self.assertIn("5 videos gratis", blocked.exception.detail)
        self.assertEqual(public["freeVideoUses"], 5)
        self.assertEqual(public["freeVideosRemaining"], 0)
        self.assertEqual(ledger_count, 5)

    def test_pro_can_create_a_repeatable_list_of_links(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/jobs/batch",
                "headers": [(b"authorization", b"Bearer pro-token")],
                "client": ("203.0.113.13", 1234),
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "auth-user-pro", "email": "pro@example.com"},
                ),
                patch.object(backend, "validate_public_url"),
                patch.object(backend, "consume_rate_limit"),
                patch.object(backend.executor, "submit") as submit,
            ):
                backend.initialize_database()
                account = backend.registered_account_from_request(request)
                with backend.database() as connection:
                    connection.execute("UPDATE accounts SET plan = 'pro' WHERE id = ?", (account["id"],))
                payload = backend.CreateBatch(
                    urls=["https://youtube.com/watch?v=one", "https://instagram.com/reel/two"],
                    requestId="a" * 32,
                    requestToken="b" * 64,
                )
                first = backend.create_batch(payload, request)
                second = backend.create_batch(payload, request)

        self.assertEqual(first["total"], 2)
        self.assertEqual([job["id"] for job in first["jobs"]], [job["id"] for job in second["jobs"]])
        self.assertEqual([job["token"] for job in first["jobs"]], [job["token"] for job in second["jobs"]])
        self.assertEqual(submit.call_count, 2)

    def test_free_account_cannot_create_a_list_of_links(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/jobs/batch",
                "headers": [(b"authorization", b"Bearer free-token")],
                "client": ("203.0.113.14", 1234),
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "auth-user-free", "email": "free@example.com"},
                ),
                patch.object(backend, "consume_rate_limit"),
            ):
                backend.initialize_database()
                payload = backend.CreateBatch(urls=["https://youtube.com/watch?v=one"])
                with self.assertRaises(backend.HTTPException) as blocked:
                    backend.create_batch(payload, request)

        self.assertEqual(blocked.exception.status_code, 403)
        self.assertIn("Video Pro", blocked.exception.detail)

    def test_authenticated_email_maps_to_a_stable_account(self) -> None:
        request = backend.Request(
            {"type": "http", "method": "GET", "path": "/api/account", "headers": []}
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "auth-user-1", "email": "cliente@example.com"},
                ),
            ):
                backend.initialize_database()
                first = backend.registered_account_from_request(request)
                second = backend.registered_account_from_request(request)

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["email"], "cliente@example.com")
        self.assertEqual(first["plan"], "free")

    def test_launch_gift_code_grants_permanent_pro_once(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/gifts/redeem",
                "headers": [(b"authorization", b"Bearer gift-token")],
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "gift-recipient", "email": "regalo@example.com"},
                ),
            ):
                backend.initialize_database()
                redeemed = backend.redeem_gift_code(
                    backend.RedeemGiftCode(code="PV-GIFT-66A07F2701"), request
                )
                with self.assertRaises(backend.HTTPException) as repeated:
                    backend.redeem_gift_code(
                        backend.RedeemGiftCode(code="PV-GIFT-66A07F2701"), request
                    )
                with backend.database() as connection:
                    account = connection.execute(
                        "SELECT plan, pro_gift FROM accounts WHERE auth_provider_id = 'gift-recipient'"
                    ).fetchone()

        self.assertEqual(redeemed["plan"], "pro")
        self.assertEqual(account["plan"], "pro")
        self.assertEqual(account["pro_gift"], 1)
        self.assertEqual(repeated.exception.status_code, 409)

    def test_pro_history_keeps_network_and_thumbnail_metadata(self) -> None:
        request = backend.Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/history",
                "headers": [(b"authorization", b"Bearer history-token")],
            }
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(backend, "DATA_DIR", root),
                patch.object(backend, "DOWNLOAD_DIR", root / "downloads"),
                patch.object(backend, "DB_PATH", root / "jobs.sqlite3"),
                patch.object(
                    backend,
                    "supabase_user_from_request",
                    return_value={"id": "history-user", "email": "historial@example.com"},
                ),
            ):
                backend.initialize_database()
                account = backend.registered_account_from_request(request)
                with backend.database() as connection:
                    connection.execute("UPDATE accounts SET plan = 'pro' WHERE id = ?", (account["id"],))
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            id, source_url, mode, quality, audio_kbps, status, progress, message, detail,
                            token_hash, plan, account_id, thumbnail_url, created_at, expires_at
                        ) VALUES (?, ?, 'video', '1080', '320', 'complete', 100, 'Descarga lista', ?, ?, 'pro', ?, ?, 10, 20)
                        """,
                        (
                            "history-instagram",
                            "https://www.instagram.com/reel/abc",
                            "Reel de prueba",
                            "token",
                            account["id"],
                            "https://cdn.example.com/thumb.jpg",
                        ),
                    )
                history = backend.download_history(request)

        self.assertEqual(history["items"][0]["network"], "instagram")
        self.assertEqual(history["items"][0]["title"], "Reel de prueba")
        self.assertEqual(history["items"][0]["thumbnailUrl"], "https://cdn.example.com/thumb.jpg")


if __name__ == "__main__":
    unittest.main()
