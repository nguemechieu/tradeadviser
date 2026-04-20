# Code Coverage Guide

TradeAdviser uses code coverage tools to track test completeness and code quality. Coverage metrics are collected automatically during CI/CD pipelines and reported to Codecov.

## Overview

| Tool | Language | Format | Storage |
|------|----------|--------|---------|
| **pytest-cov** | Python (Backend) | XML, HTML, JSON | Codecov + Artifacts |
| **Jest** | JavaScript (Frontend) | JSON | Codecov + Artifacts |
| **Codecov** | Both | Summary, Reports | codecov.io |

## Coverage Targets

- **Backend (Python)**: 70% minimum, 80% target
- **Frontend (JavaScript)**: 70% minimum, 80% target
- **Patch Coverage**: Minimum 80% for new code
- **Project Target**: 70% overall

## Local Coverage Reports

### Backend Coverage

```bash
cd backend
pytest --cov=app --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
```

**Output Files:**
- `coverage.xml` - XML format for CI/CD
- `coverage.json` - JSON format for tooling
- `htmlcov/` - HTML report for browser viewing

### Frontend Coverage

```bash
cd frontend
npm test -- --coverage

# View coverage summary
cat coverage/coverage-summary.json

# View detailed HTML report
open coverage/lcov-report/index.html  # macOS
start coverage/lcov-report/index.html # Windows
```

**Output Files:**
- `coverage/coverage-final.json` - JSON format for codecov
- `coverage/lcov.info` - LCOV format
- `coverage/lcov-report/` - HTML report

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# Backend
pytest tests/ -v --cov=app --cov-report=xml --cov-report=json

# Frontend
npm test -- --coverage

# Upload to Codecov
- uses: codecov/codecov-action@v3
```

### Codecov Configuration

Configuration file: `codecov.yml`

**Key Settings:**
```yaml
coverage:
  project:
    target: 70%      # Minimum coverage
  patch:
    target: 80%      # New code coverage
```

**Flags:**
- `backend` - Python code coverage
- `frontend` - JavaScript code coverage

## Viewing Coverage Reports

### 1. Codecov Dashboard

**Main URL:** https://codecov.io/gh/sopotek/tradeadviser

**Information Available:**
- Overall coverage percentage
- Coverage by file
- Coverage trends over time
- Commit-level coverage
- Pull request coverage comparisons

### 2. GitHub PR Comments

Codecov automatically comments on PRs with:
- ✅ Coverage increase/decrease
- 📊 New file coverage
- 🎯 Coverage percentage change
- 🔍 Recommendations

Example:
```
Coverage: 75.2% -> 77.8% (+2.6%)
Files Changed: 5 files
New Coverage: 85% (app/new_module.py)
```

### 3. GitHub Actions Artifacts

Coverage artifacts are uploaded after each test run:

```
backend/htmlcov/   - HTML coverage report
frontend/coverage/ - HTML coverage report
```

Download from GitHub Actions → Run Details → Artifacts

## Excluding Files from Coverage

### Backend (pytest)

In `backend/pyproject.toml` or pytest.ini:
```ini
[tool:pytest]
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
```

Or in test command:
```bash
pytest --cov=app --cov-report=xml --ignore=tests/integration/
```

### Frontend (Jest)

In `frontend/package.json`:
```json
{
  "jest": {
    "collectCoverageFrom": [
      "src/**/*.{js,jsx}",
      "!src/index.js",
      "!src/**/*.test.js",
      "!src/**/__tests__/**"
    ]
  }
}
```

## Coverage Quality Gates

### Project Coverage Status

- ✅ **Pass**: Coverage meets or exceeds project target (70%)
- ⚠️ **Warning**: Coverage within 5% of target
- ❌ **Fail**: Coverage below threshold

### Patch Coverage Status

- ✅ **Pass**: New code coverage ≥ 80%
- ⚠️ **Warning**: New code coverage 70-80%
- ❌ **Fail**: New code coverage < 70%

### GitHub Status Checks

Coverage checks appear in PR status:
- `codecov/project` - Project coverage
- `codecov/patch` - Patch coverage
- `codecov/changes` - Changed files coverage

## Improving Coverage

### 1. Identify Uncovered Code

**Backend:**
```bash
cd backend
pytest --cov=app --cov-report=term-missing
# Shows lines not covered: app/module.py:42-45
```

**Frontend:**
```bash
cd frontend
npm test -- --coverage
# Check coverage/lcov-report/index.html
```

### 2. Write Tests

**Backend Example:**
```python
def test_trade_calculation():
    """Test that trade calculation handles edge cases"""
    result = calculate_trade_pnl(100, 105, 1)
    assert result == 500  # 5 * 100
```

**Frontend Example:**
```javascript
test('calculates portfolio value correctly', () => {
  const portfolio = { holdings: [{ price: 100, quantity: 10 }] };
  expect(calculateValue(portfolio)).toBe(1000);
});
```

### 3. Monitor Trends

Track coverage over time:

```bash
# View historical coverage data
# https://codecov.io/gh/sopotek/tradeadviser/graph
```

Coverage should:
- 📈 Increase with new features
- 📊 Stay stable on maintenance
- 🛑 Not decrease on main/develop

## Running Coverage Locally vs CI

### Local Development

```bash
# Quick check
cd backend && pytest --cov=app
cd frontend && npm test -- --coverage

# No upload needed - for quick feedback
```

### CI/CD Pipeline

```bash
# Full coverage with upload
pytest --cov=app --cov-report=xml --cov-report=html --cov-report=json
npm test -- --coverage --collectCoverageFrom="src/**/*.{js,jsx}"

# Automatically uploaded to codecov.io
```

## Coverage Best Practices

### ✅ Do

- ✅ Write tests for new features before coverage reports
- ✅ Include edge cases and error scenarios
- ✅ Use coverage reports to identify gaps
- ✅ Aim for high coverage but prioritize important code
- ✅ Review coverage trends regularly
- ✅ Set realistic coverage targets (70-80%)

### ❌ Don't

- ❌ Write tests just to increase coverage numbers
- ❌ Cover trivial code like getters/setters
- ❌ Skip coverage for edge cases
- ❌ Ignore decreasing coverage trends
- ❌ Force 100% coverage on low-risk code
- ❌ Leave untested critical logic

## Troubleshooting

### Coverage Report Missing

**Problem:** Codecov comment not appearing on PR

**Solution:**
1. Check codecov.yml is valid: `python -m yaml codecov.yml`
2. Verify GitHub token has package read permissions
3. Check GitHub Actions upload step succeeds
4. View Codecov logs: https://codecov.io/gh/sopotek/tradeadviser/

### Low Coverage Suddenly

**Problem:** Coverage dropped after merge

**Solution:**
1. Identify changed files: `git diff HEAD~1 --name-only`
2. Check if tests exist for changed files
3. Run locally: `pytest --cov=app --cov-report=term-missing`
4. Add missing tests

### Different Coverage Local vs CI

**Problem:** Local coverage is 95%, CI shows 85%

**Solution:**
1. Ensure test database is clean (CI uses fresh DB)
2. Check for environment-specific code paths
3. Verify pytest configuration matches CI
4. Run CI tests locally: Use same dependencies in venv

## GitHub Integration

### PR Checks

Coverage status appears in PR:
```
✓ codecov/project — 75.2% (target: 70%)
✓ codecov/patch — 82.1% (target: 80%)
```

### Merging

When coverage requirements are enabled:
- ✅ Can merge if all checks pass
- ❌ Cannot merge if checks fail
- ⚠️ Can override with admin permissions (not recommended)

### Branch Protection

Configure in GitHub Settings:
- Require `codecov/project` to pass
- Require `codecov/patch` to pass
- Dismiss stale reviews on push

## Performance Impact

### CI/CD Pipeline Time

Adding coverage increases test time:
- **Backend**: +10-15% (pytest-cov overhead)
- **Frontend**: +20-30% (Jest coverage collection)
- **Total**: +2-3 minutes per test run

### Local Development Time

```bash
# Without coverage: ~30 seconds
pytest tests/

# With coverage: ~40 seconds
pytest --cov=app tests/
```

Use coverage sparingly during development, run full coverage before pushing.

## Advanced Configuration

### Custom Coverage Thresholds

By file or module in `codecov.yml`:

```yaml
coverage:
  backend:
    target: 80
  frontend:
    target: 75
  models:
    target: 90
```

### Ignore Patterns

```yaml
ignore:
  - "tests"
  - "**/test_*.py"
  - "**/__pycache__"
  - "node_modules"
```

### Carryforward Coverage

Maintain coverage for files not in PR:

```yaml
flags:
  backend:
    carryforward: true
  frontend:
    carryforward: true
```

## Resources

- **Codecov Documentation**: https://docs.codecov.io/
- **pytest-cov**: https://pytest-cov.readthedocs.io/
- **Jest Coverage**: https://jestjs.io/docs/coverage
- **Coverage.py**: https://coverage.readthedocs.io/

## Support

For coverage issues:
1. Check local coverage: `pytest --cov=app --cov-report=term-missing`
2. Review codecov.yml configuration
3. Check Codecov dashboard for error messages
4. Review test logs in GitHub Actions
5. Open issue with coverage report attached
