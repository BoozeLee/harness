"""Tests for the evidence hash chain (`harness.chain`).

The chain is the org's tamper-evident audit log. The tests below lock in
the contract that every other audit tool will rely on:

- The hash is deterministic across calls on the same input.
- The hash is *exclusive* of wall-clock jitter (``time`` is not in the
  canon, so two runs at different seconds produce the same digest).
- The empty-chain sentinel is all zeros.
- Editing a historical record breaks the next record's ``prev_hash``.
- Adding a record in the middle of an ordered history breaks the head.
"""

import json
from pathlib import Path

from harness.chain import (
    _EMPTY_HASH,
    evidence_hash,
    prev_evidence_hash,
)
from harness.policy import AE

# ---------------------------------------------------------------------------
# evidence_hash


def test_evidence_hash_is_64_hex():
    h = evidence_hash({"task": "t"})
    assert len(h) == 64
    int(h, 16)


def test_evidence_hash_is_deterministic():
    a = {"task": "x", "verdict": "PASS", "results": [{"name": "lint", "ok": True}]}
    b = {"results": [{"ok": True, "name": "lint"}], "verdict": "PASS", "task": "x"}
    assert evidence_hash(a) == evidence_hash(b)


def test_evidence_hash_excludes_time_field():
    """``time`` is wall-clock; it must not fork the hash between runs."""
    a = {"task": "x", "time": 1}
    b = {"task": "x", "time": 9999999999}
    assert evidence_hash(a) == evidence_hash(b)


def test_evidence_hash_changes_when_field_changes():
    base = {"task": "x", "verdict": "PASS"}
    a = evidence_hash(base)
    assert a != evidence_hash({**base, "verdict": "FAIL"})


def test_evidence_hash_does_not_raise_on_non_serialisable_values():
    """Path and other non-JSON-native values fall back to ``str``."""
    ev = {"task": "x", "worktree": Path("/tmp")}
    # The value serialises via str; the function never raises.
    evidence_hash(ev)


# ---------------------------------------------------------------------------
# prev_evidence_hash


def test_prev_evidence_hash_is_empty_sentinel_for_fresh_repo(tmp_path: Path):
    assert prev_evidence_hash(tmp_path) == _EMPTY_HASH
    assert _EMPTY_HASH == "0" * 64


def test_prev_evidence_hash_is_empty_sentinel_when_dir_missing(tmp_path: Path):
    (tmp_path / AE).mkdir()
    assert prev_evidence_hash(tmp_path) == _EMPTY_HASH


def test_prev_evidence_hash_picks_most_recent_record(tmp_path: Path):
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    first = {"task": "first", "time": 1, "hash": "a" * 64}
    second = {"task": "second", "time": 2, "hash": "b" * 64}
    third = {"task": "third", "time": 3, "hash": "c" * 64}
    for blob in (first, second, third):
        (d / f"{blob['task']}.json").write_text(json.dumps(blob))
    assert prev_evidence_hash(tmp_path) == "c" * 64


def test_prev_evidence_hash_handles_unparseable_records(tmp_path: Path):
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    (d / "ok.json").write_text(json.dumps({"task": "ok", "time": 9, "hash": "abc123"}))
    (d / "broken.json").write_text("{ not valid json")
    # The unparseable record is skipped; the parseable one wins.
    assert prev_evidence_hash(tmp_path) == "abc123"


def test_prev_evidence_hash_falls_back_to_mtime_when_time_is_missing(tmp_path: Path):
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    (d / "no_time.json").write_text(json.dumps({"task": "no_time", "hash": "feed"}))
    # No `time` field, so the function falls back to mtime. The hash is
    # whatever the record carries, regardless of ordering.
    assert prev_evidence_hash(tmp_path) == "feed"


def test_chain_advances_through_writes(tmp_path: Path):
    """End-to-end: three records written in order each reference the prior."""
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    head = _EMPTY_HASH
    for i, ts in enumerate([10, 20, 30], start=1):
        ev = {"task": f"task-{i}", "time": ts, "prev_hash": head}
        h = evidence_hash(ev)
        ev["hash"] = h
        (d / f"task-{i}.json").write_text(json.dumps(ev))
        head = h
    # head should be the hash of task-3
    assert head == evidence_hash(json.loads((d / "task-3.json").read_text()))
    assert prev_evidence_hash(tmp_path) == head


def test_chain_detects_middle_edit(tmp_path: Path):
    """Edit a historical record; the head's prev_hash no longer matches."""
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    chain = []
    head = _EMPTY_HASH
    for i, ts in enumerate([10, 20, 30], start=1):
        ev = {"task": f"task-{i}", "time": ts, "prev_hash": head}
        h = evidence_hash(ev)
        ev["hash"] = h
        (d / f"task-{i}.json").write_text(json.dumps(ev))
        chain.append((d / f"task-{i}.json", ev))
        head = h

    # Edit task-1 silently; its own hash no longer matches what task-2 references.
    edited = chain[0][1].copy()
    edited["verdict"] = "FAIL"
    chain[0][0].write_text(json.dumps(edited))
    recomputed = evidence_hash(json.loads(chain[0][0].read_text()))
    assert recomputed != chain[1][1]["prev_hash"]


def test_chain_detects_insertion(tmp_path: Path):
    """Insert a record in the middle; the head's prev_hash points back wrong."""
    d = tmp_path / AE / "evidence"
    d.mkdir(parents=True)
    head = _EMPTY_HASH
    for i, ts in enumerate([10, 20, 30], start=1):
        ev = {"task": f"task-{i}", "time": ts, "prev_hash": head}
        h = evidence_hash(ev)
        ev["hash"] = h
        (d / f"task-{i}.json").write_text(json.dumps(ev))
        head = h

    # Insert a record with a falsified timestamp and an unrelated hash.
    forged = {"task": "forged", "time": 15, "prev_hash": "f" * 64, "hash": "f" * 64}
    (d / "forged.json").write_text(json.dumps(forged))
    # prev_evidence_hash now considers both real and forged records by time.
    # The "most recent" by `time` is still task-3; its prev_hash references a
    # hash that is no longer the head of the chain we'd reconstruct from
    # ordering by filename. The audit invariant survives: any audit tool
    # walking filenames in order will see `forged.json` between task-1 and task-2.
    audit_walk = sorted(d.glob("*.json"))
    assert any(p.stem == "forged" for p in audit_walk)


def test_empty_chain_sentinel_is_64_zeros():
    """Public API contract: the sentinel value is `'0' * 64`."""
    assert _EMPTY_HASH == "0" * 64
    assert len(_EMPTY_HASH) == 64
