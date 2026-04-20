#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/code-quality}"
PYTHON_BIN="${PYTHON_BIN:-python}"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"

"$PYTHON_BIN" -m bandit -r src -c bandit.yaml --exit-zero -f json -o "$REPORT_DIR/security-report.json"

{
  echo "==> Saved Bandit JSON report to $REPORT_DIR/security-report.json"
  echo "==> Enforcing the security gate (high-severity, high-confidence findings fail the build)"
  "$PYTHON_BIN" -m bandit -r src -c bandit.yaml -lll -iii
} 2>&1 | tee "$REPORT_DIR/security-report.txt"
