#!/usr/bin/env python3
"""Harness - local-first control plane that professionalizes how coding agents work on a repo.
scan -> init -> task start -> (task run) -> verify -> pr.  Stdlib only, Python 3.9+."""
import argparse, fnmatch, html, json, os, shutil, subprocess, sys, time
from pathlib import Path

AE = ".ai-engineering"
LVL = {"low": 0, "medium": 1, "high": 2}
WRITE = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SAFE_ENV = (".env.example", ".env.sample", ".env.template")


def die(m):
    print(f"harness: {m}", file=sys.stderr); sys.exit(1)


def sh(cmd, cwd, timeout=900, inp=None):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout, input=inp)
        # rstrip (not strip): porcelain status lines are significant at column 0
        return p.returncode, (p.stdout + p.stderr).rstrip("\r\n"), round(time.time() - t, 1)
    except subprocess.TimeoutExpired:
        return 124, "timeout", round(time.time() - t, 1)
    except FileNotFoundError as e:
        return 127, str(e), 0.0


def git(cwd, *a):
    return sh(["git", *a], cwd)


def hit(rel, pats):
    rel = rel.replace(os.sep, "/")
    for p in pats:
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p):
            return True
        if p.endswith("/**") and (rel + "/").startswith(p[:-2]):
            return True
    return False


def find_root(start):
    d = Path(start).resolve()
    for c in [d, *d.parents]:
        if (c / AE / "policy.json").exists():
            return c
    return None


def jload(p):
    return json.loads(Path(p).read_text())


def jsave(p, d):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")


# ---------------------------------------------------------------- scan
def scan(repo):
    r = Path(repo).resolve()
    info = {"root": str(r), "stacks": [], "gates": {}, "protected": [], "ci": [], "notes": []}
    g = info["gates"]
    if (r / "package.json").exists():
        d = json.loads((r / "package.json").read_text()); s = d.get("scripts", {})
        deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
        pm = "pnpm" if (r / "pnpm-lock.yaml").exists() else "yarn" if (r / "yarn.lock").exists() else "npm"
        info["stacks"].append("node")
        for k, names in {"typecheck": ["typecheck", "type-check"], "lint": ["lint"], "unit": ["test", "test:unit"],
                         "build": ["build"], "e2e": ["test:e2e", "e2e"]}.items():
            for n in names:
                if n in s:
                    g[k] = f"{pm} run {n}"; break
        info["stacks"] += [f for f in ("next", "react", "vue", "svelte", "express", "prisma", "playwright") if f in deps]
    py = [f for f in ("pyproject.toml", "requirements.txt", "setup.py") if (r / f).exists()]
    if py:
        txt = "".join((r / f).read_text(errors="ignore") for f in py).lower()
        info["stacks"].append("python")
        if "pytest" in txt or (r / "tests").is_dir(): g.setdefault("unit", "python3 -m pytest -q")
        if "ruff" in txt or (r / "ruff.toml").exists(): g.setdefault("lint", "ruff check .")
        if "mypy" in txt: g.setdefault("typecheck", "mypy .")
    if (r / "Cargo.toml").exists():
        info["stacks"].append("rust")
        g.setdefault("typecheck", "cargo check"); g.setdefault("lint", "cargo clippy -- -D warnings")
        g.setdefault("unit", "cargo test")
    if (r / "go.mod").exists():
        info["stacks"].append("go"); g.setdefault("lint", "go vet ./..."); g.setdefault("unit", "go test ./...")
    if (r / "Makefile").exists():
        mk = (r / "Makefile").read_text(errors="ignore")
        for k, t in (("unit", "test"), ("lint", "lint"), ("build", "build"), ("typecheck", "typecheck")):
            if f"\n{t}:" in "\n" + mk: g.setdefault(k, f"make {t}")
    pro = [".env*", "*.pem", "id_rsa*", "secrets/**"]
    for d in ("infra/prod", "infrastructure/prod", "migrations", "prisma/migrations", "terraform", ".github/workflows"):
        if (r / d).is_dir(): pro.append(d + "/**")
    info["protected"] = pro
    wf = r / ".github" / "workflows"
    if wf.is_dir(): info["ci"] = sorted(p.name for p in wf.glob("*.y*ml"))
    if not g.get("unit"): info["notes"].append("No test command detected: agents cannot prove correctness here.")
    if not info["ci"]: info["notes"].append("No CI workflows found.")
    if any(s in info["stacks"] for s in ("next", "react", "vue", "svelte")) and "e2e" not in g:
        info["notes"].append("Web UI detected without browser tests: add Playwright for UI verification.")
    pts = sum(w for k, w in (("unit", 30), ("lint", 15), ("typecheck", 15), ("build", 10), ("e2e", 10)) if k in g)
    pts += 10 * bool(info["ci"]) + 5 * (r / "CLAUDE.md").exists() + 5 * (r / AE / "policy.json").exists()
    info["readiness"] = pts
    return info


def cmd_scan(a):
    i = scan(a.repo)
    if a.json: print(json.dumps(i, indent=2)); return 0
    print(f"Stacks     : {', '.join(i['stacks']) or 'unknown'}")
    for k in ("typecheck", "lint", "unit", "build", "e2e"):
        print(f"  {k:<10}: {i['gates'].get(k, '-')}")
    print(f"CI         : {', '.join(i['ci']) or 'none'}")
    print(f"Protected  : {', '.join(i['protected'])}")
    for n in i["notes"]: print(f"! {n}")
    print(f"Agent-readiness: {i['readiness']}/100")
    return 0


# ---------------------------------------------------------------- init
def cmd_init(a):
    r = Path(a.repo).resolve(); i = scan(r)
    if git(r, "rev-parse", "--git-dir")[0]: die("not a git repository")
    minrisk = {"typecheck": "low", "lint": "low", "unit": "low", "build": "medium", "e2e": "high"}
    jsave(r / AE / "project.json", i)
    jsave(r / AE / "verification.json", {"gates": {k: {"cmd": c, "min_risk": minrisk[k]} for k, c in i["gates"].items()},
                                        "review": True})
    pol = {"always_allow": list(i["gates"].values()) + ["git diff", "git status", "git log"],
           "ask": ["git push", "database migration", "new dependency", "edit CI", "auth changes"],
           "protected": i["protected"], "never_read": [".env*", "*.pem", "id_rsa*", ".ssh/**"],
           "never_commands": ["git push --force", "git push -f", "rm -rf /", "rm -rf ~", "curl | sh", "| bash",
                              "git push origin main", "git push origin master", "--no-verify"]}
    jsave(r / AE / "policy.json", pol)
    lines = ["# Project rules (generated by Harness; keep short)", "",
             f"- Stack: {', '.join(i['stacks']) or 'see repo'}", "- Verify before claiming done. Commands:"]
    lines += [f"  - {k}: `{c}`" for k, c in i["gates"].items()]
    lines += ["- Never edit protected paths: " + ", ".join(i["protected"]),
              "- Work only inside the task worktree; never push to main/master.",
              "- Done = all gates in the task contract (.ai-engineering/tasks/) pass, not 'looks right'."]
    md = "\n".join(lines) + "\n"
    dst = r / ("CLAUDE.md" if not (r / "CLAUDE.md").exists() or a.force else "CLAUDE.md.proposed")
    dst.write_text(md)
    me = str(Path(__file__).resolve())
    sp = r / ".claude" / "settings.json"
    st = jload(sp) if sp.exists() else {}
    perm = st.setdefault("permissions", {})
    perm["allow"] = sorted(set(perm.get("allow", []) + [f"Bash({c})" for c in pol["always_allow"]]))
    perm["deny"] = sorted(set(perm.get("deny", []) + [f"Read(./{p})" for p in pol["never_read"]]))
    hook = {"matcher": "Edit|Write|MultiEdit|Bash|Read",
            "hooks": [{"type": "command", "command": f'python3 "{me}" guard'}]}
    pre = [h for h in st.setdefault("hooks", {}).get("PreToolUse", []) if "harness" not in json.dumps(h) and " guard" not in json.dumps(h)]
    st["hooks"]["PreToolUse"] = pre + [hook]
    jsave(sp, st)
    print(f"Initialized {AE}/, .claude/settings.json and {dst.name} (review with `git diff`).")
    return 0


# ---------------------------------------------------------------- guard (Claude Code PreToolUse hook)
def cmd_guard(a):
    try: ev = json.load(sys.stdin)
    except Exception: return 0
    cwd = Path(ev.get("cwd") or os.getcwd()); root = find_root(cwd)
    if not root: return 0
    pol = jload(root / AE / "policy.json"); ti = ev.get("tool_input") or {}; tool = ev.get("tool_name", "")
    why = None
    fp = ti.get("file_path") or ti.get("path")
    if fp:
        ap = Path(fp) if os.path.isabs(fp) else cwd / fp
        rel = os.path.relpath(os.path.abspath(ap), root)
        if any(rel.endswith(s) for s in SAFE_ENV): pass
        elif hit(rel, pol["never_read"]): why = f"{rel} is a secret path"
        elif tool in WRITE and hit(rel, pol["protected"]): why = f"{rel} is a protected path"
    c = ti.get("command")
    if c and not why:
        for n in pol["never_commands"]:
            if n in c: why = f"command contains forbidden pattern '{n}'"
        cc = c
        for s in SAFE_ENV: cc = cc.replace(s, "")
        for p in pol["never_read"]:
            t = p.rstrip("*").rstrip("/*")
            if t and t in cc and not why: why = f"command touches secret path '{t}'"
    with open(root / AE / "audit.log", "a") as f:
        f.write(json.dumps({"t": int(time.time()), "tool": tool, "target": fp or c, "blocked": bool(why), "why": why}) + "\n")
    if why:
        print(f"Harness policy blocked this action: {why}.", file=sys.stderr); return 2
    return 0


# ---------------------------------------------------------------- task
def tdir(r): return r / AE / "tasks"


def cmd_start(a):
    r = find_root(a.repo)
    if not r: die("run `harness init` first")
    wt = r.parent / ".harness-worktrees" / f"{r.name}-{a.name}"; br = f"harness/{a.name}"
    base = git(r, "rev-parse", "HEAD")[1]
    rc, out, _ = git(r, "worktree", "add", "-b", br, str(wt))
    if rc: die(out)
    for p in (AE, ".claude", "CLAUDE.md"):
        s, d = r / p, wt / p
        if s.exists() and not d.exists():
            if s.is_dir(): shutil.copytree(s, d, ignore=shutil.ignore_patterns("tasks", "evidence", "audit.log"))
            else: shutil.copy2(s, d)
    v = jload(r / AE / "verification.json"); pol = jload(r / AE / "policy.json")
    gates = {k: g for k, g in v["gates"].items() if LVL[g["min_risk"]] <= LVL[a.risk]}
    con = {"name": a.name, "goal": a.goal, "accept": a.accept or [], "risk": a.risk, "branch": br, "worktree": str(wt),
           "base": base, "allowed": a.allow or ["**"], "protected": pol["protected"], "gates": gates,
           "review": v.get("review", True) and a.risk != "low", "created": int(time.time())}
    jsave(tdir(r) / f"{a.name}.json", con)
    print(f"Worktree : {wt}\nBranch   : {br}\nGates    : {', '.join(gates) or 'none (!)'}")
    print(f"Next     : harness task run {a.name}   |   harness verify {a.name}")
    return 0


def load_task(a):
    r = find_root(a.repo)
    if not r: die("run `harness init` first")
    p = tdir(r) / f"{a.name}.json"
    if not p.exists(): die(f"no such task: {a.name}")
    return r, jload(p)


def cmd_run(a):
    r, c = load_task(a)
    if not shutil.which("claude"): die("`claude` CLI not found; work in the worktree manually, then `harness verify`.")
    prompt = (f"Goal: {c['goal']}\nAcceptance criteria:\n" + "\n".join(f"- {x}" for x in c["accept"]) +
              "\nFirst write a short plan, then implement. Do not touch protected paths. Before finishing, run: " +
              "; ".join(g["cmd"] for g in c["gates"].values()) + ". Do not claim completion while any fails.")
    return sh(["claude", "-p", prompt, "--permission-mode", "acceptEdits"], c["worktree"], timeout=3600)[0]


def review(c):
    if not shutil.which("claude"): return None, "claude CLI unavailable; review skipped"
    d = git(c["worktree"], "diff", c["base"])[1][:40000]
    p = ("You are an independent code reviewer. Review this diff against the goal and acceptance criteria. "
         f"Goal: {c['goal']}\nCriteria: {c['accept']}\nList concrete defects only. End with 'VERDICT: PASS' or 'VERDICT: FAIL'.\n\n{d}")
    rc, out, t = sh(["claude", "-p", p], c["worktree"], timeout=900)
    return ("VERDICT: PASS" in out and rc == 0), out[-1500:]


def cmd_verify(a):
    r, c = load_task(a); wt = c["worktree"]; res = []
    for k, g in c["gates"].items():
        rc, out, t = sh(g["cmd"], wt)
        res.append({"name": k, "cmd": g["cmd"], "ok": rc == 0, "secs": t, "tail": out[-1200:], "required": True})
    ch = set(git(wt, "diff", "--name-only", c["base"], "HEAD")[1].split())
    for ln in git(wt, "status", "--porcelain")[1].splitlines(): ch.add(ln[3:].split(" -> ")[-1])
    ch = sorted(f for f in ch if f and not f.startswith((AE, ".claude", "CLAUDE.md")))
    bad = [f for f in ch if hit(f, c["protected"]) or not hit(f, c["allowed"])]
    res.append({"name": "scope", "cmd": "changed files within contract", "ok": not bad, "secs": 0,
                "tail": ("violations: " + ", ".join(bad)) if bad else f"{len(ch)} files in scope", "required": True})
    if c["review"]:
        ok, out = review(c)
        res.append({"name": "independent-review", "cmd": "claude -p reviewer", "ok": bool(ok), "secs": 0,
                    "tail": out, "required": True, "skipped": ok is None})
    stat = git(wt, "diff", "--shortstat", c["base"])[1]
    ok = all(x["ok"] for x in res if x["required"])
    ev = {"task": c["name"], "goal": c["goal"], "accept": c["accept"], "results": res, "files": ch,
          "stat": stat, "verdict": "PASS" if ok else "FAIL", "time": int(time.time())}
    jsave(r / AE / "evidence" / f"{c['name']}.json", ev)
    (r / AE / "evidence" / f"{c['name']}.html").write_text(render(ev))
    for x in res: print(f"{'✓' if x['ok'] else '✗'} {x['name']:<20} {x['secs']}s")
    print(f"\nVerdict: {ev['verdict']}   ({stat or 'no diff'})\nReport : {r / AE / 'evidence' / (c['name'] + '.html')}")
    return 0 if ok else 1


def render(e):
    rows = "".join(
        f"<details {'' if x['ok'] else 'open'}><summary class={'ok' if x['ok'] else 'bad'}>{'✓' if x['ok'] else '✗'} "
        f"{html.escape(x['name'])} <small>{x['secs']}s · {html.escape(x['cmd'])}</small></summary>"
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


def cmd_pr(a):
    r, c = load_task(a); ep = r / AE / "evidence" / f"{c['name']}.json"
    if not ep.exists() or jload(ep)["verdict"] != "PASS": die("no passing evidence; run `harness verify` first")
    wt = c["worktree"]
    git(wt, "add", "-A", ":!" + AE, ":!.claude", ":!CLAUDE.md")
    git(wt, "commit", "-m", f"{c['goal']}\n\nVerified by Harness ({c['name']}).")
    rc, out, _ = git(wt, "push", "-u", "origin", c["branch"])
    if rc: die(out)
    ev = jload(ep)
    body = "\n".join(f"- {'✓' if x['ok'] else '✗'} {x['name']}" for x in ev["results"]) + f"\n\n{ev['stat']}"
    return sh(["gh", "pr", "create", "--title", c["goal"], "--body", body, "--head", c["branch"]], wt)[0]


def main():
    p = argparse.ArgumentParser(prog="harness", description=__doc__)
    p.add_argument("--repo", default=".")
    s = p.add_subparsers(dest="c", required=True)
    x = s.add_parser("scan"); x.add_argument("--json", action="store_true"); x.set_defaults(f=cmd_scan)
    x = s.add_parser("init"); x.add_argument("--force", action="store_true"); x.set_defaults(f=cmd_init)
    s.add_parser("guard").set_defaults(f=cmd_guard)
    t = s.add_parser("task").add_subparsers(dest="t", required=True)
    x = t.add_parser("start"); x.add_argument("name"); x.add_argument("--goal", required=True)
    x.add_argument("--accept", action="append"); x.add_argument("--allow", action="append")
    x.add_argument("--risk", choices=list(LVL), default="medium"); x.set_defaults(f=cmd_start)
    x = t.add_parser("run"); x.add_argument("name"); x.set_defaults(f=cmd_run)
    x = s.add_parser("verify"); x.add_argument("name"); x.set_defaults(f=cmd_verify)
    x = s.add_parser("pr"); x.add_argument("name"); x.set_defaults(f=cmd_pr)
    a = p.parse_args(); sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
