import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def harness(args: list[str], cwd: Path, inp: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ, PYTHONPATH=str(REPO_ROOT), **(env or {}))
    return subprocess.run([sys.executable, "-m", "harness", *args], cwd=str(cwd), input=inp,
                          capture_output=True, text=True, timeout=600, env=e, check=False)


def gcmd(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=str(cwd), check=True, capture_output=True, text=True)
