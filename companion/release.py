"""Small, dependency-free release checker used by the desktop client."""

from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen


LATEST_RELEASE_URL = "https://api.github.com/repos/Pachecoins/PacheVideoPlugin/releases/latest"
WINDOWS_INSTALLER_URL = (
    "https://github.com/Pachecoins/PacheVideoPlugin/releases/latest/download/"
    "PacheVideo-Setup-Windows-x64.exe"
)


def version_key(value: str) -> tuple[int, ...]:
    """Parse release labels such as v0.5.2 without evaluating external input."""
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers[:4]) or (0,)


def is_newer_release(candidate: str, current: str) -> bool:
    width = max(len(version_key(candidate)), len(version_key(current)))
    return version_key(candidate) + (0,) * (width - len(version_key(candidate))) > (
        version_key(current) + (0,) * (width - len(version_key(current)))
    )


def fetch_latest_release(timeout: float = 4.0) -> tuple[str, str] | None:
    """Return (version, Windows installer URL), or None when offline/unavailable."""
    request = Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PacheVideo-Desktop"},
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        return None
    for asset in payload.get("assets") or []:
        if asset.get("name") == "PacheVideo-Setup-Windows-x64.exe":
            url = str(asset.get("browser_download_url") or "").strip()
            if url:
                return tag.removeprefix("v"), url
    return tag.removeprefix("v"), WINDOWS_INSTALLER_URL
