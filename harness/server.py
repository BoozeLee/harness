"""P1/P2 local API server: loopback-only, bearer token, a thin shell over the core.

The core (harness.*) stays the only writer of .ai-engineering state; every handler
here delegates to it. Core fatal errors arrive as die()/sys.exit, which must never
kill the server process, so all core calls go through SystemExit-safe wrappers.
P2 adds the async runner: verify/agent runs return 202 + run id and stream over SSE."""

import argparse
import asyncio
import contextlib
import io
import json
import re
import secrets
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator

from harness import __version__
from harness.agents import AGENTS
from harness.contract import cmd_start
from harness.policy import AE, LVL, jload, jsave
from harness.runner import TERMINAL, Runner, agent_argv, runs_db
from harness.scan import scan

NAME_CORE = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
NAME_RE = re.compile(rf"^{NAME_CORE}$")
# archived shot names: <sha12>-<slug>.<ext> — nothing else is fetchable
SHOT_CORE = r"[a-f0-9]{12}-[A-Za-z0-9._-]{1,90}\.(?:png|jpe?g)"
SHOT_NAME_RE = re.compile(rf"^{SHOT_CORE}$")
TOOLS = ("git", "gh", "claude", "codex", "node", "npm", "bun", "uv", "cargo", "go", "ruff", "mypy", "pytest", "playwright")


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


RUNID_RE = re.compile(r"^[0-9a-f]{16}$")


def _run_id(v: str) -> str:
    if not RUNID_RE.fullmatch(v):
        raise HTTPException(400, "invalid run id")
    return v


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


class AgentRun(BaseModel):
    agent: str = "claude"

    @field_validator("agent")
    @classmethod
    def _agent(cls, v: str) -> str:
        if v not in AGENTS:
            raise ValueError(f"agent must be one of {list(AGENTS)}")
        return v


def create_app(repo: Path, token: str, max_parallel: int = 2) -> FastAPI:
    # constructed once per app: the Runner owns its loop thread, so no running loop is needed here
    runner = Runner(repo, runs_db(repo), max_parallel=max_parallel)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await runner.shutdown()

    app = FastAPI(title="Harness API", version=__version__,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

    @app.middleware("http")
    async def bearer(request: Request, call_next):
        p = request.url.path
        # SSE and evidence shots are public: EventSource/img/link loads cannot send Authorization;
        # loopback-only, same output as terminal verify (§6)
        public = (p in ("/api/health", "/api/docs", "/api/openapi.json")
                  or re.fullmatch(r"/api/runs/[0-9a-f]{16}/events", p)
                  or re.fullmatch(rf"/api/evidence/{NAME_CORE}/shots/{SHOT_CORE}", p))
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

    def _task_rows() -> list[dict]:
        d = repo / AE / "tasks"
        rows = []
        for p in sorted(d.glob("*.json")) if d.is_dir() else []:
            c = _jload(p)
            ep = repo / AE / "evidence" / f"{c['name']}.json"
            rows.append({"name": c["name"], "risk": c["risk"], "branch": c["branch"],
                         "verdict": _jload(ep)["verdict"] if ep.exists() else "unverified"})
        return rows

    @app.get("/api/v1/projects")
    def projects():
        # a project is a repo bound to this server; one entry today, the list envelope
        # keeps a future multi-repo registry from breaking the API
        s = scan(repo)
        rows = _task_rows()
        npass = sum(1 for r in rows if r["verdict"] == "PASS")
        nfail = sum(1 for r in rows if r["verdict"] == "FAIL")
        proj = {"name": repo.name, "root": str(repo),
                "initialized": (repo / AE / "project.json").exists(),
                "stacks": s["stacks"], "gates": sorted(s["gates"]), "protected": s["protected"],
                "ci": s["ci"], "readiness": s["readiness"],
                "tasks": {"total": len(rows), "pass": npass, "fail": nfail,
                          "unverified": len(rows) - npass - nfail}}
        return {"schema_version": 1, "projects": [proj]}

    @app.get("/api/tasks")
    def tasks():
        return _task_rows()

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

    @app.post("/api/tasks/{name}/verify", status_code=202)
    async def verify(name: str, review: bool = True):
        _safe(name)
        cf = repo / AE / "tasks" / f"{name}.json"
        if not cf.exists():
            raise HTTPException(404, f"no such task: {name}")
        if not review:
            # review is contract state; the core stays the only writer, so amend via core schema
            c = _jload(cf)
            if c.get("review"):
                c["review"] = False
                jsave(cf, c)
        c = _jload(cf)
        run_id = await runner.create(name, "verify", ["verify", name], c["worktree"])
        return {"id": run_id, "events": f"/api/runs/{run_id}/events"}

    @app.post("/api/tasks/{name}/run", status_code=202)
    async def agent_run(name: str, body: AgentRun | None = None):
        _safe(name)
        cf = repo / AE / "tasks" / f"{name}.json"
        if not cf.exists():
            raise HTTPException(404, f"no such task: {name}")
        agent = body.agent if body else "claude"
        if not shutil.which(agent):
            raise HTTPException(409, f"{agent} CLI not found; cannot enqueue an agent run")
        c = _jload(cf)
        run_id = await runner.create(name, "agent", agent_argv(repo, name, agent), c["worktree"])
        return {"id": run_id, "events": f"/api/runs/{run_id}/events"}

    @app.get("/api/runs")
    async def runs():
        return await runner.recent()

    @app.get("/api/runs/{run_id}")
    async def run(run_id: str):
        r = await runner.get(_run_id(run_id))
        if not r:
            raise HTTPException(404, "no such run")
        return r

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request):
        rid = _run_id(run_id)
        if not await runner.get(rid):
            raise HTTPException(404, "no such run")

        async def stream():
            seq = 0
            while True:
                if await request.is_disconnected():
                    return
                events = await runner.events_after(rid, seq)
                done = False
                for e in events:
                    seq = e["seq"]
                    # end only once the terminal status EVENT has drained: the runs row
                    # flips terminal before those last events commit, so a row check could truncate the stream
                    if e["kind"] == "status" and e["payload"].get("status") in TERMINAL:
                        done = True
                    yield f"id: {seq}\nevent: {e['kind']}\ndata: {json.dumps(e['payload'])}\n\n"
                if done:
                    yield "event: end\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/runs/{run_id}/cancel", status_code=202)
    async def run_cancel(run_id: str):
        if not await runner.cancel(_run_id(run_id)):
            raise HTTPException(409, "run already finished or unknown")
        return {"cancelled": True}

    @app.get("/api/evidence/{name}")
    def evidence(name: str):
        return _jload_or_404(repo / AE / "evidence" / f"{_safe(name)}.json")

    @app.get("/api/evidence/{name}/html")
    def evidence_html(name: str):
        p = _jload_or_404(repo / AE / "evidence" / f"{_safe(name)}.json").get("task")
        hpath = repo / AE / "evidence" / f"{p}.html"
        if not hpath.exists():
            raise HTTPException(404, "no html report")
        # file:// links are relative (shots/…); under /api/… they would resolve wrongly → rewrite
        text = hpath.read_text().replace('href="shots/', f'href="/api/evidence/{p}/shots/')
        return HTMLResponse(text, headers={"Content-Security-Policy": "sandbox"})

    @app.get("/api/evidence/{name}/shots/{fname}")
    def evidence_shot(name: str, fname: str):
        _safe(name)
        if not SHOT_NAME_RE.fullmatch(fname):
            raise HTTPException(400, "invalid shot name")
        shots_dir = (repo / AE / "evidence" / name / "shots").resolve()
        p = (shots_dir / fname).resolve()
        if p.parent != shots_dir or not p.is_file():
            raise HTTPException(404, "no such shot")
        return FileResponse(p)

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
    uvicorn.run(create_app(r, token, max_parallel=getattr(a, "max_parallel", 2)),
                host=a.host, port=a.port, log_level="warning")
    return 0
