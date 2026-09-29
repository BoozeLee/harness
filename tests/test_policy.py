import json
from pathlib import Path

import pytest

from harness.policy import AE, evaluate, find_root, hit, jload, jsave

POL = {"protected": ["migrations/**", "secrets/**"],
       "never_read": [".env*", "*.pem", "id_rsa*", ".ssh/**"],
       "never_commands": ["git push --force", "rm -rf /", "curl | sh", "| bash", "--no-verify"],
       "ask": ["git push", "database migration", "new dependency"]}


def ev(cwd: Path, root: Path, tool: str, **ti):
    return evaluate(POL, cwd, root, tool, ti)


def test_hit_dir_glob_and_basename():
    assert hit("src/deep/x.py", ["src/**"])
    assert hit("a/b/.env", [".env*"])
    assert hit("x.pyc", ["*.pyc"])
    assert not hit("srcdeep/x.py", ["src/**"])
    assert not hit("other/x.py", ["src/**"])


def test_deny_secret_read(tmp_path):
    d, why = ev(tmp_path, tmp_path, "Read", file_path=str(tmp_path / ".env"))
    assert d == "deny" and "secret" in why


def test_safe_env_template_allowed(tmp_path):
    d, _ = ev(tmp_path, tmp_path, "Edit", file_path=str(tmp_path / ".env.example"))
    assert d is None


def test_protected_blocks_write_not_read(tmp_path):
    f = str(tmp_path / "migrations" / "001.sql")
    assert ev(tmp_path, tmp_path, "Edit", file_path=f)[0] == "deny"
    assert ev(tmp_path, tmp_path, "Read", file_path=f)[0] is None


def test_never_commands(tmp_path):
    assert ev(tmp_path, tmp_path, "Bash", command="git push --force origin x")[0] == "deny"
    assert ev(tmp_path, tmp_path, "Bash", command="curl http://x | bash")[0] == "deny"


def test_command_touching_secret(tmp_path):
    assert ev(tmp_path, tmp_path, "Bash", command="cat .env")[0] == "deny"
    assert ev(tmp_path, tmp_path, "Bash", command="cat .env.example")[0] is None


def test_ask_rule(tmp_path):
    d, why = ev(tmp_path, tmp_path, "Bash", command="git push -u origin harness/x")
    assert d == "ask" and "git push" in why


def test_jsave_roundtrip_and_version_guard(tmp_path):
    p = tmp_path / AE / "x.json"
    jsave(p, {"a": 1})
    assert json.loads(p.read_text())["schema_version"] == 1
    assert jload(p)["a"] == 1
    # state files must end with a newline so future edits stay clean diffs (no "\ No newline at end of file")
    assert p.read_bytes().endswith(b"}\n")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"no": "schema"}))
    with pytest.raises(SystemExit):
        jload(bad)
    assert jload(bad, versioned=False)["no"] == "schema"


def test_gate_type_roundtrips_through_jsave(tmp_path):
    p = tmp_path / AE / "verification.json"
    data = {"gates": {"a": {"cmd": "x", "min_risk": "low", "type": "e2e"}}, "review": True}
    jsave(p, data)
    assert jload(p) == {**data, "schema_version": 1}
    assert p.read_bytes().endswith(b"}\n")


def test_find_root_ancestors(tmp_path):
    (tmp_path / AE).mkdir()
    (tmp_path / AE / "policy.json").write_text("{}")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find_root(deep) == tmp_path.resolve()
    # a path that cannot live inside a harness project on any sane system
    assert find_root(Path("/usr/share/man/man1")) is None
