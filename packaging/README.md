# Packaging Muesli for Windows

Muesli ships as an unsigned, per-user Windows installer built with **PyInstaller**
(onedir) wrapped by **Inno Setup**. Model weights and the optional CUDA libraries
are downloaded on first use, not bundled, so the base installer stays lean.

## Prerequisites

- Windows 10/11 (x64).
- The project Python venv at `engine/.venv` with all deps installed, plus
  PyInstaller:
  ```powershell
  engine\.venv\Scripts\python -m pip install -r engine\requirements.txt
  engine\.venv\Scripts\python -m pip install pyinstaller
  ```
- Node.js (to build the UI).
- **Inno Setup 6** with `ISCC.exe` available (installed via
  `winget install JRSoftware.InnoSetup`). The build script auto-discovers it under
  `%LOCALAPPDATA%\Programs\Inno Setup 6` and `Program Files`.

## One command

From the repo root:

```powershell
.\build_installer.ps1
```

This runs the full pipeline:

1. `npm --prefix ui run build` → `ui/dist`
2. `pyinstaller packaging/muesli.spec` → `dist/Muesli/Muesli.exe` (onedir)
3. `iscc packaging/muesli.iss` → `packaging/Output/MuesliSetup-<version>.exe`

The version is read from `engine/pyproject.toml` and stamped into the output
filename and the installer metadata.

## Building just the app bundle

```powershell
npm --prefix ui run build
pyinstaller packaging/muesli.spec
```

`dist/Muesli/Muesli.exe` launches the engine and opens the desktop window. If the
window is blank, the UI wasn't built first (`ui/dist` missing from the bundle).

## What is and isn't bundled

| Bundled | Downloaded on first use | External (detected) |
| --- | --- | --- |
| Python runtime, all pip deps | Whisper model | Ollama |
| Built UI (`ui/dist`) | sherpa-onnx diarization models | WebView2 runtime |
| Native libs (ctranslate2, onnxruntime, sherpa-onnx, PyAudioWPatch) | NVIDIA CUDA libs (opt-in) | |

Downloads land in `%LOCALAPPDATA%\Muesli\models`. User data (recordings, the
SQLite DB) lives in `~/.muesli` and is left untouched by uninstall.

## Known limitations

- **Unsigned.** SmartScreen will warn on first launch ("More info" →
  "Run anyway"). Code signing is out of scope for now.
- **Windows only.** Loopback capture is WASAPI-specific.
- **GPU is opt-in.** The base build is CPU-only. CUDA acceleration requires the
  NVIDIA cuBLAS/cuDNN libraries, offered as an optional download in the installer
  and in the app's first-run onboarding.
