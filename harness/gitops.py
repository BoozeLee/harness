"""Git queries with NUL-safe parsing and generated-artifact filtering."""

from harness.policy import ARTIFACTS, META_PREFIX, hit
from harness.shellx import git


def porcelain_paths(out: str) -> list[str]:
    """Parse `git status --porcelain=v1 -z` output. Rename/copy entries carry the
    source path as the next NUL field; we keep only the destination."""
    paths: list[str] = []
    recs = out.split("\0")
    i = 0
    while i < len(recs):
        rec = recs[i]
        i += 1
        if not rec:
            continue
        xy = rec[:2]
        path = rec[3:]
        if "R" in xy or "C" in xy:
            i += 1
        if path:
            paths.append(path)
    return paths


def changed_files(wt, base: str) -> list[str]:
    ch = {p for p in git(wt, "diff", "--name-only", "-z", base, "HEAD")[1].split("\0") if p}
    ch |= set(porcelain_paths(git(wt, "status", "--porcelain=v1", "-z", "-uall")[1]))
    return sorted(f for f in ch if f and not f.startswith(META_PREFIX) and not hit(f, ARTIFACTS))
