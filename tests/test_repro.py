"""Reproducibility metadata: stamp, shape, stability, never-raise contract.

The `harness.repro` module is small but high-leverage: every `harness verify
--embed-repro` call depends on it returning a stable, complete dict. These
tests pin the contract so a future refactor cannot silently drop fields or
leak exceptions.
"""

import re
import socket
import sys
from pathlib import Path

import pytest

from harness.repro import _harness_sha, _pip_freeze, embed_repro_metadata

HOST = socket.gethostname()
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

REQUIRED_KEYS = {
    "captured_at", "harness_sha", "harness_version", "python_version",
    "python_implementation", "platform", "host",
    "packages_sha256", "packages_count",
    "github_sha", "github_run_id", "github_run_attempt",
}


def test_embed_returns_required_keys(tmp_path: Path):
    meta = embed_repro_metadata(tmp_path)
    missing = REQUIRED_KEYS - meta.keys()
    assert not missing, f"missing keys: {missing}"


def test_embed_values_are_well_typed(tmp_path: Path):
    meta = embed_repro_metadata(tmp_path)
    # captured_at is an ISO timestamp with T separator
    assert isinstance(meta["captured_at"], str)
    assert "T" in meta["captured_at"]
    # Version fields are strings; harness_version looks like "1.2.3"
    assert isinstance(meta["harness_version"], str)
    assert re.match(r"^\d+\.\d+\.\d+", meta["harness_version"])
    # python_version matches running interpreter
    assert meta["python_version"] == PYTHON_VERSION
    # host matches the machine
    assert meta["host"] == HOST
    # SHA hashes are 64-hex or None
    for k in ("packages_sha256",):
        v = meta[k]
        if v is not None:
            assert len(v) == 64
            int(v, 16)
    # packages_count is an int or None
    c = meta["packages_count"]
    assert c is None or isinstance(c, int)
    assert c is None or c > 0


def test_stable_fields_match_across_calls(tmp_path: Path):
    """Two consecutive calls agree on every field except `captured_at`."""
    a = embed_repro_metadata(tmp_path)
    b = embed_repro_metadata(tmp_path)
    for k in REQUIRED_KEYS - {"captured_at"}:
        assert a[k] == b[k], f"unstable field {k!r}: {a[k]!r} vs {b[k]!r}"


def test_harness_sha_is_40_hex_when_present(tmp_path: Path):
    s = _harness_sha()
    if s is not None:
        assert len(s) == 40
        int(s, 16)


def test_pip_freeze_returns_sha_and_count_or_none(tmp_path: Path):
    f = _pip_freeze()
    if f is not None:
        sha, count = f
        assert len(sha) == 64
        int(sha, 16)
        assert count > 0


def test_embed_never_raises(tmp_path: Path):
    """Total contract: any failure becomes `None`, never an exception."""
    meta = embed_repro_metadata(tmp_path)
    assert meta is not None
    for v in meta.values():
        # value types are bounded — no Exception/traceback leakage
        assert v is None or isinstance(v, (str, int)), f"unexpected type: {type(v)}"


def test_no_github_env_does_not_set_github_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    meta = embed_repro_metadata(tmp_path)
    assert meta["github_sha"] is None
    assert meta["github_run_id"] is None
    assert meta["github_run_attempt"] is None


def test_github_env_propagates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef0123456789abcdef01234567")
    monkeypatch.setenv("GITHUB_RUN_ID", "987654321")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")
    meta = embed_repro_metadata(tmp_path)
    assert meta["github_sha"] == "0123456789abcdef0123456789abcdef01234567"
    assert meta["github_run_id"] == "987654321"
    assert meta["github_run_attempt"] == "3"


def test_override_harness_sha(tmp_path: Path):
    override = "deadbeef" * 5  # 40 hex chars
    meta = embed_repro_metadata(tmp_path, harness_sha=override)
    assert meta["harness_sha"] == override


def test_root_arg_is_accepted_but_unused(tmp_path: Path):
    """The `root` argument is kept for API symmetry with the rest of the
    evidence path; today it carries no project-level fields. Lock that in:
    passing different roots must still produce a stable harness runtime block."""
    a = embed_repro_metadata(tmp_path / "a")
    b = embed_repro_metadata(tmp_path / "b")
    assert a["harness_version"] == b["harness_version"]
    assert a["python_version"] == b["python_version"]
    assert a["host"] == b["host"]
