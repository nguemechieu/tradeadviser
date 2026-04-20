#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/code-quality}"
PYTHON_BIN="${PYTHON_BIN:-python}"
CACHE_DIR="$ROOT_DIR/tmp/pytest-cache"
BASE_TEMP="$ROOT_DIR/tmp/pytest-basetemp-$$"

mkdir -p "$REPORT_DIR" "$CACHE_DIR" "$BASE_TEMP"

cd "$ROOT_DIR"

{
  echo "==> Running pytest with coverage"
  "$PYTHON_BIN" -m pytest src/tests \
    --override-ini="cache_dir=$CACHE_DIR" \
    --basetemp="$BASE_TEMP" \
    --cov=src \
    --cov-branch \
    --cov-report=term-missing:skip-covered \
    --cov-report="xml:$REPORT_DIR/coverage.xml" \
    --cov-report="html:$REPORT_DIR/htmlcov" \
    --cov-report="json:$REPORT_DIR/coverage.json" \
    --junitxml="$REPORT_DIR/pytest-junit.xml" \
    --cov-fail-under=80
} 2>&1 | tee "$REPORT_DIR/test-report.txt"
