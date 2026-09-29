import subprocess
import zipfile
from pathlib import Path

from helpers import REPO_ROOT


def test_wheel_builds_with_console_script(tmp_path: Path) -> None:
    """Install-smoke automation (§9 DoD): the distributable wheel a clean
    install consumes is well-formed and ships the `harness` entry point.
    Full `uv pip install` of the wheel needs PyPI, so this proves the
    offline-checkable part; scripts/smoke.sh proves the installed CLI."""
    subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, wheels
    with zipfile.ZipFile(wheels[0]) as z:
        names = z.namelist()
        ep = next(n for n in names if n.endswith("entry_points.txt"))
        text = z.read(ep).decode()
        assert "[console_scripts]" in text and "harness = harness.cli:main" in text, text
        assert "harness/cli.py" in names
        dist = ep.rsplit("/", 1)[0]
        assert {f"{dist}/RECORD", f"{dist}/WHEEL", f"{dist}/METADATA"} <= set(names)


def test_smoke_script_matches_readme_block() -> None:
    """The §3/README command block and scripts/smoke.sh must not drift."""
    readme = (REPO_ROOT / "README.md").read_text()
    smoke = (REPO_ROOT / "scripts" / "smoke.sh").read_text()
    for verb in ("scan", "init", "ci", "task start", "task update", "task list", "verify", "serve"):
        assert f"harness {verb}" in readme or f"`{verb}`" in readme or verb in readme, verb
        assert f'"$h" {verb}' in smoke, verb
