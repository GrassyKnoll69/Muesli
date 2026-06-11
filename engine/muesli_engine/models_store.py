"""First-run model download helpers.

Manages two kinds of large assets:

1. Diarization ONNX models (sherpa-onnx segmentation + speaker embedding).
2. Opt-in CUDA DLL libraries (nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels).

All network I/O is performed by :func:`_download`.  Pass *progress* callbacks
to receive streaming download notifications.  No asset is downloaded unless it
is actually absent or its checksum does not match.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

import httpx

from muesli_engine.config import CUDA_DIR, MODELS_DIR
from muesli_engine.diarize.pipeline import EMBEDDING_MODEL, SEGMENTATION_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model specs
# ---------------------------------------------------------------------------

_EMBEDDING: dict = {
    "filename": EMBEDDING_MODEL,
    "url": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
        "speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx"
    ),
    "sha256": "5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94",
    "archive_member": None,
}

_SEGMENTATION: dict = {
    "filename": SEGMENTATION_MODEL,
    "url": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
        "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
    ),
    "sha256": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "archive_member": "sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
}

_DIARIZATION_SPECS = [_SEGMENTATION, _EMBEDDING]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

ProgressFn = Callable[[str, int, int | None], None]


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(
    url: str,
    dest: Path,
    progress: ProgressFn | None = None,
    filename_hint: str = "",
) -> None:
    """Download *url* to *dest* with optional *progress* callback.

    The download is streamed in chunks.  *progress* is called as
    ``progress(filename_hint, bytes_downloaded, total_or_None)`` after each
    chunk.
    """
    with httpx.Client(follow_redirects=True, timeout=300) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total_str = resp.headers.get("content-length")
            total: int | None = int(total_str) if total_str else None
            downloaded = 0
            with open(dest, "wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(filename_hint, downloaded, total)


# ---------------------------------------------------------------------------
# Diarization model management
# ---------------------------------------------------------------------------


def diarization_models_present() -> bool:
    """Return True if both diarization model files exist under MODELS_DIR."""
    return (MODELS_DIR / SEGMENTATION_MODEL).exists() and (
        MODELS_DIR / EMBEDDING_MODEL
    ).exists()


def ensure_diarization_models(
    progress: ProgressFn | None = None,
) -> dict[str, str]:
    """Ensure both diarization ONNX models are present and correct.

    For each model:
    - If the file is absent, download it.
    - If the file is present but its SHA-256 does not match, re-download.
    - If *archive_member* is set, extract that member from the downloaded
      tar.bz2 and write it as *filename*; otherwise move the raw download.
    - After writing, verify the SHA-256 against the spec; raise RuntimeError
      on mismatch.

    Args:
        progress: Optional callback ``(filename, bytes_downloaded, total|None)``.

    Returns:
        ``{"segmentation": "<path>", "embedding": "<path>"}``.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    key_map = {SEGMENTATION_MODEL: "segmentation", EMBEDDING_MODEL: "embedding"}

    for spec in _DIARIZATION_SPECS:
        filename: str = spec["filename"]
        expected_sha: str = spec["sha256"]
        dest = MODELS_DIR / filename
        key = key_map[filename]

        # Check if already present with correct checksum.
        if dest.exists() and _sha256(dest) == expected_sha:
            results[key] = str(dest)
            continue

        # Need to download.
        logger.info("Downloading %s …", filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = Path(tmp.name)

        try:
            _download(spec["url"], tmp_path, progress=progress, filename_hint=filename)

            if spec["archive_member"]:
                # Extract the specific member from the tar.bz2.
                with tarfile.open(tmp_path, mode="r:bz2") as tf:
                    member = tf.getmember(spec["archive_member"])
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        raise RuntimeError(
                            f"Could not extract {spec['archive_member']} from archive"
                        )
                    data = extracted.read()
                dest.write_bytes(data)
            else:
                shutil.move(str(tmp_path), str(dest))
                tmp_path = dest  # don't delete again

        finally:
            if tmp_path.exists() and tmp_path != dest:
                tmp_path.unlink(missing_ok=True)

        # Verify checksum of the written file.
        actual = _sha256(dest)
        if actual != expected_sha:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Checksum mismatch for {filename}: "
                f"expected {expected_sha}, got {actual}"
            )

        results[key] = str(dest)
        logger.info("Saved %s", dest)

    return results


# ---------------------------------------------------------------------------
# Opt-in CUDA library management
# ---------------------------------------------------------------------------

_CUDA_PACKAGES = ("nvidia-cublas-cu12", "nvidia-cudnn-cu12")


def cuda_libraries_present() -> bool:
    """Return True if CUDA_DIR exists and contains at least one DLL."""
    if not CUDA_DIR.exists():
        return False
    return any(CUDA_DIR.rglob("*.dll"))


def ensure_cuda_libraries(progress: ProgressFn | None = None) -> str:
    """Download CUDA wheel packages and extract their DLLs into CUDA_DIR.

    For each of ``nvidia-cublas-cu12`` and ``nvidia-cudnn-cu12``:
    - Query the PyPI JSON API to find the latest win_amd64 wheel.
    - Download the wheel (which is a zip file).
    - Extract every ``*/bin/*.dll`` member into ``CUDA_DIR/<pkg>/``.

    Args:
        progress: Optional callback ``(filename, bytes_downloaded, total|None)``.

    Returns:
        ``str(CUDA_DIR)``.
    """
    CUDA_DIR.mkdir(parents=True, exist_ok=True)

    for pkg in _CUDA_PACKAGES:
        pypi_url = f"https://pypi.org/pypi/{pkg}/json"
        try:
            resp = httpx.get(pypi_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to query PyPI for %s: %s", pkg, exc)
            continue

        # Find the newest version that has a win_amd64 wheel.
        releases = data.get("releases", {})
        wheel_url: str | None = None
        wheel_filename: str | None = None

        # Sort versions descending (newest first) with packaging-style comparison
        # using a simple key that falls back to lexicographic.
        try:
            from packaging.version import Version as _V

            sorted_versions = sorted(releases.keys(), key=_V, reverse=True)
        except Exception:
            sorted_versions = sorted(releases.keys(), reverse=True)

        for version in sorted_versions:
            files = releases[version]
            for f in files:
                fname: str = f.get("filename", "")
                if "win_amd64" in fname and fname.endswith(".whl"):
                    wheel_url = f.get("url")
                    wheel_filename = fname
                    break
            if wheel_url:
                break

        if not wheel_url:
            logger.warning("No win_amd64 wheel found for %s — skipping", pkg)
            continue

        pkg_dir = CUDA_DIR / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading %s …", wheel_filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".whl") as tmp:
            tmp_path = Path(tmp.name)

        try:
            _download(
                wheel_url,
                tmp_path,
                progress=progress,
                filename_hint=wheel_filename or pkg,
            )
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for member in zf.namelist():
                    # Extract only DLLs under a */bin/ directory.
                    parts = member.split("/")
                    if (
                        len(parts) >= 2
                        and parts[-2] == "bin"
                        and member.lower().endswith(".dll")
                    ):
                        dll_name = parts[-1]
                        out_path = pkg_dir / dll_name
                        out_path.write_bytes(zf.read(member))
                        logger.info("Extracted %s → %s", dll_name, out_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    return str(CUDA_DIR)
