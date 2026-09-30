"""P7 acceptance, offline: the eval machinery must be provably honest without a
provider. A fake no-op agent stands in for claude/codex — it writes nothing, so
`graded_pass=False` is the *expected* result and proves grading really reads the
worktree, not the prompt. The corpus itself is checked for self-consistency:
fixtures must start green (placeholder tests pass) or the comparison is void.
"""

import json
import subprocess
from pathlib import Path

from helpers import REPO_ROOT, harness


def _tasks() -> list[dict]:
    return json.loads((REPO_ROOT / "evals" / "tasks.json").read_text())["tasks"]


def test_eval_list_shows_the_matrix():
    r = harness(["eval", "list"], REPO_ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    for t in _tasks():
        assert t["id"] in r.stdout
    assert "python" in r.stdout and "typescript" in r.stdout
    assert "claude" in r.stdout and "codex" in r.stdout


def test_corpus_fixtures_start_green(tmp_path: Path):
    py = next(t for t in _tasks() if t["stack"] == "python")
    wd = tmp_path / "wd"
    subprocess.run(["cp", "-r", str(REPO_ROOT / "evals" / "fixtures" / py["id"]), wd], check=True)
    r = subprocess.run(["uv", "run", "pytest", "-q"], cwd=wd, capture_output=True, text=True,
                     timeout=180, check=False)
    assert r.returncode == 0, r.stdout[-800:]


def _clean_repo_copy(wd: Path) -> None:
    subprocess.run(["cp", "-r", str(REPO_ROOT / "evals"), str(wd / "evals")], check=True)
    subprocess.run(["cp", "-r", str(REPO_ROOT / "harness"), str(wd / "harness")], check=True)
    (wd / "pyproject.toml").write_text((REPO_ROOT / "pyproject.toml").read_text())
    for art in ("results.jsonl", "report.html"):
        p = wd / "evals" / art
        if p.exists():
            p.unlink()


def test_dry_run_produces_honest_metric_rows(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    _clean_repo_copy(wd)
    r = harness(["--repo", str(wd), "eval", "run", "--task", "wordcount",
                 "--agent", "claude", "--variant", "all", "--dry"], wd)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:]
    lines = (wd / "evals" / "results.jsonl").read_text().splitlines()
    assert len(lines) == 2, lines
    recs = [json.loads(x) for x in lines]
    by_variant = {x["variant"]: x for x in recs}
    assert set(by_variant) == {"raw", "harnessed"}
    for rec in by_variant.values():
        assert rec["agent"] == "fake" and rec["graded_pass"] is False, rec
        assert rec["agent_rc"] == 0 and rec["wall"] >= 0
        assert "scope_violations" in rec
    # honest comparison: with --risk medium the real independent-review gate runs
    # in the dry loop (fake claude emits no VERDICT line -> FAIL), so a
    # do-nothing agent can no longer reach verdict=PASS.
    assert by_variant["harnessed"]["verdict"] == "FAIL"
    assert "review_note" in by_variant["harnessed"]


def test_dry_run_full_matrix(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    _clean_repo_copy(wd)
    r = harness(["--repo", str(wd), "eval", "run", "--task", "dedup", "--dry"], wd)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:]
    lines = (wd / "evals" / "results.jsonl").read_text().splitlines()
    assert len(lines) == 4  # 2 agents x 2 variants
    keys = {(json.loads(x)["agent"], json.loads(x)["variant"]) for x in lines}
    assert ("fake", "raw") in keys and ("fake", "harnessed") in keys


def test_report_groups_and_escapes(tmp_path: Path):
    recs = [
        {"ts": 1, "task": "wordcount", "stack": "python", "agent": "claude", "variant": "raw",
         "dry": False, "graded_pass": True, "agent_rc": 0, "agent_wall": 12.0, "wall": 12.0,
         "verdict": None, "scope_violations": 2},
        {"ts": 2, "task": "wordcount", "stack": "python", "agent": "claude", "variant": "harnessed",
         "dry": False, "graded_pass": True, "agent_rc": 0, "agent_wall": 20.0, "wall": 20.0,
         "verdict": "PASS", "review_note": "<script>alert(1)</script>", "scope_violations": 0},
    ]
    (tmp_path / "evals").mkdir()
    (tmp_path / "evals" / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    r = harness(["--repo", str(tmp_path), "eval", "report"], tmp_path)
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "evals" / "report.html").read_text()
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "raw vs harnessed" in html
    assert html.count("<tr><td>raw") == 1 and ">1/1<" in html
    assert ">/1<" not in html  # raw rows show no fake gate counts
    assert "Content-Security-Policy" in html
