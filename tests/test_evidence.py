import hashlib
from pathlib import Path

from harness import evidence
from harness.evidence import archive_shots, render

PNG = b"\x89PNG fake bytes, tests only"
E2E_GATES = {"pw": {"cmd": "x", "min_risk": "low", "type": "e2e"}}


def sample(**kw):
    base = {"task": "t", "goal": "g", "accept": ["a"],
            "results": [{"name": "browser", "cmd": "x", "ok": True, "secs": 1.0, "tail": "t", "required": True}],
            "files": ["src/a.py"], "stat": "1 file", "verdict": "PASS", "time": 0}
    return {**base, **kw}


def test_archive_shots_hashes_and_copies(tmp_path: Path):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    p = wt / "web" / "test-results" / "demo-a" / "test-passed-1.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(PNG)
    recs = archive_shots(root, "t", str(wt), E2E_GATES)
    assert len(recs) == 1
    r = recs[0]
    assert r["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert r["file"] == f"shots/{r['sha256'][:12]}-demo-a-test-passed-1.png"
    assert (root / ".ai-engineering" / "evidence" / "t" / r["file"]).read_bytes() == PNG
    assert (r["test"], r["gate"], r["bytes"]) == ("demo-a", "pw", len(PNG))


def test_archive_shots_rerun_prunes_stale(tmp_path: Path):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    p = wt / "test-results" / "a" / "one.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(PNG)
    archive_shots(root, "t", str(wt), E2E_GATES)
    p.unlink()
    stale = root / ".ai-engineering" / "evidence" / "t" / "shots" / "orphan.png"
    stale.write_bytes(PNG)
    assert archive_shots(root, "t", str(wt), E2E_GATES) == []
    assert not stale.exists()


def test_archive_shots_noop_without_e2e_type(tmp_path: Path):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    p = wt / "test-results" / "a" / "one.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(PNG)
    assert archive_shots(root, "t", str(wt), {"u": {"cmd": "x", "min_risk": "low"}}) == []
    assert not (root / ".ai-engineering" / "evidence" / "t").exists()


def test_archive_shots_caps_and_skips_oversized(tmp_path: Path, monkeypatch):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    d = wt / "test-results" / "a"
    d.mkdir(parents=True)
    for i in range(3):
        (d / f"{i}.png").write_bytes(PNG)
    monkeypatch.setattr(evidence, "MAX_SHOTS_PER_GATE", 2)
    assert len(archive_shots(root, "t", str(wt), E2E_GATES)) == 2
    monkeypatch.setattr(evidence, "MAX_SHOT_BYTES", 8)
    assert archive_shots(root, "t", str(wt), E2E_GATES) == []


def test_archive_shots_ignores_non_images(tmp_path: Path):
    root, wt = tmp_path / "repo", tmp_path / "wt"
    d = wt / "test-results" / "a"
    d.mkdir(parents=True)
    (d / "trace.zip").write_bytes(PNG)
    (d / "ok.png").write_bytes(PNG)
    recs = archive_shots(root, "t", str(wt), E2E_GATES)
    assert [r["test"] for r in recs] == ["a"] and recs[0]["file"].endswith(".png")


def test_render_without_shots_has_no_section():
    assert "Screenshots" not in render(sample())


def test_render_screenshots_links_and_escaping():
    sha = "deadbeefcafe" + "0" * 52
    shots = [{"file": "shots/deadbeefcafe-x.png", "sha256": sha, "bytes": 3, "test": "<b>&x", "gate": "g"}]
    h = render(sample(shots=shots))
    assert 'href="shots/deadbeefcafe-x.png"' in h
    assert f"sha256 {sha[:16]}…" in h
    assert "&lt;b&gt;&amp;x" in h
