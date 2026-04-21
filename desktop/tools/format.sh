#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/code-quality}"
PYTHON_BIN="${PYTHON_BIN:-python}"
BLACK_WORKERS="${BLACK_WORKERS:-1}"
MODE="${1:-}"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"

if [[ "$MODE" == "--check" ]]; then
  {
    echo "==> Checking import order with isort"
    "$PYTHON_BIN" -m isort --check-only --diff src main.py
    echo
    echo "==> Checking code style with black"
    "$PYTHON_BIN" -m black --workers "$BLACK_WORKERS" --check --diff src main.py
  } 2>&1 | tee "$REPORT_DIR/format-report.txt"
else
  {
    echo "==> Sorting imports with isort"
    "$PYTHON_BIN" -m isort src main.py
    echo
    echo "==> Formatting code with black"
    "$PYTHON_BIN" -m black --workers "$BLACK_WORKERS" src main.py
  } 2>&1 | tee "$REPORT_DIR/format-report.txt"
fi
