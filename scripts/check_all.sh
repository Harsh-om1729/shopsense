#!/usr/bin/env bash
# Run every check. Add --rebuild to also rebuild everything from the raw data
# and confirm the API's answers are unchanged (about 30 seconds).
#
# Usage: scripts/check_all.sh [--rebuild]
set -euo pipefail

cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$1"; }

step "Backend lint and formatting"
uv run ruff check .
uv run ruff format --check .

step "Backend tests"
uv run pytest -q

step "Frontend type check, lint, tests, and build"
(
  cd frontend
  npm run typecheck
  npm run lint
  npm test
  npm run build
)

if [[ -f data/processed/shopsense.db && -f models/freight_cost/metadata.json ]]; then
  step "Browser tests against the real API and site"
  (cd frontend && npm run e2e)
else
  step "Browser tests skipped, because the database or packages aren't built"
fi

if [[ "${1:-}" == "--rebuild" ]]; then
  step "Full rebuild from raw data"
  uv run python -m scripts.rebuild_check
fi

step "All checks passed"
