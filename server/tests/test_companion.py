from __future__ import annotations

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from companion.server import (
    compatibility_selector,
    inspect_media_codecs,
    is_retryable_download_error,
    retry_limit_for_error,
    selector_for_attempt,
    unique_destination,
)
import yt_dlp
from unittest.mock import patch


class CompanionReliabilityTests(unittest.TestCase):
    @patch("companion.server.subprocess.run")
    def test_desktop_detects_h264_aac_as_mobile_compatible(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stderr="Stream #0:0: Video: h264 (High), yuv420p\nStream #0:1: Audio: aac (LC), 48000 Hz",
        )
        self.assertEqual(inspect_media_codecs(Path("video.mp4"), "ffmpeg"), ("h264", "aac"))

    def test_desktop_has_compatible_single_file_fallback(self) -> None:
        self.assertEqual(
            compatibility_selector("video", "1080"),
            "best[ext=mp4][height<=1080]/best[height<=1080]/best",
        )

    def test_youtube_uses_single_file_mp4_before_high_quality_dash(self) -> None:
        self.assertEqual(
            selector_for_attempt("https://youtu.be/VYq_h7cOCBY", "video", "max", 1),
            "best[ext=mp4]/best",
        )
        self.assertEqual(
            selector_for_attempt("https://www.youtube.com/watch?v=test", "video", "1080", 1),
            "best[ext=mp4][height<=1080]/best[height<=1080]/best",
        )
        self.assertEqual(
            selector_for_attempt("https://youtu.be/test", "audio", "320", 1),
            "best[ext=mp4]/best",
        )
        self.assertEqual(
            selector_for_attempt("https://notyoutube.com/watch?v=test", "video", "max", 1),
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        )

    def test_desktop_retries_transient_but_not_private_content(self) -> None:
        self.assertTrue(
            is_retryable_download_error(yt_dlp.utils.DownloadError("HTTP Error 429"))
        )
        self.assertFalse(
            is_retryable_download_error(yt_dlp.utils.DownloadError("Private video"))
        )

    def test_desktop_stops_repeating_an_origin_forbidden_response(self) -> None:
        self.assertEqual(
            retry_limit_for_error(yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")),
            2,
        )
        self.assertGreaterEqual(
            retry_limit_for_error(yt_dlp.utils.DownloadError("HTTP Error 429")),
            3,
        )

    def test_desktop_does_not_overwrite_an_existing_download(self) -> None:
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "video.mp4").write_bytes(b"first")
            destination = unique_destination(folder, "video.mp4")
        self.assertEqual(destination.name, "video (2).mp4")


if __name__ == "__main__":
    unittest.main()
