from harness.evidence import render


def sample() -> dict:
    return {"task": "<b>ti</b>", "goal": "&amp", "accept": ['say "hi"'],
            "results": [{"name": "unit", "cmd": "pytest <x>", "ok": True, "secs": 1.0,
                         "tail": "<script>alert(1)</script>", "required": True},
                        {"name": "scope", "cmd": "scope check", "ok": False, "secs": 0,
                         "tail": "violations: a<b.py", "required": True}],
            "files": ["a<b.py"], "stat": "1 file changed", "verdict": "FAIL", "time": 0}


def test_render_escapes_every_untrusted_field():
    h = render(sample())
    assert "<script>alert(1)</script>" not in h
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in h
    assert "<b>ti</b>" not in h
    assert "a&lt;b.py" in h


def test_render_verdict_and_sections():
    h = render(sample())
    assert "FAIL" in h
    assert "Acceptance criteria" in h
    assert "say &quot;hi&quot;" in h
    assert "1 file changed" in h
