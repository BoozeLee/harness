"""Evidence records: JSON (machine) + HTML (human), written under .ai-engineering/evidence."""

import html

from harness.policy import AE, jsave


def render(e: dict) -> str:
    rows = "".join(
        f"<details {'' if x['ok'] else 'open'}><summary class={'ok' if x['ok'] else 'bad'}>"
        f"{'PASS' if x['ok'] else 'FAIL'} {html.escape(x['name'])} "
        f"<small>{x['secs']}s · {html.escape(x['cmd'])}</small></summary>"
        f"<pre>{html.escape(x['tail'])}</pre></details>" for x in e["results"])
    acc = "".join(f"<li>{html.escape(x)}</li>" for x in e["accept"]) or "<li>none stated</li>"
    fl = "".join(f"<li><code>{html.escape(f)}</code></li>" for f in e["files"])
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
<h3>Evidence</h3>{rows}<h3>Files changed</h3><ul>{fl}</ul>"""


def write(r, ev: dict) -> tuple:
    jpath = r / AE / "evidence" / f"{ev['task']}.json"
    hpath = jpath.with_suffix(".html")
    jsave(jpath, ev)
    hpath.write_text(render(ev))
    return jpath, hpath
