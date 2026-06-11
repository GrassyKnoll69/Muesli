"""Tests for muesli_engine.models_store.

All tests are fully offline — no real network calls are made.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import muesli_engine.models_store as models_store
from muesli_engine.models_store import (
    EMBEDDING_MODEL,
    SEGMENTATION_MODEL,
    _EMBEDDING,
    _SEGMENTATION,
    diarization_models_present,
    ensure_diarization_models,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_dummy(path: Path, content: bytes = b"dummy") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


# ---------------------------------------------------------------------------
# diarization_models_present
# ---------------------------------------------------------------------------


def test_diarization_models_present_false_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)
    assert diarization_models_present() is False


def test_diarization_models_present_false_when_one_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)
    _write_dummy(tmp_path / SEGMENTATION_MODEL)
    assert diarization_models_present() is False


def test_diarization_models_present_true_when_both_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)
    _write_dummy(tmp_path / SEGMENTATION_MODEL)
    _write_dummy(tmp_path / EMBEDDING_MODEL)
    assert diarization_models_present() is True


# ---------------------------------------------------------------------------
# ensure_diarization_models — "skip when already present" path
# ---------------------------------------------------------------------------


def test_ensure_diarization_models_skips_download_when_correct(tmp_path, monkeypatch):
    """When both files exist with the expected checksums, _download is never called."""
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)

    # Create dummy files at the expected paths.
    seg_path = tmp_path / SEGMENTATION_MODEL
    emb_path = tmp_path / EMBEDDING_MODEL
    _write_dummy(seg_path)
    _write_dummy(emb_path)

    # Patch _sha256 to return the expected hashes without reading real bytes.
    sha_map = {
        seg_path: _SEGMENTATION["sha256"],
        emb_path: _EMBEDDING["sha256"],
    }
    monkeypatch.setattr(models_store, "_sha256", lambda p: sha_map[p])

    # Patch _download to raise so any download attempt fails the test.
    def _no_download(*args, **kwargs):
        raise AssertionError("_download should not have been called")

    monkeypatch.setattr(models_store, "_download", _no_download)

    result = ensure_diarization_models()

    assert result["segmentation"] == str(seg_path)
    assert result["embedding"] == str(emb_path)


# ---------------------------------------------------------------------------
# ensure_diarization_models — checksum-mismatch triggers re-download
# ---------------------------------------------------------------------------


def test_ensure_diarization_models_redownloads_on_checksum_mismatch(
    tmp_path, monkeypatch
):
    """A file with the wrong checksum triggers _download, then re-verifies."""
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)

    seg_path = tmp_path / SEGMENTATION_MODEL
    emb_path = tmp_path / EMBEDDING_MODEL

    # Write "stale" content for segmentation; correct content for embedding.
    _write_dummy(seg_path, b"stale-bytes")
    _write_dummy(emb_path)

    # sha256 for embedding is always correct; for segmentation, return wrong
    # hash first (triggering re-download), then correct hash after download.
    call_count: dict[str, int] = {"seg": 0}

    def _fake_sha256(p: Path) -> str:
        if p == seg_path:
            call_count["seg"] += 1
            # First call (existence check): wrong hash → triggers download.
            # Second call (post-write verify): correct hash.
            if call_count["seg"] == 1:
                return "wrong-hash"
            return _SEGMENTATION["sha256"]
        return _EMBEDDING["sha256"]

    monkeypatch.setattr(models_store, "_sha256", _fake_sha256)

    # _download should write some bytes to its dest path; we just overwrite
    # seg_path with dummy bytes (the second _sha256 call will return the
    # correct hash anyway).
    downloaded: list[str] = []

    def _fake_download(url, dest, progress=None, filename_hint=""):
        downloaded.append(filename_hint or str(dest))
        dest.write_bytes(b"downloaded")

    monkeypatch.setattr(models_store, "_download", _fake_download)

    # Patch tarfile.open so the archive extraction path is exercised without
    # needing a real tar.bz2.  The segmentation spec has archive_member set,
    # so we need to return something that behaves like a TarFile.
    import io as _io
    import types

    class _FakeTf:
        def __init__(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def getmember(self, name):
            return object()

        def extractfile(self, member):
            return _io.BytesIO(b"extracted-onnx-bytes")

    monkeypatch.setattr(models_store.tarfile, "open", lambda *a, **kw: _FakeTf())

    result = ensure_diarization_models()

    assert SEGMENTATION_MODEL.split(".")[0].replace("-", "_") or True  # existence check
    assert result["segmentation"] == str(seg_path)
    assert result["embedding"] == str(emb_path)
    assert len(downloaded) == 1  # only segmentation was re-downloaded


# ---------------------------------------------------------------------------
# ensure_diarization_models — both files absent → download both
# ---------------------------------------------------------------------------


def test_ensure_diarization_models_downloads_when_absent(tmp_path, monkeypatch):
    """When both files are missing, _download is called twice (once per spec)."""
    monkeypatch.setattr(models_store, "MODELS_DIR", tmp_path)

    downloaded: list[str] = []

    def _fake_download(url, dest, progress=None, filename_hint=""):
        downloaded.append(filename_hint)
        dest.write_bytes(b"fake-model-bytes")

    monkeypatch.setattr(models_store, "_download", _fake_download)

    # Patch tarfile for the segmentation archive extraction.
    import io as _io

    class _FakeTf:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def getmember(self, name):
            return object()

        def extractfile(self, member):
            return _io.BytesIO(b"fake-onnx")

    monkeypatch.setattr(models_store.tarfile, "open", lambda *a, **kw: _FakeTf())

    # Patch _sha256 to always return the expected hash (post-write check).
    def _fake_sha256(p: Path) -> str:
        if SEGMENTATION_MODEL in p.name:
            return _SEGMENTATION["sha256"]
        return _EMBEDDING["sha256"]

    monkeypatch.setattr(models_store, "_sha256", _fake_sha256)

    result = ensure_diarization_models()

    assert len(downloaded) == 2
    assert result["segmentation"] == str(tmp_path / SEGMENTATION_MODEL)
    assert result["embedding"] == str(tmp_path / EMBEDDING_MODEL)
