"""Runner-path parity for the repro-metadata feature.

The CLI ``harness verify --embed-repro`` writes a ``repro`` block into the
evidence JSON. The serve-side ``Runner._verify_run`` is a parallel re-
implementation of verify; this module locks in parity by exercising both paths
through the FastAPI test client and the ``harness`` CLI driver.
"""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from helpers import harness

from harness import __version__
from harness.policy import jload, jsave
from harness.server import create_app

TOK = "test-token"
AUTH = {"Authorization": f"Bearer {TOK}"}


# Mirror the contract pinned in tests/test_repro.py. Kept duplicated here so
# each test file is independently runnable.
REPRO_KEYS = {
    "captured_at", "harness_sha", "harness_version", "python_version",
    "python_implementation", "platform", "host",
    "packages_sha256", "packages_count",
    "github_sha", "github_run_id", "github_run_attempt",
}


def client_for(repo: Path) -> TestClient:
    return TestClient(create_app(repo, TOK))


def wait_run(c: TestClient, run_id: str, want: str = "succeeded", secs: float = 90) -> dict:
    import time
    t0 = time.time()
    while time.time() - t0 < secs:
        row = c.get(f"/api/runs/{run_id}", headers=AUTH).json()
        if row["status"] in (want, "failed", "cancelled"):
            assert row["status"] == want, row
            return row
        time.sleep(0.15)
    raise AssertionError(f"run {run_id} still {row['status']} after {secs}s")


# ---------------------------------------------------------------------------
# Runner path (serve /api/tasks/<name>/verify)


def _enable_repro_in_contract(pyrepo: Path, name: str, on: bool) -> None:
    cf = pyrepo / ".ai-engineering" / "tasks" / f"{name}.json"
    c = jload(cf)
    c["embed_repro"] = on
    jsave(cf, c)


def test_runner_emits_repro_when_contract_says_so(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "rep", "goal": "keep add", "risk": "low", "allow": ["src/**"],
                     "embed_repro": True})
    assert r.status_code == 201
    assert r.json()["contract"]["embed_repro"] is True
    run_id = c.post("/api/tasks/rep/verify", headers=AUTH).json()["id"]
    wait_run(c, run_id)
    ev = c.get("/api/evidence/rep", headers=AUTH).json()
    assert "repro" in ev, ev
    assert set(ev["repro"].keys()) >= REPRO_KEYS
    assert ev["repro"]["harness_version"] == __version__


def test_runner_omits_repro_when_off(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "nor", "goal": "keep add", "risk": "low", "allow": ["src/**"]})
    assert r.status_code == 201
    assert r.json()["contract"]["embed_repro"] is False
    run_id = c.post("/api/tasks/nor/verify", headers=AUTH).json()["id"]
    wait_run(c, run_id)
    ev = c.get("/api/evidence/nor", headers=AUTH).json()
    assert "repro" not in ev, ev


def test_per_invocation_embed_repro_override_mutates_contract(pyrepo: Path):
    """Per-invocation override on /verify persists on the contract so the
    next run inherits it. The override never silently flips contract state."""
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "ovr", "goal": "keep add", "risk": "low", "allow": ["src/**"]})
    assert r.status_code == 201
    cf = pyrepo / ".ai-engineering" / "tasks" / "ovr.json"
    assert jload(cf)["embed_repro"] is False

    # First run with the override enabled
    run_id = c.post("/api/tasks/ovr/verify", headers=AUTH, params={"embed_repro": True}).json()["id"]
    wait_run(c, run_id)
    assert jload(cf)["embed_repro"] is True
    assert "repro" in c.get("/api/evidence/ovr", headers=AUTH).json()

    # Idempotency: same override on a second run still produces the repro block
    run_id = c.post("/api/tasks/ovr/verify", headers=AUTH, params={"embed_repro": True}).json()["id"]
    wait_run(c, run_id)
    assert jload(cf)["embed_repro"] is True


def test_repro_block_is_byte_identical_to_cli_when_inputs_match(pyrepo: Path, monkeypatch):
    """CLI ``harness verify --embed-repro`` and the runner path produce the
    same ``repro`` block shape for the same checkout. The wall-clock
    ``captured_at`` differs, so we ignore that one field."""
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "par", "goal": "keep add", "risk": "low", "allow": ["src/**"],
                     "embed_repro": True})
    assert r.status_code == 201
    # Make sure the worktree actually has a tracked file (gates need a diff)
    wt = Path(r.json()["contract"]["worktree"])
    (wt / "src" / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n")
    (wt / "src" / "mul.py").write_text(
        "def mul(a: int, b: int) -> int:\n    return a * b\n")

    run_id = c.post("/api/tasks/par/verify", headers=AUTH).json()["id"]
    wait_run(c, run_id)
    ev_serve = c.get("/api/evidence/par", headers=AUTH).json()
    assert "repro" in ev_serve

    # CLI path against the same contract: re-run ``harness verify --embed-repro`` in the worktree
    rc = subprocess.run(
        [sys.executable, "-m", "harness", "verify", "par", "--embed-repro"],
        cwd=str(pyrepo), capture_output=True, text=True, check=False,
    )
    assert rc.returncode == 0, rc.stderr

    # CLI evidence writes into the same AE/evidence/<task>.json; rerun must overwrite with the same shape
    repro_cli = jload(pyrepo / ".ai-engineering" / "evidence" / "par.json").get("repro")
    assert repro_cli is not None
    repro_serve = {k: v for k, v in ev_serve["repro"].items() if k != "captured_at"}
    repro_cli_clean = {k: v for k, v in repro_cli.items() if k != "captured_at"}
    assert repro_serve == repro_cli_clean


# ---------------------------------------------------------------------------
# CLI contract surface


def test_task_start_persists_embed_repro(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    rc = harness(["task", "start", "demo", "--goal", "x", "--risk", "low", "--embed-repro"], pyrepo)
    assert rc.returncode == 0, rc.stderr
    cf = pyrepo / ".ai-engineering" / "tasks" / "demo.json"
    assert jload(cf)["embed_repro"] is True


def test_task_start_default_is_off(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    rc = harness(["task", "start", "demo", "--goal", "x", "--risk", "low"], pyrepo)
    assert rc.returncode == 0, rc.stderr
    assert jload(pyrepo / ".ai-engineering" / "tasks" / "demo.json")["embed_repro"] is False


def test_task_update_toggles_embed_repro(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    harness(["task", "start", "demo", "--goal", "x", "--risk", "low"], pyrepo)
    cf = pyrepo / ".ai-engineering" / "tasks" / "demo.json"
    assert jload(cf)["embed_repro"] is False
    rc = harness(["task", "update", "demo", "--embed-repro", "on"], pyrepo)
    assert rc.returncode == 0, rc.stderr
    assert jload(cf)["embed_repro"] is True
    rc = harness(["task", "update", "demo", "--embed-repro", "off"], pyrepo)
    assert rc.returncode == 0, rc.stderr
    assert jload(cf)["embed_repro"] is False
