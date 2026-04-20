# Code Quality

The project ships with a production-oriented code quality system that enforces formatting, linting, type checking, tests, and security scanning both locally and in GitHub Actions.

## Toolchain

- `flake8` for static analysis, including unused variables, undefined names, and complexity checks
- `black` plus `isort` for deterministic formatting and import ordering
- `mypy` for static type analysis
- `pytest` plus `pytest-cov` for test execution and coverage enforcement
- `bandit` for security scanning

## Local Usage

Install the development environment:

```bash
python -m pip install -r requirements.txt
```

Run the quality commands:

```bash
make format
make format-check
make lint
make type-check
make test
make security
make check-all
```

If `make` is unavailable, run the scripts directly:

```bash
bash tools/format.sh
bash tools/format.sh --check
bash tools/lint.sh
bash tools/type_check.sh
bash tools/test.sh
bash tools/security_scan.sh
```

## Quality Gates

- Formatting must already match `black` and `isort`
- Linting must pass with zero `flake8` violations
- Mypy must complete with zero type errors
- Test coverage must stay at or above 80 percent
- High-severity, high-confidence Bandit findings fail the security gate

## Reports

Generated reports are written to `reports/code-quality/`.

- `format-report.txt`
- `lint-report.txt`
- `type-check-report.txt`
- `mypy-junit.xml`
- `test-report.txt`
- `pytest-junit.xml`
- `coverage.xml`
- `coverage.json`
- `htmlcov/`
- `security-report.txt`
- `security-report.json`

## CI Integration

`.github/workflows/ci.yml` runs on every push and pull request. The workflow:

1. Creates the project environment from `environment.yml`
2. Verifies the quality toolchain
3. Runs formatting checks
4. Runs linting
5. Runs mypy
6. Runs pytest with the 80 percent coverage gate
7. Runs Bandit
8. Uploads the generated reports as build artifacts

## Optional Next Step

If you want maintainability scoring and centralized vulnerability dashboards, add a separate SonarQube workflow later. The current system is intentionally self-contained so it works immediately in local development and GitHub Actions.
