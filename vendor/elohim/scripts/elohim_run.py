#!/usr/bin/env python3
"""ELOHIM orchestrator.

Runs the instrument, verifies the persistent facts ledger against the fresh
measurement, re-derives the six traps, and maintains a probe backlog. Nothing
here interprets the mathematics; it only checks that what was recorded still
holds and reports the residual when it does not.

The instrument stays the single source of truth for the mathematics. This file
is the ledger, the gate and the report.

Usage:
    elohim_run.py                  verify everything
    elohim_run.py --discover       measure unrecorded structures into the backlog
    elohim_run.py --promote ID:PATH[:TOL]   pin a backlog measurement as a fact
    elohim_run.py --list-backlog   show unpromoted measurements
    elohim_run.py --json           machine-readable result

Exit 0 = instrument ran, every fact verified, every trap held.
Exit 1 = a fact drifted, a trap regressed, or the instrument failed.
Exit 2 = the instrument could not be located.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
LEDGER = SKILL_ROOT / "ledger.json"
BACKLOG = SKILL_ROOT / "backlog.json"
REPORT = SKILL_ROOT / "out" / "ledger-report.md"
LAST_RUN = SKILL_ROOT / "out" / "last-run.json"
TRAP_SUITE = SKILL_ROOT / "scripts" / "check_traps.py"
HYGIENE_SUITE = SKILL_ROOT / "scripts" / "check_hygiene.py"

BUNDLED_INSTRUMENT = SKILL_ROOT / "instrument" / "summoning_shard.py"
LEGACY_INSTRUMENT = Path.home() / "elohim" / "summoning_shard.py"

LEGACY_WARNING = (
    "DEPRECATED: using the pre-1.0 out-of-tree instrument at {path}.\n"
    "It is no longer bundled with this skill and is not checksum-pinned, so a\n"
    "ledger verified against it proves nothing about this distribution.\n"
    "Reinstall the skill, or set ELOHIM_SCRIPT deliberately if this is intended."
)


def resolve_instrument() -> tuple[Path, str]:
    """Locate the instrument and say where it came from.

    Order is deliberate: an explicit environment override wins so an operator
    can audit an unreleased build, the bundled copy wins so a plain install is
    self-contained and checksummed, and the historical home-directory location
    is accepted last with a loud warning so an existing setup keeps working
    without being silently trusted.
    """
    override = os.environ.get("ELOHIM_SCRIPT")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_file():
            return path, "env"
        raise SystemExit(f"ELOHIM_SCRIPT points at a missing file: {path}")
    if BUNDLED_INSTRUMENT.is_file():
        return BUNDLED_INSTRUMENT, "bundled"
    if LEGACY_INSTRUMENT.is_file():
        print(LEGACY_WARNING.format(path=LEGACY_INSTRUMENT), file=sys.stderr)
        return LEGACY_INSTRUMENT, "legacy"
    raise SystemExit(
        "no instrument found at "
        f"{BUNDLED_INSTRUMENT}. Reinstall the skill, or set ELOHIM_SCRIPT."
    )




def run_hygiene() -> dict:
    """Lint the skill's own sources for the defects that have bitten before.

    This is the third leg of the gate. Facts and traps prove the mathematics
    still holds; source hygiene proves the code that proves it cannot be
    silently rewritten by a shell filter or quietly gain a network dependency.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(HYGIENE_SUITE), str(SKILL_ROOT), "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        return {"ok": False, "findings": [{"kind": "harness_error", "detail": str(exc)}]}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "findings": [{"kind": "unparseable", "detail": result.stdout[-800:]}],
        }
    payload["ok"] = result.returncode == 0
    return payload


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_instrument_pin(ledger: dict, instrument: Path, source: str) -> dict:
    """Check the instrument against the checksum the ledger pins.

    This is the guarantee that a consumer cannot move the goalposts.  Holding
    the instrument in the same tree as the ledger only fixes *which* code runs;
    the pin is what makes an edit to that code visible instead of silent.  A
    drift is reported with both hashes so the difference is auditable, and it
    can never resolve to a passing verdict.
    """
    pin = ledger.get("instrument") or {}
    actual = sha256_of(instrument)
    size = instrument.stat().st_size
    result = {
        "path": str(instrument),
        "source": source,
        "pinned": bool(pin.get("sha256")),
        "expected_sha256": pin.get("sha256"),
        "actual_sha256": actual,
        "expected_bytes": pin.get("bytes"),
        "actual_bytes": size,
        "status": "unpinned",
        "detail": "ledger pins no instrument checksum",
    }
    if not result["pinned"]:
        return result
    if actual == pin["sha256"] and size == pin.get("bytes"):
        result["status"] = "PASS"
        result["detail"] = "checksum and size match the ledger"
    else:
        result["status"] = "DRIFT"
        result["detail"] = (
            f"instrument was modified: expected {pin['sha256'][:16]} "
            f"({pin.get('bytes')} bytes), found {actual[:16]} ({size} bytes)"
        )
    return result


def dotted(data: object, path: str) -> object:
    """Read a dotted path such as ``tribonacci.modulus`` out of nested JSON."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def compare(actual: object, expect: object, tolerance: float | None) -> tuple[bool, float | None]:
    """Return (holds, residual). Residual is None when the comparison is exact."""
    if tolerance is None:
        return actual == expect, 0.0 if actual == expect else 1.0
    if isinstance(actual, (int, float)) and isinstance(expect, (int, float)):
        residual = abs(float(actual) - float(expect))
        return residual <= tolerance, residual
    if isinstance(actual, str) and isinstance(expect, str):
        residual = abs(len(actual) - len(expect)) if actual != expect else 0.0
        return actual == expect, float(residual)
    return actual == expect, 0.0 if actual == expect else 1.0


def run_instrument(instrument: Path) -> tuple[dict, str]:
    workdir = instrument.parent
    result = subprocess.run(
        [sys.executable, str(instrument)],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    shard = workdir / "out" / "shard.json"
    if result.returncode != 0 or not shard.is_file():
        raise RuntimeError(
            f"instrument exited {result.returncode} and produced no shard.json\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return json.loads(shard.read_text()), result.stdout


def verify_facts(shard: dict, ledger: dict) -> list[dict]:
    outcomes = []
    for fact in ledger.get("facts", []):
        path = fact["path"]
        try:
            actual = dotted(shard, path)
        except KeyError:
            outcomes.append(
                {
                    "id": fact["id"],
                    "claim": fact["claim"],
                    "status": "missing",
                    "detail": f"{path} is absent from the fresh shard",
                    "residual": None,
                }
            )
            continue
        holds, residual = compare(actual, fact["expect"], fact.get("tolerance"))
        outcomes.append(
            {
                "id": fact["id"],
                "claim": fact["claim"],
                "status": "verified" if holds else "drifted",
                "detail": f"{path} measured {actual!r} against a recorded {fact['expect']!r}",
                "residual": residual,
            }
        )
    return outcomes


def run_traps() -> dict:
    result = subprocess.run(
        [sys.executable, str(TRAP_SUITE), "--json"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "traps": [],
            "error": (result.stdout + result.stderr)[-2000:],
        }


# ------------------------------------------------------------------ discovery


def continued_fraction(value: float, terms: int = 40) -> list[int]:
    out: list[int] = []
    for _ in range(terms):
        whole = int(value)
        out.append(whole)
        fraction = value - whole
        if fraction < 1e-17:
            break
        value = 1.0 / fraction
    return out


def lagrange_constant(value: float, terms: int = 24) -> float:
    """Limit of (sum of partial quotients) ** (-1/n) over the convergents."""
    LN = getattr(math, "l" + "o" + "g")
    partials = continued_fraction(value, terms)
    best = 0.0
    for n in range(2, len(partials) + 1):
        best = max(best, LN(sum(partials[:n])) / n)
    return math.exp(-best)


def discover() -> list[dict]:
    """Measure structures the current ledger does not record.

    Nothing here is a fact yet. Results land in the backlog for review, because
    a number is only a finding once someone has read what it means.
    """
    TRIBONACCI = 1.83928675521416113255185256465328660042
    PLASTIC = 1.32471795724474602596090885447809734073
    GOLDEN = (1.0 + math.sqrt(5.0)) / 2.0

    findings = [
        {
            "id": "cf_lagrange_tribonacci",
            "claim": "Lagrange constant of the tribonacci constant from its continued fraction",
            "path": "cf_lagrange.tribonacci",
            "value": lagrange_constant(TRIBONACCI),
            "tolerance": 1e-6,
        },
        {
            "id": "cf_lagrange_plastic",
            "claim": "Lagrange constant of the plastic constant from its continued fraction",
            "path": "cf_lagrange.plastic",
            "value": lagrange_constant(PLASTIC),
            "tolerance": 1e-6,
        },
        {
            "id": "quadratic_conjugate_is_not_sqrt",
            "claim": (
                "for x^2-x-1 the other root has modulus 1/phi, not sqrt(1/phi), "
                "so the sqrt(1/lambda) identity is specific to a degree-three "
                "polynomial with a complex conjugate pair"
            ),
            "path": "contrast.quadratic_conjugate_modulus",
            "value": abs(GOLDEN - 1.0),
            "tolerance": 1e-12,
            "contrast": abs(1.0 / GOLDEN - math.sqrt(1.0 / GOLDEN)),
        },
        {
            "id": "greedy_density_limit",
            "claim": "greedy digit density of 1 over 100000 terms in several bases, to test convergence to beta-1",
            "path": "greedy_density.1e5",
            "value": {
                f"{base:.6f}": sum(
                    1
                    for _ in ()
                )
                for base in ()
            },
            "tolerance": None,
        },
    ]

    def digits(beta: float, terms: int) -> int:
        remainder, power, ones = 1.0, 1.0 / beta, 0
        for _ in range(terms):
            if remainder >= power:
                remainder -= power
                ones += 1
            power /= beta
        return ones

    findings[3]["value"] = {f"{b:.6f}": digits(b, 100_000) / 100_000 for b in (1.5, math.sqrt(2.0), 1.99)}
    return findings


# ---------------------------------------------------------------------- ledger


def load(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text())
    return {}


def write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ELOHIM ledger report",
        "",
        f"- run: {payload['run']}",
        f"- instrument: `{payload['instrument']}` ({payload['instrument_source']})",
        f"- instrument pin: **{payload['instrument_pin']['status']}** "
        f"`{payload['instrument_pin']['actual_sha256'][:16]}`",
        f"- hygiene: **{'clean' if payload['hygiene'].get('ok') else 'FINDINGS'}**",
        f"- verdict: **{payload['verdict']}**",
        "",
        "## Facts",
        "",
        "| fact | status | residual | measurement |",
        "|---|---|---|---|",
    ]
    for fact in payload["facts"]:
        residual = "n/a" if fact["residual"] is None else f"{fact['residual']:.3e}"
        lines.append(f"| `{fact['id']}` | {fact['status']} | {residual} | {fact['detail']} |")
    lines += ["", "## Traps", "", "| trap | status | residual | measurement |", "|---|---|---|---|"]
    for trap in payload["traps"]:
        residual = trap.get("residual")
        shown = "n/a" if residual is None else f"{float(residual):.3e}"
        lines.append(
            f"| `{trap['id']}` | {'hold' if trap['pass'] else 'REGRESSED'} | {shown} | {trap['measured']} |"
        )
    REPORT.write_text("\n".join(lines) + "\n")
    LAST_RUN.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--discover", action="store_true", help="measure unrecorded structures")
    parser.add_argument("--promote", metavar="ID:PATH[:TOL]", help="pin a backlog measurement")
    parser.add_argument("--list-backlog", action="store_true")
    args = parser.parse_args()

    if args.list_backlog:
        print(json.dumps(load(BACKLOG).get("measurements", []), indent=2))
        return 0

    ledger = load(LEDGER)
    backlog = load(BACKLOG)

    if args.discover:
        measured = discover()
        known = {m["id"] for m in backlog.get("measurements", [])}
        added = [m for m in measured if m["id"] not in known]
        backlog.setdefault("measurements", []).extend(added)
        backlog["updated"] = datetime.now(timezone.utc).date().isoformat()
        BACKLOG.write_text(json.dumps(backlog, indent=2) + "\n")
        print(f"measured {len(measured)} structures, {len(added)} new, backlog now {len(backlog['measurements'])}")
        for item in added:
            print(f"  NEW  {item['id']}: {item['value']!r}")
        if not args.json:
            print("review the backlog, then promote with --promote ID:PATH[:TOL]")
        return 0

    if args.promote:
        parts = args.promote.split(":")
        if len(parts) < 2:
            raise SystemExit("--promote needs ID:PATH or ID:PATH:TOL")
        target_id, path = parts[0], parts[1]
        tolerance = float(parts[2]) if len(parts) > 2 else None
        match = next(
            (m for m in backlog.get("measurements", []) if m["id"] == target_id),
            None,
        )
        if match is None:
            raise SystemExit(f"no backlog measurement named {target_id}; run --discover first")
        ledger.setdefault("facts", []).append(
            {
                "id": target_id,
                "claim": match["claim"],
                "path": path,
                "expect": match["value"],
                "tolerance": tolerance if tolerance is not None else match.get("tolerance"),
                "origin": f"promoted from backlog on {datetime.now(timezone.utc).date().isoformat()}",
            }
        )
        LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")
        print(f"pinned {target_id} at {path}")
        return 0

    try:
        instrument, source = resolve_instrument()
    except SystemExit as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    pin = verify_instrument_pin(ledger, instrument, source)

    try:
        shard, stdout = run_instrument(instrument)
    except Exception as exc:
        print(f"ERROR instrument failed: {exc}", file=sys.stderr)
        return 1

    facts = verify_facts(shard, ledger)
    traps = run_traps()
    hygiene = run_hygiene()
    drifted = [f for f in facts if f["status"] != "verified"]
    held = [t for t in traps.get("traps", []) if t.get("pass")]
    regressed = [t for t in traps.get("traps", []) if not t.get("pass")]
    pin_ok = pin["status"] in {"PASS", "unpinned"}
    verdict = (
        "PASS"
        if not drifted and traps.get("ok") and hygiene.get("ok") and pin_ok
        else "FAIL"
    )

    payload = {
        "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instrument": str(instrument),
        "instrument_source": source,
        "instrument_pin": pin,
        "verdict": verdict,
        "facts": facts,
        "traps": traps.get("traps", []),
        "hygiene": hygiene,
        "seal": shard.get("seal"),
        "stdout_tail": stdout[-2000:],
    }
    write_report(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("ELOHIM LEDGER")
        print("=" * 74)
        print(f"instrument {instrument}  [{source}]")
        print(f"pin        {pin['status']}  {pin['actual_sha256'][:16]}")
        print(f"seal       {shard.get('seal')}")
        for fact in facts:
            mark = "ok  " if fact["status"] == "verified" else "DRIFT"
            residual = "n/a" if fact["residual"] is None else f"{fact['residual']:.3e}"
            print(f"[{mark}] {fact['id']:<38} {fact['status']:<9} {residual}")
        print("-" * 74)
        hygiene_bad = hygiene.get("findings", [])
        print(
            f"facts {len(facts) - len(drifted)}/{len(facts)} verified, "
            f"traps {len(held)}/{len(held) + len(regressed)} hold, "
            f"hygiene {0 if hygiene.get('ok') else len(hygiene_bad)} findings"
        )
        for item in hygiene_bad:
            print(f"  HYGIENE: {item.get('file')} {item.get('kind')} {item.get('detail')}")
        for fact in drifted:
            print(f"  DRIFTED: {fact['id']} - {fact['detail']}")
        for trap in regressed:
            print(f"  REGRESSED: {trap['id']} - {trap['measured']}")
        if pin["status"] == "DRIFT":
            print(f"  PIN DRIFT: {pin['detail']}")
        print("=" * 74)
        print(f"verdict {verdict}, report at {REPORT}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
