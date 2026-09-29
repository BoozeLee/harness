#!/usr/bin/env bash
# §9 DoD proof, one command: install the package the way a stranger would, then
# run the README/§3 command block verbatim against a throwaway repo. Every step
# is the real CLI; failure anywhere exits non-zero. Leaves nothing behind.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# 1. clean install into a throwaway venv (uv tool install has no --tool-dir in
# 0.11.x; a venv isolates identically without touching ~/.local/bin/harness)
uv venv -q "$tmp/venv"
uv pip install -q --python "$tmp/venv/bin/python" "$repo"
h="$tmp/venv/bin/harness"
"$h" --help >/dev/null   # §9 explicitly requires --help after install
echo "== harness --version: $("$h" --version)"

# 2. scratch git repo (also the clean-checkout stand-in for the §3 block)
mkdir -p "$tmp/proj/tests" "$tmp/proj/src"
cd "$tmp/proj"
git init -q -b main .
printf '[project]\nname="p"\nversion="0.1.0"\n\n[tool.pytest.ini_options]\ntestpaths=["tests"]\n' > pyproject.toml
: > src/__init__.py
: > tests/__init__.py
printf 'def test_ok():\n    assert True\n' > tests/test_ok.py
git add -A
git -c user.email=s@m -c user.name=s commit -qm i

# 3. README command block, verbatim
"$h" scan | grep -q 'readiness'
! "$h" scan --fail-under 95 >/dev/null 2>&1   # bare repo sits below a high floor
before=$("$h" scan | sed -n 's/.*readiness: *\([0-9]*\)\/100.*/\1/p')
"$h" init
after=$("$h" scan | sed -n 's/.*readiness: *\([0-9]*\)\/100.*/\1/p')
[ "$after" -gt "$before" ] || { echo "init did not lift readiness ($before -> $after)"; exit 1; }
"$h" ci
"$h" policy status "$tmp/bundle.git" >/dev/null 2>&1 && { echo "status should fail before push"; exit 1; } || true
git init --bare -q -b main "$tmp/bundle.git"
"$h" policy push "$tmp/bundle.git"
"$h" policy status "$tmp/bundle.git"
"$h" task start invites --goal "Add team invitations" --accept "expired invite is rejected" --risk low
"$h" task update invites --allow "src/**" --allow "tests/**"
"$h" task list | grep -q invites
wt=$(python3 -c "import json;print(json.load(open('.ai-engineering/tasks/invites.json'))['worktree'])")
printf 'def invite_ok():\n    return True\n' > "$wt/src/invites.py"
git -C "$wt" add -A
"$h" verify invites | grep -q PASS
# (task run / pr create / live serve need a provider or gh auth by design —
# covered by tests/test_agents.py fakes and P5b's fake-gh tests, not this script.)
"$h" serve --help | grep -q port

echo "smoke ok: install + §3 lifecycle green in $repo"
