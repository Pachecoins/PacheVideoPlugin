[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$Version = "0.5.7"
$Root = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $Root ".build-windows"
$Venv = Join-Path $Build "venv"
$PyInstallerDist = Join-Path $Build "pyinstaller-dist"
$PyInstallerWork = Join-Path $Build "pyinstaller-work"
$Icon = Join-Path $Build "PacheVideo.ico"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $Root "dist"
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)

New-Item -ItemType Directory -Force -Path $Build, $OutputDirectory | Out-Null

function Remove-DirectoryWithRetry([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return }
    for ($Attempt = 1; $Attempt -le 12; $Attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force
            return
        }
        catch {
            if ($Attempt -eq 12) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
}

if (!(Test-Path -LiteralPath $Venv)) {
    & py "-$PythonVersion" -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno con Python $PythonVersion" }
}

$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "companion\requirements.txt")

function Find-FFmpegBinary {
    $Candidates = [Collections.Generic.List[string]]::new()
    if ($env:PACHEVIDEO_FFMPEG) { $Candidates.Add($env:PACHEVIDEO_FFMPEG) }
    foreach ($Candidate in (& where.exe ffmpeg 2>$null)) { $Candidates.Add($Candidate) }

    foreach ($Candidate in ($Candidates | Select-Object -Unique)) {
        if (!(Test-Path -LiteralPath $Candidate -PathType Leaf)) { continue }
        if ((Get-Item -LiteralPath $Candidate).Length -lt 5MB) { continue }
        $VersionOutput = & $Candidate -version 2>&1
        if ($LASTEXITCODE -eq 0 -and $VersionOutput -match "ffmpeg version") {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }

    $Archive = Join-Path $Build "ffmpeg-release-essentials.zip"
    $Expanded = Join-Path $Build "ffmpeg-download"
    if (!(Test-Path -LiteralPath $Archive)) {
        $DownloadParameters = @{
            Uri = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            OutFile = $Archive
        }
        Invoke-WebRequest @DownloadParameters
    }
    if (Test-Path -LiteralPath $Expanded) {
        Remove-Item -LiteralPath $Expanded -Recurse -Force
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Expanded
    $Downloaded = Get-ChildItem -LiteralPath $Expanded -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if (!$Downloaded) { throw "El paquete descargado no contiene ffmpeg.exe" }
    return $Downloaded.FullName
}

$FFmpeg = Find-FFmpegBinary
$Encoders = (& $FFmpeg -hide_banner -encoders 2>&1) -join "`n"
if ($Encoders -notmatch "libx264") { throw "FFmpeg no incluye el codificador libx264" }
if ($Encoders -notmatch "libmp3lame") { throw "FFmpeg no incluye el codificador libmp3lame" }

$IconScript = Join-Path $Root "scripts\make-windows-icon.py"
$Logo = Join-Path $Root "plugin\icons\logo.png"
& $Python $IconScript $Logo $Icon

if (Test-Path -LiteralPath $PyInstallerDist) {
    Remove-DirectoryWithRetry $PyInstallerDist
}
if (Test-Path -LiteralPath $PyInstallerWork) {
    Remove-DirectoryWithRetry $PyInstallerWork
}

$env:PACHEVIDEO_FFMPEG = $FFmpeg
$env:PACHEVIDEO_ICON = $Icon
$HelperBuildArguments = @(
    "--noconfirm",
    "--clean",
    "--distpath", $PyInstallerDist,
    "--workpath", $PyInstallerWork,
    (Join-Path $Root "companion\PacheVideoHelper.windows.spec")
)
& $PyInstaller @HelperBuildArguments
if ($LASTEXITCODE -ne 0) { throw "Falló la compilación de PacheVideo Helper" }

$AppBuildArguments = @(
    "--noconfirm",
    "--clean",
    "--distpath", $PyInstallerDist,
    "--workpath", $PyInstallerWork,
    (Join-Path $Root "companion\PacheVideo.windows.spec")
)
& $PyInstaller @AppBuildArguments
if ($LASTEXITCODE -ne 0) { throw "Falló la compilación de PacheVideo" }

$HelperExe = Join-Path $PyInstallerDist "PacheVideoHelper\PacheVideoHelper.exe"
$AppExe = Join-Path $PyInstallerDist "PacheVideo\PacheVideo.exe"
if (!(Test-Path -LiteralPath $HelperExe)) { throw "PyInstaller no generó $HelperExe" }
if (!(Test-Path -LiteralPath $AppExe)) { throw "PyInstaller no generó $AppExe" }

$Inno = $env:PACHEVIDEO_ISCC
if ([string]::IsNullOrWhiteSpace($Inno)) {
    $Inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
}
if (!(Test-Path -LiteralPath $Inno)) { throw "No se encontró Inno Setup 6 (ISCC.exe)" }

$InnoArguments = @(
    "/DSourceRoot=$Root",
    "/DBuildRoot=$Build",
    "/DOutputDir=$OutputDirectory",
    "/DAppVersion=$Version",
    (Join-Path $Root "packaging\windows\PacheVideo.iss")
)
& $Inno @InnoArguments
if ($LASTEXITCODE -ne 0) { throw "Inno Setup no pudo generar el instalador" }

$Installer = Join-Path $OutputDirectory "PacheVideo-Setup-Windows-x64.exe"
if (!(Test-Path -LiteralPath $Installer)) { throw "No se generó $Installer" }
$Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$Installer.sha256" -Value "$Hash  PacheVideo-Setup-Windows-x64.exe" -Encoding ascii

Write-Host "Instalador generado: $Installer"
Write-Host "SHA-256: $Hash"
