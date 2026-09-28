from pathlib import Path

import pytest
from helpers import gcmd


@pytest.fixture
def pyrepo(tmp_path: Path) -> Path:
    """Committed git repo with a python stack whose gates pass, deliberately without
    a .gitignore so generated artifacts must be filtered by the harness itself."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="0.1.0"\n\n'
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\n\n[tool.ruff]\nline-length=100\n\n[tool.mypy]\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "src" / "calc.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_calc.py").write_text(
        "def test_add():\n    from src.calc import add\n    assert add(2, 3) == 5\n")
    (tmp_path / ".env").write_text("SECRET=1\n")
    gcmd(tmp_path, "init", "-q", "-b", "main")
    gcmd(tmp_path, "add", "-A")
    gcmd(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i")
    return tmp_path
