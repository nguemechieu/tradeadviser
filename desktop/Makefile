SHELL := bash
PYTHON ?= python
REPORT_DIR ?= reports/code-quality
SCRIPT_ENV = PYTHON_BIN="$(PYTHON)" REPORT_DIR="$(REPORT_DIR)"

.PHONY: lint format format-check type-check test security check-all

lint:
	$(SCRIPT_ENV) bash tools/lint.sh

format:
	$(SCRIPT_ENV) bash tools/format.sh

format-check:
	$(SCRIPT_ENV) bash tools/format.sh --check

type-check:
	$(SCRIPT_ENV) bash tools/type_check.sh

test:
	$(SCRIPT_ENV) bash tools/test.sh

security:
	$(SCRIPT_ENV) bash tools/security_scan.sh

check-all: format-check lint type-check test security
