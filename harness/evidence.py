"""Evidence records: JSON (machine) + HTML (human), written under .ai-engineering/evidence."""

import hashlib
import html
import re
import shutil
from pathlib import Path

from harness.policy import AE, jsave

SHOT_DIRS = ("test-results", "web/test-results")  # Playwright output conventions, worktree-relative
SHOT_EXTS = {".png", ".jpg", ".jpeg"}  # never trace.zip: traces can carry request headers (token)
MAX_SHOT_BYTES = 5 * 1024 * 1024
MAX_SHOTS_PER_GATE = 25


def _slug(s: str) -> str:
    return (re.sub(r"[^a-z0-9.]+", "-", s.lower()).strip("-.") or "shot")[:80]


def archive_shots(root: Path, task: str, worktree: str, gates: dict) -> list:
    """Copy images produced by type=e2e gates into evidence/<task>/shots/ with hash-prefixed
    names. The <task> dir is regenerated per verify so reruns never link stale evidence."""
    shutil.rmtree(Path(root) / AE / "evidence" / task, ignore_errors=True)
    dest_dir = Path(root) / AE / "evidence" / task / "shots"
    recs = []
    for k, g in gates.items():
        if g.get("type") != "e2e":
            continue
        n = 0
        for d in SHOT_DIRS:
            base = Path(worktree) / d
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*")):
                if n >= MAX_SHOTS_PER_GATE:
                    break
                if not p.is_file() or p.suffix.lower() not in SHOT_EXTS:
                    continue
                try:
                    data = p.read_bytes()
                except OSError:
                    continue
                if len(data) > MAX_SHOT_BYTES:
                    continue
                h = hashlib.sha256(data).hexdigest()
                slug = _slug(f"{p.parent.name}-{p.stem}")
                ext = p.suffix.lower()
                dest = dest_dir / f"{h[:12]}-{slug}{ext}"
                i = 2
                while dest.exists() and dest.read_bytes() != data:
                    dest = dest_dir / f"{h[:12]}-{slug}-{i}{ext}"
                    i += 1
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                recs.append({"file": f"shots/{dest.name}", "sha256": h, "bytes": len(data),
                             "test": p.parent.name, "gate": k})
                n += 1
    recs.sort(key=lambda x: (x["gate"], x["test"], x["file"]))
    return recs


def render(e: dict) -> str:
    rows = "".join(
        f"<details {'' if x['ok'] else 'open'}><summary class={'ok' if x['ok'] else 'bad'}>"
        f"{'PASS' if x['ok'] else 'FAIL'} {html.escape(x['name'])} "
        f"<small>{x['secs']}s · {html.escape(x['cmd'])}</small></summary>"
        f"<pre>{html.escape(x['tail'])}</pre></details>" for x in e["results"])
    acc = "".join(f"<li>{html.escape(x)}</li>" for x in e["accept"]) or "<li>none stated</li>"
    fl = "".join(f"<li><code>{html.escape(f)}</code></li>" for f in e["files"])
    shots = e.get("shots") or []
    sh_sec = (("<h3>Screenshots</h3><ul>" + "".join(
        f"<li><a href=\"{html.escape(x['file'])}\">{html.escape(x['file'])}</a>"
        f"<small> · sha256 {html.escape(x['sha256'][:16])}… · {x['bytes']}B · {html.escape(x['test'])}</small></li>"
        for x in shots) + "</ul>") if shots else "")
    return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Evidence: {html.escape(e['task'])}</title><style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--ok:#0a7d33;--bad:#c62828;--card:#f4f4f5}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--ok:#4cd07d;--bad:#ff6b6b;--card:#1e1e20}}}}
body{{background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem}}
.v{{font-size:2rem;font-weight:700;color:var(--{'ok' if e['verdict']=='PASS' else 'bad'})}}
details{{background:var(--card);border-radius:8px;padding:.6rem .9rem;margin:.4rem 0}}summary{{cursor:pointer;font-weight:600}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}small{{color:var(--mut);font-weight:400}}pre{{overflow-x:auto;white-space:pre-wrap}}</style>
<h1>{html.escape(e['task'])}</h1><p>{html.escape(e['goal'])}</p><div class=v>{e['verdict']}</div>
<p class=mut>{html.escape(e['stat'])}</p><h3>Acceptance criteria (checked by review)</h3><ul>{acc}</ul>
<h3>Evidence</h3>{rows}{sh_sec}<h3>Files changed</h3><ul>{fl}</ul>"""


def write(r, ev: dict) -> tuple:
    jpath = r / AE / "evidence" / f"{ev['task']}.json"
    hpath = jpath.with_suffix(".html")
    jsave(jpath, ev)
    hpath.write_text(render(ev))
    return jpath, hpath
