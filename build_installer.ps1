<#
.SYNOPSIS
    One-command Windows build for Muesli: UI -> PyInstaller bundle -> Inno Setup installer.

.DESCRIPTION
    Runs the full packaging pipeline and fails fast on any step:
      1. npm --prefix ui run build           -> ui/dist
      2. pyinstaller packaging/muesli.spec    -> dist/Muesli/Muesli.exe (onedir)
      3. iscc packaging/muesli.iss            -> packaging/Output/MuesliSetup-<version>.exe

    The version is read from engine/pyproject.toml and stamped into the output
    filename and the installer's version metadata.

.NOTES
    Prerequisites: the engine venv (engine/.venv) with PyInstaller installed,
    Node.js, and Inno Setup 6 (winget install JRSoftware.InnoSetup).
#>
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root "engine\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Engine venv not found at $py. Create it and install requirements + pyinstaller." }

# --- version from engine/pyproject.toml ---
$pyproject = Get-Content (Join-Path $root "engine\pyproject.toml") -Raw
if ($pyproject -match '(?m)^\s*version\s*=\s*"([^"]+)"') {
    $version = $Matches[1]
} else {
    throw "Could not read version from engine/pyproject.toml"
}
Write-Host "=== Building Muesli $version ===" -ForegroundColor Cyan

# --- 1. UI ---
Write-Host "[1/3] Building UI (npm run build)..." -ForegroundColor Cyan
npm --prefix ui run build
if ($LASTEXITCODE -ne 0) { throw "UI build failed (npm run build)." }

# --- 2. PyInstaller bundle ---
Write-Host "[2/3] Building app bundle (PyInstaller)..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean packaging/muesli.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
if (-not (Test-Path (Join-Path $root "dist\Muesli\Muesli.exe"))) { throw "Expected dist\Muesli\Muesli.exe was not produced." }

# --- 3. Inno Setup installer ---
Write-Host "[3/3] Building installer (Inno Setup)..." -ForegroundColor Cyan
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe not found. Install Inno Setup 6: winget install JRSoftware.InnoSetup" }

& $iscc "/DMyAppVersion=$version" "packaging\muesli.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed." }

$out = Join-Path $root "packaging\Output\MuesliSetup-$version.exe"
Write-Host "=== Done -> $out ===" -ForegroundColor Green
