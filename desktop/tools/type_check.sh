#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/code-quality}"
PYTHON_BIN="${PYTHON_BIN:-python}"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"

{
  echo "==> Running mypy"
  "$PYTHON_BIN" -m mypy --config-file mypy.ini --junit-xml "$REPORT_DIR/mypy-junit.xml" -p src
} 2>&1 | tee "$REPORT_DIR/type-check-report.txt"
