import json
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient
from helpers import harness

from harness.policy import jload, jsave
from harness.server import create_app

TOK = "test-token"
AUTH = {"Authorization": f"Bearer {TOK}"}


def client_for(repo: Path) -> TestClient:
    return TestClient(create_app(repo, TOK))


def wait_run(c: TestClient, run_id: str, want: str = "succeeded", secs: float = 90) -> dict:
    t0 = time.time()
    while time.time() - t0 < secs:
        row = c.get(f"/api/runs/{run_id}", headers=AUTH).json()
        if row["status"] in (want, "failed", "cancelled"):
            assert row["status"] == want, row
            return row
        time.sleep(0.15)
    raise AssertionError(f"run {run_id} still {row['status']} after {secs}s")


def test_health_is_public_and_probes_tools(pyrepo: Path):
    r = client_for(pyrepo).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["harness"]
    assert body["tools"]["git"] and "playwright" in body["tools"]


def test_other_endpoints_require_bearer(pyrepo: Path):
    c = client_for(pyrepo)
    assert c.get("/api/scan").status_code == 401
    assert c.get("/api/scan", headers=AUTH).status_code == 200
    assert json.loads(c.get("/api/scan", headers=AUTH).text)["schema_version"] == 1


def test_projects_endpoint_shape_and_auth(pyrepo: Path):
    c = client_for(pyrepo)
    assert c.get("/api/v1/projects").status_code == 401
    j = c.get("/api/v1/projects", headers=AUTH).json()
    assert j["schema_version"] == 1 and len(j["projects"]) == 1
    p = j["projects"][0]
    assert p["name"] == pyrepo.name and p["root"] == str(pyrepo)
    assert p["initialized"] is False
    assert "python" in p["stacks"] and "unit" in p["gates"]
    assert p["tasks"] == {"total": 0, "pass": 0, "fail": 0, "unverified": 0}


def test_projects_counts_track_task_lifecycle(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)

    def counts() -> dict:
        return c.get("/api/v1/projects", headers=AUTH).json()["projects"][0]["tasks"]

    assert c.get("/api/v1/projects", headers=AUTH).json()["projects"][0]["initialized"] is True
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "proj", "goal": "keep add", "risk": "low", "allow": ["src/**"]})
    assert r.status_code == 201
    assert counts() == {"total": 1, "pass": 0, "fail": 0, "unverified": 1}
    wait_run(c, c.post("/api/tasks/proj/verify", headers=AUTH).json()["id"])
    assert counts() == {"total": 1, "pass": 1, "fail": 0, "unverified": 0}


def test_task_create_verify_and_evidence_flow(pyrepo: Path):
    assert harness(["init"], pyrepo).returncode == 0
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "api", "goal": "add mul", "risk": "low", "allow": ["src/**"]})
    assert r.status_code == 201
    wt = Path(r.json()["contract"]["worktree"])
    (wt / "src" / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\n\n"
        "def mul(a: int, b: int) -> int:\n    return a * b\n")
    v = c.post("/api/tasks/api/verify", headers=AUTH)
    assert v.status_code == 202
    run_id = v.json()["id"]
    assert wait_run(c, run_id)["task"] == "api"
    rows = c.get("/api/tasks", headers=AUTH).json()
    assert rows == [{"name": "api", "risk": "low", "branch": "harness/api", "verdict": "PASS"}]
    ev = c.get("/api/evidence/api", headers=AUTH)
    assert ev.json()["verdict"] == "PASS"
    h = c.get("/api/evidence/api/html", headers=AUTH)
    assert h.headers["content-security-policy"] == "sandbox"
    assert "PASS" in h.text
    runs = c.get("/api/runs", headers=AUTH).json()
    assert [r["id"] for r in runs] == [run_id] and runs[0]["kind"] == "verify"


def test_sse_stream_is_public_and_complete(pyrepo: Path):
    harness(["init"], pyrepo)
    c = client_for(pyrepo)
    assert c.post("/api/tasks", headers=AUTH,
                  json={"name": "stream", "goal": "keep add", "risk": "low", "allow": ["src/**"]}).status_code == 201
    v = c.post("/api/tasks/stream/verify", headers=AUTH)
    run_id = v.json()["id"]
    with c.stream("GET", f"/api/runs/{run_id}/events") as s:  # no Authorization header: EventSource cannot send one
        assert s.status_code == 200
        assert s.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in s.iter_lines():
            if line.startswith("event: "):
                events.append(line[len("event: "):])
            if events and events[-1] == "end":
                break
        assert events.count("gate") >= 2, events[:6]
        assert "out" in events and "verdict" in events and "status" in events
    wait_run(c, run_id)


def test_cancel_kills_process_group(pyrepo: Path):
    harness(["init"], pyrepo)
    c = client_for(pyrepo)
    c.post("/api/tasks", headers=AUTH, json={"name": "slow", "goal": "sleepy", "risk": "low"})
    cf = pyrepo / ".ai-engineering" / "tasks" / "slow.json"
    con = jload(cf)
    con["gates"] = {"sleepy": {"cmd": "sleep 60", "min_risk": "low"}}
    jsave(cf, con)
    run_id = c.post("/api/tasks/slow/verify", headers=AUTH).json()["id"]
    t0 = time.time()
    while c.get(f"/api/runs/{run_id}", headers=AUTH).json()["status"] != "running" and time.time() - t0 < 30:
        time.sleep(0.1)
    r = c.post(f"/api/runs/{run_id}/cancel", headers=AUTH)
    assert r.status_code == 202
    wait_run(c, run_id, want="cancelled", secs=10)
    left = subprocess.run(["pgrep", "-f", "sleep 60"], capture_output=True, text=True, check=False)
    assert left.stdout.strip() == "", f"orphan survived PGID kill: {left.stdout}"


def test_e2e_shots_served_publicly_and_html_rewritten(pyrepo: Path):
    harness(["init"], pyrepo)
    c = client_for(pyrepo)
    r = c.post("/api/tasks", headers=AUTH,
               json={"name": "shot", "goal": "g", "risk": "low", "allow": ["src/**"]})
    assert r.status_code == 201
    cf = pyrepo / ".ai-engineering" / "tasks" / "shot.json"
    con = jload(cf)
    con["gates"] = {"browser": {"cmd": "mkdir -p web/test-results/demo-a && "
                              "head -c 64 /dev/urandom > web/test-results/demo-a/test-passed-1.png",
                              "min_risk": "low", "type": "e2e"}}
    jsave(cf, con)
    wait_run(c, c.post("/api/tasks/shot/verify", headers=AUTH).json()["id"])

    ev = c.get("/api/evidence/shot", headers=AUTH).json()
    fname = Path(ev["shots"][0]["file"]).name
    s = c.get(f"/api/evidence/shot/shots/{fname}")  # no auth: img/link loads cannot send one
    assert s.status_code == 200 and s.headers["content-type"].startswith("image/png")
    assert c.get("/api/evidence/shot/shots/0123456789ab-gone.png").status_code == 404
    for bad in ("zzzz-nope.png", "..%2F..%2Fserve.token"):
        assert c.get(f"/api/evidence/shot/shots/{bad}").status_code in (400, 401)
    h = c.get("/api/evidence/shot/html", headers=AUTH)
    assert h.headers["content-security-policy"] == "sandbox"
    assert f'href="/api/evidence/shot/shots/{fname}"' in h.text


def test_invalid_and_unknown_names(pyrepo: Path):
    c = client_for(pyrepo)
    assert c.get("/api/evidence/..%2f.secrets", headers=AUTH).status_code in (400, 404)
    assert c.post("/api/tasks", headers=AUTH,
                  json={"name": "ok; rm -rf", "goal": "x"}).status_code == 422
    assert c.post("/api/tasks/nope/verify", headers=AUTH).status_code == 404
    assert c.post("/api/tasks/nope/run", headers=AUTH, json={"agent": "bogus"}).status_code == 422
    assert c.get("/api/policy", headers=AUTH).status_code == 404  # pyrepo not initialized
