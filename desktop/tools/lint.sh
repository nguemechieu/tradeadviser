#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/code-quality}"
PYTHON_BIN="${PYTHON_BIN:-python}"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"

{
  echo "==> Running flake8"
  "$PYTHON_BIN" -m flake8 src main.py
} 2>&1 | tee "$REPORT_DIR/lint-report.txt"
