# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Muesli (Windows, onedir).

Build from the repo root with the project venv active:

    pyinstaller packaging/muesli.spec

onedir (not onefile) is deliberate: faster startup and far fewer native-DLL
extraction problems with ctranslate2 / onnxruntime / sherpa-onnx, which ship
many DLLs loaded by name at runtime.

Model weights are NOT bundled. The Whisper model and the sherpa-onnx diarization
models are downloaded on first use into %LOCALAPPDATA%\\Muesli\\models (see
muesli_engine.models_store). The optional NVIDIA CUDA libraries are likewise
downloaded on demand, never bundled.
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

# SPECPATH is the directory containing this spec (packaging/).
project_root = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = []
binaries = []
hiddenimports = []


def _collect(pkg: str) -> None:
    """Collect a package's data files, native libs, and submodules if present."""
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        return
    datas.extend(d)
    binaries.extend(b)
    hiddenimports.extend(h)


# Built UI, served by FastAPI StaticFiles at runtime (resolved via sys._MEIPASS).
ui_dist = os.path.join(project_root, "ui", "dist")
datas.append((ui_dist, os.path.join("ui", "dist")))

# Native / data-heavy dependencies PyInstaller can't fully infer on its own.
for _pkg in (
    "faster_whisper",
    "ctranslate2",
    "sherpa_onnx",
    "onnxruntime",
    "av",            # faster-whisper's audio decoder (PyAV), if present
    "pyaudiowpatch",
):
    _collect(_pkg)

# The engine package and its submodules.
hiddenimports += collect_submodules("muesli_engine")

# uvicorn loads its protocol/loop implementations dynamically.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.loops.asyncio",
    "anyio._backends._asyncio",
]

block_cipher = None

a = Analysis(
    [os.path.join(project_root, "run.py")],
    pathex=[os.path.join(project_root, "engine"), project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Muesli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # windowed app (pywebview provides the window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Muesli",
)
