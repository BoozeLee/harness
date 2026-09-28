import subprocess
from pathlib import Path

from harness.gitops import changed_files, porcelain_paths
from harness.policy import AE
from harness.shellx import git


def test_porcelain_leading_space_is_path_data():
    # regression: sh() must not lstrip; column 0 encodes staged status
    assert porcelain_paths(" M src/calc.py\0?? tests/x.py\0") == ["src/calc.py", "tests/x.py"]


def test_porcelain_empty():
    assert porcelain_paths("") == []


def test_rename_keeps_destination(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "mv", "a.txt", "b.txt"], cwd=tmp_path, check=True)
    out = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=tmp_path,
                         capture_output=True, text=True, check=False).stdout
    paths = porcelain_paths(out)
    assert paths == ["b.txt"]


def test_changed_files_filters_meta_and_artifacts(pyrepo: Path):
    base = git(pyrepo, "rev-parse", "HEAD")[1]
    (pyrepo / "src" / "new.py").write_text("def n() -> int:\n    return 1\n")
    (pyrepo / "src" / "__pycache__").mkdir()
    (pyrepo / "src" / "__pycache__" / "junk.pyc").write_text("")
    (pyrepo / AE).mkdir()
    (pyrepo / AE / "x.json").write_text("{}")
    (pyrepo / ".claude").mkdir()
    ch = changed_files(pyrepo, base)
    assert "src/new.py" in ch
    assert not any("__pycache__" in f or f.startswith((AE, ".claude")) for f in ch)
