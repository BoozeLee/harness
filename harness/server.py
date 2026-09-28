"""P1 local API server: loopback-only, bearer token, a thin shell over the core.

The core (harness.*) stays the only writer of .ai-engineering state; every handler
here delegates to it. Core fatal errors arrive as die()/sys.exit, which must never
kill the server process, so all core calls go through SystemExit-safe wrappers."""

import argparse
import contextlib
import io
import json
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, field_validator

from harness import __version__
from harness.contract import cmd_start
from harness.policy import AE, LVL, jload
from harness.scan import scan
from harness.verify import cmd_verify

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TOOLS = ("git", "gh", "claude", "node", "npm", "bun", "uv", "cargo", "go", "ruff", "mypy", "pytest", "playwright")


def _version_of(tool: str) -> str | None:
    path = shutil.which(tool)
    if not path:
        return None
    for args in (["--version"], ["version"]):
        try:
            r = subprocess.run([path, *args], capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            lines = (r.stdout + r.stderr).strip().splitlines()
            return lines[0][:90] if lines else "present"
    return "present"


def _probe() -> dict[str, str | None]:
    return {t: _version_of(t) for t in TOOLS}


def _jload(p: Path) -> dict:
    try:
        return jload(p)
    except SystemExit as e:
        raise HTTPException(409, str(e.code or "schema error"))


def _run_core(fn, *args):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fn(*args)
    except SystemExit as e:
        raise HTTPException(400, str(e.code or "harness error"))
    return rc, buf.getvalue()


def _safe(name: str) -> str:
    if not NAME_RE.match(name):
        raise HTTPException(400, f"invalid task name: {name!r}")
    return name


class TaskCreate(BaseModel):
    name: str
    goal: str
    accept: list[str] = []
    allow: list[str] = []
    risk: str = "medium"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("name must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
        return v

    @field_validator("risk")
    @classmethod
    def _risk(cls, v: str) -> str:
        if v not in LVL:
            raise ValueError(f"risk must be one of {sorted(LVL)}")
        return v


def create_app(repo: Path, token: str) -> FastAPI:
    app = FastAPI(title="Harness API", version=__version__,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def bearer(request: Request, call_next):
        p = request.url.path
        public = p in ("/api/health", "/api/docs", "/api/openapi.json")
        if p.startswith("/api") and not public and request.headers.get("authorization") != f"Bearer {token}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"harness": __version__, "repo": str(repo), "tools": _probe()}

    @app.get("/api/scan")
    def scan_ep():
        return scan(repo)

    @app.get("/api/policy")
    def policy():
        return _jload_or_404(repo / AE / "policy.json")

    @app.get("/api/verification")
    def verification():
        return _jload_or_404(repo / AE / "verification.json")

    def _jload_or_404(p: Path) -> dict:
        if not p.exists():
            raise HTTPException(404, "not initialized: run `harness init`")
        return _jload(p)

    @app.get("/api/tasks")
    def tasks():
        d = repo / AE / "tasks"
        rows = []
        for p in sorted(d.glob("*.json")) if d.is_dir() else []:
            c = _jload(p)
            ep = repo / AE / "evidence" / f"{c['name']}.json"
            rows.append({"name": c["name"], "risk": c["risk"], "branch": c["branch"],
                         "verdict": _jload(ep)["verdict"] if ep.exists() else "unverified"})
        return rows

    @app.get("/api/tasks/{name}")
    def task(name: str):
        return _jload_or_404(repo / AE / "tasks" / f"{_safe(name)}.json")

    @app.post("/api/tasks", status_code=201)
    def start(body: TaskCreate):
        args = argparse.Namespace(name=body.name, goal=body.goal, accept=body.accept or None,
                                  allow=body.allow or None, risk=body.risk, repo=str(repo))
        rc, out = _run_core(cmd_start, args)
        if rc:
            raise HTTPException(400, out.strip() or "task start failed")
        return {"output": out, "contract": _jload(repo / AE / "tasks" / f"{body.name}.json")}

    @app.post("/api/tasks/{name}/verify")
    def verify(name: str):
        _safe(name)
        if not (repo / AE / "tasks" / f"{name}.json").exists():
            raise HTTPException(404, f"no such task: {name}")
        rc, out = _run_core(cmd_verify, argparse.Namespace(name=name, repo=str(repo)))
        ep = repo / AE / "evidence" / f"{name}.json"
        return {"rc": rc, "output": out, "verdict": _jload(ep)["verdict"] if ep.exists() else None}

    @app.get("/api/evidence/{name}")
    def evidence(name: str):
        return _jload_or_404(repo / AE / "evidence" / f"{_safe(name)}.json")

    @app.get("/api/evidence/{name}/html")
    def evidence_html(name: str):
        p = _jload_or_404(repo / AE / "evidence" / f"{_safe(name)}.json").get("task")
        hpath = repo / AE / "evidence" / f"{p}.html"
        if not hpath.exists():
            raise HTTPException(404, "no html report")
        return HTMLResponse(hpath.read_text(), headers={"Content-Security-Policy": "sandbox"})

    @app.get("/api/audit")
    def audit(blocked: bool = False):
        log = repo / AE / "audit.log"
        if not log.exists():
            return []
        events = []
        for line in log.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not blocked or e.get("blocked"):
                events.append(e)
        return events[-500:]

    return app


def cmd_serve(a) -> int:
    import uvicorn

    r = Path(a.repo).resolve()
    tf = r / AE / "serve.token"
    if tf.exists():
        token = tf.read_text().strip()
    else:
        token = secrets.token_urlsafe(24)
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text(token + "\n")
        tf.chmod(0o600)
    print(f"Harness API: http://{a.host}:{a.port}  repo: {r}  token file: {tf}  docs: /api/docs")
    uvicorn.run(create_app(r, token), host=a.host, port=a.port, log_level="warning")
    return 0
