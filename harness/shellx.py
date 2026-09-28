"""Subprocess helpers. Output is rstripped, never lstripped: git porcelain lines
are significant at column 0 (a leading space is part of the status encoding)."""

import subprocess
import time
from pathlib import Path


def sh(cmd, cwd, timeout=900, inp=None):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout, input=inp, check=False)
        return p.returncode, (p.stdout + p.stderr).rstrip("\r\n"), round(time.time() - t, 1)
    except subprocess.TimeoutExpired:
        return 124, "timeout", round(time.time() - t, 1)
    except FileNotFoundError as e:
        return 127, str(e), 0.0


def git(cwd, *a):
    return sh(["git", *a], str(Path(cwd)))
