# PacheVideo Tools for Adobe Premiere

PacheVideo Tools is a Premiere UXP panel that downloads video/audio through yt-dlp and FFmpeg, then imports the result into the active Premiere project.

The macOS GitHub build produces two complete installers:

- `PacheVideo-Premiere-macOS-arm64.pkg` for Apple Silicon.
- `PacheVideo-Premiere-macOS-x86_64.pkg` for Intel Macs.

Each `.pkg` installs:

1. `/Applications/PacheVideo Helper.app`, including FFmpeg 8.0.1 and yt-dlp.
2. The UXP panel as `PacheVideo-Premiere.ccx` through Adobe UPIA.
3. `/Library/LaunchAgents/com.pachevideo.helper.plist` so the helper starts automatically.

## Requirements

- macOS 13 or later.
- Adobe Premiere 25.6 or later.
- Adobe Creative Cloud Desktop installed and updated.
- Xcode Command Line Tools and Homebrew only when building locally.

## Install from the latest GitHub Release

From a cloned repository:

```bash
git clone https://github.com/Pachecoins/pachevideo-premiere.git
cd pachevideo-premiere
chmod +x scripts/install-latest-macos.sh
./scripts/install-latest-macos.sh Pachecoins/pachevideo-premiere
```

Or download the installer for your architecture from **Releases** and double-click the `.pkg`.

After installation, restart Premiere and open:

```text
Window > UXP Plugins > PacheVideo Tools
```

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
git tag v0.2.3
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

## UXP package

The build creates a `.ccx` ZIP-compatible package with the manifest at its root. Adobe UPIA installs it during the `.pkg` post-install step. The plugin uses port `18765` on loopback to communicate with the helper.

## Logs

- Installer: `/var/log/PacheVideoInstaller.log`
- Helper stdout: `/tmp/com.pachevideo.helper.out.log`
- Helper stderr: `/tmp/com.pachevideo.helper.err.log`

## Responsible use

Users must have authorization to download source media and must follow the originating site's terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before redistribution.
