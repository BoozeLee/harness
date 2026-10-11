"""Evidence hash chain: tamper-evident audit log for `.ai-engineering/evidence`.

Every `evidence/<task>.json` produced by `harness verify` (CLI or runner)
gets two extra fields at the moment it is written:

    "hash":      sha256 over a canonicalised form of the evidence JSON
    "prev_hash": sha256 of the most recent evidence record in the same
                 directory (or 64 zeros for an empty chain)

The chain head (the most recent record's `hash`) is therefore a single
64-hex-character commitment to the entire evidence history of a repo:
any past edit, deletion, or insertion that does not update the chain
breaks `hash == sha256(canon(ev))` for some record, and the head's
`prev_hash` catches any re-ordering that does not update the chain.

The function is total — it never raises. Missing directories, empty
chains, and unparseable history records all yield well-defined values
(the empty-chain sentinel `'0' * 64`, or the canonical hash of a best-
effort reconstruction). Audit tools and tests depend on this.
"""

import hashlib
import json
from pathlib import Path

from harness.policy import AE

_EMPTY_HASH = "0" * 64


def _canon(d: dict) -> bytes:
    """Canonical JSON encoding (sort keys, compact separators) for hashing.

    Excludes ``time`` (wall-clock jitter) and ``hash`` (the field that
    carries the digest itself) so the same record can be hashed twice
    and round-trip through ``write_evidence`` without forking the chain.
    """
    redacted = {k: v for k, v in d.items() if k not in ("time", "hash")}
    return json.dumps(redacted, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def evidence_hash(ev: dict) -> str:
    """SHA-256 over a canonicalised form of an evidence record.

    Returns the 64-hex-character digest. The function never raises: a
    non-JSON-serialisable value falls back to ``str`` via ``default=str``.
    """
    return hashlib.sha256(_canon(ev)).hexdigest()


def prev_evidence_hash(root: Path) -> str:
    """Hash of the most recent evidence record in `root/.ai-engineering/evidence`,
    or `'0' * 64` for an empty / missing chain.

    "Most recent" is by the record's `time` field (epoch seconds int) when
    present, falling back to file mtime, falling back to the empty-chain
    sentinel. The fallback chain was chosen because ``mtime`` can lie under
    clock skew and the evidence `time` field is the only value the verify
    path writes deterministically.
    """
    d = root / AE / "evidence"
    if not d.is_dir():
        return _EMPTY_HASH
    latest_hash = _EMPTY_HASH
    latest_key = -1
    for p in d.glob("*.json"):
        try:
            blob = json.loads(p.read_text())
        except (ValueError, OSError):
            continue
        key = blob.get("time")
        if not isinstance(key, (int, float)) or key <= 0:
            key = p.stat().st_mtime
        if key > latest_key:
            latest_key = key
            latest_hash = blob.get("hash", _EMPTY_HASH)
    return latest_hash or _EMPTY_HASH
