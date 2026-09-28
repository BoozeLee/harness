"""Stack/gate detection and agent-readiness scoring."""

import json
from pathlib import Path
from typing import Any

from harness.policy import AE, SCHEMA


def scan(repo) -> dict:
    r = Path(repo).resolve()
    info: dict[str, Any] = {"root": str(r), "stacks": [], "gates": {}, "protected": [], "ci": [], "notes": []}
    g = info["gates"]
    if (r / "package.json").exists():
        d = json.loads((r / "package.json").read_text())
        s = d.get("scripts", {})
        deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
        pm = "pnpm" if (r / "pnpm-lock.yaml").exists() else "yarn" if (r / "yarn.lock").exists() else "npm"
        info["stacks"].append("node")
        for k, names in {"typecheck": ["typecheck", "type-check"], "lint": ["lint"],
                         "unit": ["test", "test:unit"], "build": ["build"],
                         "e2e": ["test:e2e", "e2e"]}.items():
            for n in names:
                if n in s:
                    g[k] = f"{pm} run {n}"
                    break
        info["stacks"] += [f for f in ("next", "react", "vue", "svelte", "express",
                                       "prisma", "playwright") if f in deps]
    py = [f for f in ("pyproject.toml", "requirements.txt", "setup.py") if (r / f).exists()]
    if py:
        txt = "".join((r / f).read_text(errors="ignore") for f in py).lower()
        info["stacks"].append("python")
        if "pytest" in txt or (r / "tests").is_dir():
            g.setdefault("unit", "python3 -m pytest -q")
        if "ruff" in txt or (r / "ruff.toml").exists():
            g.setdefault("lint", "ruff check .")
        if "mypy" in txt:
            g.setdefault("typecheck", "mypy .")
    if (r / "Cargo.toml").exists():
        info["stacks"].append("rust")
        g.setdefault("typecheck", "cargo check")
        g.setdefault("lint", "cargo clippy -- -D warnings")
        g.setdefault("unit", "cargo test")
    if (r / "go.mod").exists():
        info["stacks"].append("go")
        g.setdefault("lint", "go vet ./...")
        g.setdefault("unit", "go test ./...")
    if (r / "Makefile").exists():
        mk = (r / "Makefile").read_text(errors="ignore")
        for k, t in (("unit", "test"), ("lint", "lint"), ("build", "build"), ("typecheck", "typecheck")):
            if f"\n{t}:" in "\n" + mk:
                g.setdefault(k, f"make {t}")
    pro = [".env*", "*.pem", "id_rsa*", "secrets/**"]
    for d in ("infra/prod", "infrastructure/prod", "migrations", "prisma/migrations",
              "terraform", ".github/workflows"):
        if (r / d).is_dir():
            pro.append(d + "/**")
    info["protected"] = pro
    wf = r / ".github" / "workflows"
    if wf.is_dir():
        info["ci"] = sorted(p.name for p in wf.glob("*.y*ml"))
    if not g.get("unit"):
        info["notes"].append("No test command detected: agents cannot prove correctness here.")
    if not info["ci"]:
        info["notes"].append("No CI workflows found.")
    if any(s in info["stacks"] for s in ("next", "react", "vue", "svelte")) and "e2e" not in g:
        info["notes"].append("Web UI detected without browser tests: add Playwright for UI verification.")
    pts = sum(w for k, w in (("unit", 30), ("lint", 15), ("typecheck", 15), ("build", 10), ("e2e", 10)) if k in g)
    pts += 10 * bool(info["ci"]) + 5 * (r / "CLAUDE.md").exists() + 5 * (r / AE / "policy.json").exists()
    info["readiness"] = pts
    info["schema_version"] = SCHEMA
    return info


def cmd_scan(a) -> int:
    i = scan(a.repo)
    if a.json:
        print(json.dumps(i, indent=2))
        return 0
    print(f"Stacks     : {', '.join(i['stacks']) or 'unknown'}")
    for k in ("typecheck", "lint", "unit", "build", "e2e"):
        print(f"  {k:<10}: {i['gates'].get(k, '-')}")
    print(f"CI         : {', '.join(i['ci']) or 'none'}")
    print(f"Protected  : {', '.join(i['protected'])}")
    for n in i["notes"]:
        print(f"! {n}")
    print(f"Agent-readiness: {i['readiness']}/100")
    return 0
