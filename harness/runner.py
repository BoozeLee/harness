"""P2 runner: async subprocess runs, streamed line-by-line into a rebuildable
SQLite index, cancellable by process group. The runs table is an execution
journal only — task contracts and evidence files stay the source of truth.

Runs execute on a dedicated event-loop thread so their lifetime is independent
of any request loop (uvicorn reloads and TestClient both recycle loops).

SSE (`/api/runs/{id}/events`) is loopback-only and served without the bearer
token because EventSource cannot set headers; the stream exposes exactly the
same output a terminal `harness verify` prints. See plan §6.
"""

import asyncio
import json
import os
import secrets
import sqlite3
import threading
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from harness.evidence import archive_shots
from harness.evidence import write as write_evidence
from harness.gitops import changed_files
from harness.policy import AE, hit, jload
from harness.shellx import git
from harness.verify import review

TERMINAL = ("succeeded", "failed", "cancelled")
KINDS = ("verify", "agent")


def _now() -> float:
    return time.time()


def _bad_scope(rel: str, c: dict) -> bool:
    return hit(rel, c["protected"]) or not hit(rel, c["allowed"])


class Runner:
    def __init__(self, root: Path, db_path: Path, max_parallel: int = 2):
        self.root = root
        self.db_path = db_path
        self._db_lock = threading.Lock()  # sqlite calls are sync and fast; shared by both loops
        self._sem = asyncio.Semaphore(max_parallel)  # touched only on the runner loop
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._wt: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="harness-runner", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------ plumbing

    def _submit(self, coro: Coroutine) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _call(self, coro: Coroutine) -> Any:
        return await asyncio.wrap_future(self._submit(coro))

    def _db(self, fn):
        with self._db_lock:
            first = not self.db_path.exists()
            con = sqlite3.connect(self.db_path, timeout=10)
            con.row_factory = sqlite3.Row
            try:
                if first:
                    con.executescript(
                        """
                        CREATE TABLE runs(
                          id TEXT PRIMARY KEY, task TEXT NOT NULL, kind TEXT NOT NULL,
                          status TEXT NOT NULL, argv TEXT NOT NULL, worktree TEXT NOT NULL,
                          created REAL NOT NULL, started REAL, ended REAL, exit_code INTEGER);
                        CREATE TABLE events(
                          run TEXT NOT NULL, seq INTEGER NOT NULL, t REAL NOT NULL,
                          kind TEXT NOT NULL, payload TEXT NOT NULL,
                          PRIMARY KEY(run, seq));
                        """
                    )
                    con.commit()
                return fn(con)
            finally:
                con.close()

    # ------------------------------------------------------------ public API (awaited from any loop)

    async def create(self, task: str, kind: str, argv: list[str], worktree: str) -> str:
        if kind not in KINDS:
            raise ValueError(f"unknown run kind: {kind}")
        return await self._call(self._create(task, kind, argv, worktree))

    async def get(self, run_id: str) -> dict | None:
        return await self._call(self._get(run_id))

    async def recent(self, limit: int = 50) -> list[dict]:
        return await self._call(asyncio.to_thread(
            self._db, lambda con: [dict(r) for r in con.execute(
                "SELECT * FROM runs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()]))

    async def events_after(self, run_id: str, seq: int) -> list[dict]:
        def go(con):
            rows = con.execute(
                "SELECT seq,kind,payload FROM events WHERE run=? AND seq>? ORDER BY seq", (run_id, seq)).fetchall()
            return [{"seq": r["seq"], "kind": r["kind"], "payload": json.loads(r["payload"])} for r in rows]
        return await self._call(asyncio.to_thread(self._db, go))

    async def cancel(self, run_id: str) -> bool:
        return await self._call(self._cancel(run_id))

    async def shutdown(self) -> None:
        await self._call(self._shutdown())
        self._loop.call_soon_threadsafe(self._loop.stop)

    # ------------------------------------------------------------ runner-loop internals

    async def _create(self, task: str, kind: str, argv: list[str], worktree: str) -> str:
        run_id = secrets.token_hex(8)

        def ins(con):
            con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (run_id, task, kind, "queued", " ".join(argv), worktree, _now(), None, None, None))
            con.commit()
        await asyncio.to_thread(self._db, ins)
        await self._emit(run_id, "status", {"status": "queued"})
        body = self._verify_run(run_id, task, worktree) if kind == "verify" else self._agent_run(run_id, argv, worktree)
        self._tasks[run_id] = self._loop.create_task(self._guarded(run_id, body))
        return run_id

    async def _guarded(self, run_id: str, body) -> None:
        try:
            await body
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 -- journal must always close; a crash may not strand a run in "running"
            await self._set(run_id, status="failed", ended=_now(), exit_code=1)
            await self._emit(run_id, "status", {"status": "failed", "error": f"{type(e).__name__}: {e}"})

    async def _get(self, run_id: str) -> dict | None:
        row = await asyncio.to_thread(
            self._db, lambda con: con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())
        return dict(row) if row else None

    async def _set(self, run_id: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)

        def go(con):
            con.execute(f"UPDATE runs SET {cols} WHERE id=?", (*fields.values(), run_id))
            con.commit()
        await asyncio.to_thread(self._db, go)

    async def _emit(self, run_id: str, kind: str, payload: dict) -> None:
        t = _now()

        def ins(con):
            seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE run=?", (run_id,)).fetchone()[0]
            con.execute("INSERT INTO events VALUES(?,?,?,?,?)", (run_id, seq, t, kind, json.dumps(payload)))
            con.commit()
        await asyncio.to_thread(self._db, ins)

    async def _cancel(self, run_id: str) -> bool:
        """SIGKILL the whole process group (claude spawns nested shells)."""
        run = await self._get(run_id)
        if not run or run["status"] in TERMINAL:
            return False

        ph = ",".join("?" * len(TERMINAL))

        def go(con):
            cur = con.execute(f"UPDATE runs SET status='cancelled', ended=? WHERE id=? AND status NOT IN ({ph})",
                              (_now(), run_id, *TERMINAL))
            con.commit()
            return cur.rowcount
        # atomic claim: a run may reach terminal between the read above and this write
        if not await asyncio.to_thread(self._db, go):
            return False
        proc = self._procs.get(run_id)
        if proc and proc.returncode is None:
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except (ProcessLookupError, PermissionError):
                pass
        task = self._tasks.get(run_id)
        if task:
            task.cancel()
        await self._emit(run_id, "status", {"status": "cancelled"})
        return True

    async def _shutdown(self) -> None:
        for t in self._tasks.values():
            t.cancel()

    async def _gate(self, run_id: str, cwd: str, cmd: str, env=None) -> tuple[bool, float, str]:
        t0 = _now()
        proc = await asyncio.create_subprocess_shell(
            cmd, cwd=cwd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            start_new_session=True)
        self._procs[run_id] = proc
        tail: list[str] = []
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            tail.append(line)
            if len(tail) > 60:
                tail.pop(0)
            await self._emit(run_id, "out", {"line": line})
        rc = await proc.wait()
        self._procs.pop(run_id, None)
        return rc == 0, round(_now() - t0, 1), "\n".join(tail)

    async def _verify_run(self, run_id: str, task: str, worktree: str) -> None:
        try:
            async with self._sem:
                lock = self._wt.setdefault(worktree, asyncio.Lock())  # one run per worktree (git index.lock)
                async with lock:
                    run = await self._get(run_id)
                    if not run or run["status"] != "queued":
                        return  # cancelled while waiting
                    await self._set(run_id, status="running", started=_now())
                    await self._emit(run_id, "status", {"status": "running"})
                    c = jload(self.root / AE / "tasks" / f"{task}.json", versioned=False)
                    wt = c["worktree"]
                    res = []
                    for k, g in c["gates"].items():
                        await self._emit(run_id, "gate", {"name": k, "state": "running", "cmd": g["cmd"]})
                        env = {**os.environ, "HARNESS_GATE_E2E": "1"} if g.get("type") == "e2e" else None
                        ok, secs, tail = await self._gate(run_id, wt, g["cmd"], env=env)
                        res.append({"name": k, "cmd": g["cmd"], "ok": ok, "secs": secs,
                                    "tail": tail[-1200:], "required": True})
                        await self._emit(run_id, "gate", {"name": k, "state": "done", "ok": ok, "secs": secs})
                    shots = await asyncio.to_thread(archive_shots, self.root, task, wt, c["gates"])
                    ch = changed_files(wt, c["base"])
                    bad = [f for f in ch if _bad_scope(f, c)]
                    res.append({"name": "scope", "cmd": "changed files within contract", "ok": not bad, "secs": 0,
                                "tail": ("violations: " + ", ".join(bad)) if bad else f"{len(ch)} files in scope",
                                "required": True})
                    await self._emit(run_id, "gate", {"name": "scope", "state": "done", "ok": not bad, "secs": 0})
                    if c["review"]:
                        await self._emit(run_id, "gate", {"name": "independent-review", "state": "running",
                                                          "cmd": "claude -p reviewer"})
                        ok, out = await asyncio.to_thread(review, c)
                        res.append({"name": "independent-review", "cmd": "claude -p reviewer", "ok": bool(ok),
                                    "secs": 0, "tail": out, "required": True, "skipped": ok is None})
                        await self._emit(run_id, "gate", {"name": "independent-review", "state": "done",
                                                          "ok": bool(ok)})
                    stat = git(wt, "diff", "--shortstat", c["base"])[1]
                    if not stat.strip():
                        stat = f"{len(ch)} untracked file(s) added" if ch else ""
                    passed = all(x["ok"] for x in res if x["required"])
                    ev = {"task": task, "goal": c["goal"], "accept": c["accept"], "results": res, "files": ch,
                          "stat": stat, "verdict": "PASS" if passed else "FAIL", "time": int(_now())}
                    if shots:
                        ev["shots"] = shots
                    await asyncio.to_thread(write_evidence, self.root, ev)
                    status = "succeeded" if passed else "failed"
                    await self._set(run_id, status=status, ended=_now(), exit_code=0 if passed else 1)
                    await self._emit(run_id, "verdict", {"verdict": ev["verdict"], "stat": stat})
                    await self._emit(run_id, "status", {"status": status})
        finally:
            self._tasks.pop(run_id, None)
            self._procs.pop(run_id, None)

    async def _agent_run(self, run_id: str, argv: list[str], worktree: str) -> None:
        try:
            async with self._sem:
                lock = self._wt.setdefault(worktree, asyncio.Lock())
                async with lock:
                    run = await self._get(run_id)
                    if not run or run["status"] != "queued":
                        return  # cancelled while waiting
                    await self._set(run_id, status="running", started=_now())
                    await self._emit(run_id, "status", {"status": "running"})
                    proc = await asyncio.create_subprocess_exec(
                        *argv, cwd=worktree, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT, start_new_session=True)
                    self._procs[run_id] = proc
                    assert proc.stdout is not None
                    async for raw in proc.stdout:
                        await self._emit(run_id, "out", {"line": raw.decode("utf-8", "replace").rstrip("\r\n")})
                    rc = await proc.wait()
                    status = "succeeded" if rc == 0 else "failed"
                    await self._set(run_id, status=status, ended=_now(), exit_code=rc)
                    await self._emit(run_id, "status", {"status": status})
        finally:
            self._procs.pop(run_id, None)
            self._tasks.pop(run_id, None)


def agent_argv(r: Path, task: str, agent: str = "claude") -> list[str]:
    """Headless agent invocation for a contract (same prompt as CLI `task run`)."""
    from harness.agents import agent_prompt, build_argv

    c = jload(r / AE / "tasks" / f"{task}.json")
    return build_argv(agent, agent_prompt(c))


def runs_db(r: Path) -> Path:
    return r / AE / "runs.sqlite"
