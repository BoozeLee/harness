"""Team policy bundle: the shared files of .ai-engineering/ versioned in a Git repo.

Bundle = policy.json + verification.json at .ai-engineering/ in the bundle repo.
Everything else stays local on purpose: project.json carries machine-specific
paths, and tasks/evidence/audit.log are per-repo history.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from harness.policy import AE, die, find_root

BUNDLE = ("policy.json", "verification.json")


def _git(cwd: Path, *a: str) -> tuple[int, str]:
    p = subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=False)
    return p.returncode, (p.stdout + p.stderr).rstrip()


def _clone(remote: str, branch: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="harness-bundle-"))
    clone = tmp / "repo"
    rc, out = _git(tmp, "clone", remote, "repo")
    if rc:
        shutil.rmtree(tmp, ignore_errors=True)
        die(f"cannot clone bundle remote {remote!r}: {out}")
    if _git(clone, "rev-parse", "--verify", f"origin/{branch}")[0] == 0:
        _git(clone, "checkout", "-B", branch, f"origin/{branch}")
    else:
        # non-empty repo without the branch: new branch off HEAD; empty repo: unborn HEAD
        _git(clone, "checkout", "-B", branch)
    return clone


def _need_local(r: Path) -> None:
    miss = [n for n in BUNDLE if not (r / AE / n).exists()]
    if miss:
        die(f"missing {', '.join(miss)}; run `harness init` first")


def _remote_bundle(clone: Path) -> dict[str, str]:
    out = {}
    for n in BUNDLE:
        p = clone / AE / n
        if p.exists():
            out[n] = p.read_text()
        else:
            die(f"bundle remote has no {AE}/{n}; run `harness policy push` from a member repo first")
    return out


def _push(r: Path, clone: Path, a) -> int:
    _need_local(r)
    dst = clone / AE
    dst.mkdir(parents=True, exist_ok=True)
    for n in BUNDLE:
        shutil.copy2(r / AE / n, dst / n)
    _git(clone, "add", "-A")
    rc, out = _git(clone, "commit", "-m", f"harness policy bundle: {r.name}")
    if "nothing to commit" in out:
        print("Bundle   : unchanged (remote already has this state)")
        return 0
    rc, out = _git(clone, "push", "origin", f"HEAD:{a.branch}")
    if rc:
        die(f"push failed: {out}")
    print(f"Pushed   : {_git(clone, 'rev-parse', 'HEAD')[1]} -> {a.remote} ({a.branch})")
    return 0


def _status(r: Path, clone: Path, a) -> int:
    _need_local(r)
    remote = _remote_bundle(clone)
    drift = [n for n in BUNDLE if remote[n] != (r / AE / n).read_text()]
    for n in drift:
        print(f"DRIFT    : {AE}/{n} differs from {a.remote} ({a.branch})")
    if drift:
        return 1
    print(f"In sync  : {', '.join(BUNDLE)} match {a.remote} ({a.branch})")
    return 0


def _pull(r: Path, clone: Path, a) -> int:
    remote = _remote_bundle(clone)
    updated = []
    for n in BUNDLE:
        lp = r / AE / n
        if not lp.exists() or lp.read_text() != remote[n]:
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.write_text(remote[n])
            updated.append(n)
    print(f"Pulled   : {', '.join(updated) if updated else 'nothing (already in sync)'}")
    return 0


def cmd_policy(a) -> int:
    r = find_root(a.repo)
    if not r:
        die("run `harness init` first")
    clone = _clone(a.remote, a.branch)
    try:
        if a.polc == "push":
            return _push(r, clone, a)
        if a.polc == "status":
            return _status(r, clone, a)
        return _pull(r, clone, a)
    finally:
        shutil.rmtree(clone.parent, ignore_errors=True)
