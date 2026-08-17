from __future__ import annotations

import json
import sys
import time
from urllib.request import Request, urlopen


BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3000"
MODE = sys.argv[2] if len(sys.argv) > 2 else "video"
assert MODE in {"video", "audio"}
SAMPLE = "https://samplelib.com/mp4/sample-5s.mp4"


def json_request(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


health = json_request("/api/health")
assert health["ok"] is True and health["ffmpeg"] is True, health
job = json_request(
    "/api/jobs",
    {
        "url": SAMPLE,
        "mode": MODE,
        "quality": "480",
        "audioKbps": "192",
        "acceptedTerms": True,
    },
)
token = job["token"]
deadline = time.time() + 120
while time.time() < deadline:
    job = json_request(f"/api/jobs/{job['id']}?token={token}")
    if job["status"] in {"complete", "error"}:
        break
    time.sleep(0.75)

assert job["status"] == "complete", job
with urlopen(job["downloadUrl"], timeout=60) as response:
    first_chunk = response.read(1024)
    assert response.status == 200
    assert len(first_chunk) == 1024

expected_extension = ".mp4" if MODE == "video" else ".mp3"
assert job["fileName"].lower().endswith(expected_extension), job
print(json.dumps({"status": job["status"], "mode": MODE, "file": job["fileName"], "health": health}, ensure_ascii=False))
