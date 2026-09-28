import json
from pathlib import Path

from fastapi.testclient import TestClient
from helpers import harness

from harness.server import create_app

TOK = "test-token"
AUTH = {"Authorization": f"Bearer {TOK}"}


def client_for(repo: Path) -> TestClient:
    return TestClient(create_app(repo, TOK))


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
    assert v.status_code == 200 and v.json()["verdict"] == "PASS"
    rows = c.get("/api/tasks", headers=AUTH).json()
    assert rows == [{"name": "api", "risk": "low", "branch": "harness/api", "verdict": "PASS"}]
    ev = c.get("/api/evidence/api", headers=AUTH)
    assert ev.json()["verdict"] == "PASS"
    h = c.get("/api/evidence/api/html", headers=AUTH)
    assert h.headers["content-security-policy"] == "sandbox"
    assert "PASS" in h.text


def test_invalid_and_unknown_names(pyrepo: Path):
    c = client_for(pyrepo)
    assert c.get("/api/evidence/..%2f.secrets", headers=AUTH).status_code in (400, 404)
    assert c.post("/api/tasks", headers=AUTH,
                  json={"name": "ok; rm -rf", "goal": "x"}).status_code == 422
    assert c.post("/api/tasks/nope/verify", headers=AUTH).status_code == 404
    assert c.get("/api/policy", headers=AUTH).status_code == 404  # pyrepo not initialized
