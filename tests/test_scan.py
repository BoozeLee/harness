import json
from pathlib import Path

from helpers import harness

from harness.policy import SCHEMA
from harness.scan import scan


def test_scan_python_gates(pyrepo: Path):
    i = scan(pyrepo)
    assert "python" in i["stacks"]
    assert set(i["gates"]) == {"unit", "lint", "typecheck"}
    assert i["schema_version"] == SCHEMA
    assert ".env*" in i["protected"]
    assert any("No CI" in n for n in i["notes"])


def test_scan_node_package_manager_and_scripts(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps(
        {"scripts": {"lint": "eslint .", "test": "vitest run", "build": "vite build"},
         "devDependencies": {"react": "^19.0.0"}}))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    i = scan(tmp_path)
    assert i["gates"]["lint"] == "pnpm run lint"
    assert i["gates"]["unit"] == "pnpm run test"
    assert "react" in i["stacks"]
    assert any("Playwright" in n for n in i["notes"])
    assert i["readiness"] == 15 + 30 + 10


def test_scan_protected_known_dirs(tmp_path: Path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (tmp_path / "prisma" / "migrations").mkdir(parents=True)
    i = scan(tmp_path)
    assert "prisma/migrations/**" in i["protected"]
    assert i["ci"] == ["ci.yml"]


def test_scan_fail_under_blocks_and_passes(pyrepo: Path):
    """pyrepo scores 60 bare (unit+lint+typecheck), 70 once init adds CLAUDE.md + policy."""
    assert scan(pyrepo)["readiness"] == 60
    blocked = harness(["scan", "--fail-under", "61"], pyrepo)
    assert blocked.returncode == 1
    assert "--fail-under" in blocked.stdout + blocked.stderr
    assert harness(["init"], pyrepo).returncode == 0
    assert scan(pyrepo)["readiness"] == 70
    assert harness(["scan", "--fail-under", "70"], pyrepo).returncode == 0
    assert harness(["scan", "--fail-under", "71"], pyrepo).returncode == 1


def test_scan_fail_under_still_emits_json(pyrepo: Path):
    blocked = harness(["scan", "--json", "--fail-under", "99"], pyrepo)
    assert blocked.returncode == 1
    assert json.loads(blocked.stdout)["readiness"] == 60
