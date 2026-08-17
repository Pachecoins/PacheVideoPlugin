# PacheVideo

PacheVideo is a web-first video and audio preparation service powered by yt-dlp and FFmpeg. The browser sends jobs to an isolated processing server and receives a temporary download link; FFmpeg never runs on the user's phone.

## Web app and processing server

- `web/` contains the installable, responsive web interface and its server-side API proxy.
- `server/` contains the FastAPI job service, SQLite job metadata, yt-dlp/FFmpeg workers, signed download links, limits, and automatic cleanup.
- `deploy/` contains a Docker Compose deployment with Caddy HTTPS termination.
- `scripts/smoke-webapp.py` exercises the complete web-to-server download flow with a real media file.

The launch model (free trial, Pro subscription, advertising, payments, and the scaling path) is documented in [docs/LANZAMIENTO_WEB.md](docs/LANZAMIENTO_WEB.md).

The current MVP definition (one visitor trial, five free 1080p videos per registered account, MP3 up to 320 kbps, Video Pro quality gates, retries, and the path to automated billing) is documented in [docs/MVP_PRODUCTO.md](docs/MVP_PRODUCTO.md).

The channel pack, market-readiness gates, and phased commercial checklist are documented in [docs/ROADMAP_SALIDA_AL_MERCADO.md](docs/ROADMAP_SALIDA_AL_MERCADO.md).

Capacity formulas and beta/launch/viral server budgets are documented in [docs/ESTIMACION_INFRAESTRUCTURA.md](docs/ESTIMACION_INFRAESTRUCTURA.md).

Local development requires Node.js 22+, Python 3.12+, and FFmpeg:

```powershell
py -3.12 -m venv .venv-server
.\.venv-server\Scripts\python.exe -m pip install -r .\server\requirements.txt
$env:PACHEVIDEO_DATA_DIR = "$PWD/server/data"
$env:PACHEVIDEO_PUBLIC_BASE_URL = "http://127.0.0.1:8080"
.\.venv-server\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8080
```

In a second terminal:

```powershell
cd web
npm ci
$env:PACHEVIDEO_API_URL = "http://127.0.0.1:8080"
npm run dev
```

For a public launch, configure a dedicated API domain, an explicit source allowlist, an outbound firewall that blocks private networks, user authentication, quotas, billing, abuse monitoring, and object storage before increasing concurrency.

The processing API performs ten automatic download attempts by default, changes to a compatibility format after the first failure, and caps the wait between attempts so workers recover predictably. Configure `PACHEVIDEO_DOWNLOAD_ATTEMPTS`, `PACHEVIDEO_RETRY_BASE_SECONDS`, and `PACHEVIDEO_RETRY_MAX_SECONDS` to tune that policy. The web client also reconnects automatically without exposing a manual retry control. Video Pro is granted only from the subscription state synchronized with Mercado Pago; see [the subscription setup guide](docs/MERCADO_PAGO_SUSCRIPCIONES.md).

## Windows installer

`PacheVideo-Setup-Windows-x64.exe` installs the standalone Windows edition. It does not install or require UXP, Premiere, Creative Cloud, or Adobe UPIA.

1. `PacheVideo`, the standalone downloader.
2. `PacheVideo Helper`, including FFmpeg and yt-dlp.
3. Start Menu and optional desktop shortcuts.
4. Optional automatic Helper startup with Windows.
5. A complete uninstaller.

Requirements:

- Windows 10 1809 or later, x64.

Build on Windows with Python 3.12 and Inno Setup 6 installed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows-installer.ps1
```

The installer and its SHA-256 file are written to `dist/`.

The macOS GitHub build produces two complete standalone installers:

- `PacheVideo-macOS-arm64.pkg` for Apple Silicon.
- `PacheVideo-macOS-x86_64.pkg` for Intel Macs.

Each `.pkg` installs:

1. `/Applications/PacheVideo.app`, a standalone downloader that works without Premiere.
2. `/Applications/PacheVideo Helper.app`, including FFmpeg 8.0.1 and yt-dlp.
3. `/Library/LaunchAgents/com.pachevideo.helper.plist` so the helper starts automatically.

## Requirements

- macOS 13 or later.
- Xcode Command Line Tools and Homebrew only when building locally.

## Install from the latest GitHub Release

From a cloned repository:

```bash
git clone https://github.com/Pachecoins/PacheVideoPlugin.git
cd PacheVideoPlugin
chmod +x scripts/install-latest-macos.sh
./scripts/install-latest-macos.sh Pachecoins/PacheVideoPlugin
```

Or download the installer for your architecture from **Releases** and double-click the `.pkg`.

After installation, open `PacheVideo` from the macOS Applications folder.
The standalone app lets you choose a destination folder before each download.

## Build locally on a Mac

```bash
xcode-select --install
chmod +x scripts/build-macos-installer.sh
./scripts/build-macos-installer.sh
```

The installer and SHA-256 file are written to `dist/`.

## Publish a Release

Create and push a version tag:

```bash
git tag v0.5.0
git push origin main --tags
```

GitHub Actions builds both architectures. A tag automatically creates a GitHub Release containing both `.pkg` files and checksums. A manual workflow run builds downloadable Actions artifacts without creating a Release.

## Apple signing and notarization

Unsigned builds are useful for internal testing. For normal distribution, configure these repository secrets:

| Secret | Value |
|---|---|
| `MACOS_CERTIFICATE_P12` | Base64-encoded `.p12` containing Developer ID Application and Developer ID Installer certificates |
| `MACOS_CERTIFICATE_PASSWORD` | Password for the `.p12` |
| `MACOS_APPLICATION_IDENTITY` | Exact `Developer ID Application: ...` identity |
| `MACOS_INSTALLER_IDENTITY` | Exact `Developer ID Installer: ...` identity |
| `APPLE_ID` | Apple developer account email |
| `APPLE_TEAM_ID` | Apple Developer Team ID |
| `APPLE_APP_PASSWORD` | App-specific password for notarization |

When those secrets exist, the workflow signs the helper and installer, submits the `.pkg` to Apple notarization, and staples the ticket.

## Logs

- Windows Helper: `%LOCALAPPDATA%\PacheVideo\logs\helper.log`
- Installer: `/var/log/PacheVideoInstaller.log`
- Helper stdout: `/tmp/com.pachevideo.helper.out.log`
- Helper stderr: `/tmp/com.pachevideo.helper.err.log`

## Responsible use

Users must have authorization to download source media and must follow the originating site's terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before redistribution.
