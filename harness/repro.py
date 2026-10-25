"""Reproducibility metadata stamped into evidence bundles.

Every `harness verify` invocation can (opt-in via `--embed-repro`) attach a
`repro` block to its evidence JSON. The block captures the harness build,
runtime, host, and Python environment in a shape that survives months and
machines: a reviewer who reads `evidence/<task>.json` later can prove the
artifact was produced by an exact harness build on an exact runtime.

The function is intentionally total — it never raises. Missing data is
encoded as `None` rather than a runtime error; failures during SHA lookup or
`pip freeze` are silent so that an offline or partially-initialised workstation
still produces a usable evidence bundle.

Stable fields (`harness_sha`, `python_version`, `platform`, `host`,
`packages_sha256`, `packages_count`) match across consecutive calls on the same
machine. The `captured_at` ISO timestamp is the only wall-clock field.
"""

import datetime as _dt
import hashlib
import importlib.util as _ils
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

from harness import __version__


def _harness_sha() -> str | None:
    """Return the HEAD SHA of the installed harness checkout, or None.

    Resolves the `harness` package location via `importlib.util.find_spec`,
    then walks up looking for a `.git` directory. Wheels (no .git) return
    None — the `harness_version` field carries the wheel marker instead.
    """
    try:
        spec = _ils.find_spec("harness")
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    cur: Path | None = Path(spec.origin).resolve().parent
    while cur is not None:
        if (cur / ".git").is_dir():
            try:
                r = subprocess.run(
                    ["git", "-C", str(cur), "rev-parse", "HEAD"],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                return None
            return None
        cur = cur.parent
    return None


def _pip_freeze() -> tuple | None:
    """Return (sha256_hex, package_count) of `python -m pip freeze`, or None."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    pkgs = r.stdout
    return hashlib.sha256(pkgs.encode("utf-8")).hexdigest(), len(pkgs.splitlines())


def embed_repro_metadata(root: Path | None = None, *,
                         harness_sha: str | None = None) -> dict:
    """Return a reproducibility dict suitable for `ev["repro"]`.

    Args:
        root: repo root, kept for symmetry with the rest of the evidence path
            (currently unused; reserved for project-level fields).
        harness_sha: optional override for the harness checkout SHA. When
            None, `_harness_sha` walks the installed package to find it.

    Returns:
        A dict with stable (deterministic-on-same-machine) fields and one
        wall-clock `captured_at` field. Never raises.
    """
    freeze = _pip_freeze()
    return {
        "captured_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "harness_sha": harness_sha if harness_sha is not None else _harness_sha(),
        "harness_version": __version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "host": socket.gethostname(),
        "packages_sha256": freeze[0] if freeze else None,
        "packages_count": freeze[1] if freeze else None,
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
