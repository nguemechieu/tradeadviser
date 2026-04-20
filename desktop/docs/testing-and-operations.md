# Testing And Operations

## Local Runtime

Recommended desktop run command:

```powershell
python main.py
```

This repo-root launcher is the preferred operator path. It forwards startup to `src/main.py`.

## Test Commands

Run all tests:

```powershell
python -m pytest src\tests -q
```

Run focused execution and broker tests:

```powershell
python -m pytest src\tests\test_execution.py src\tests\test_other_broker_adapters.py src\tests\test_storage_runtime.py -q
```

Run focused integration tests:

```powershell
python -m pytest src\tests\test_news_service.py src\tests\test_telegram_service.py src\tests\test_license_manager.py -q
```

## Build Commands

Build Python packages:

```powershell
python -m build
```

Check package metadata:

```powershell
python -m twine check dist\*
```

## Documentation Commands

Serve docs locally:

```powershell
python -m mkdocs serve -f docs\mkdocs.yml
```

Build docs site:

```powershell
python -m mkdocs build -f docs\mkdocs.yml
```

Build and validate docs in one pass:

```powershell
python -m mkdocs build -f docs\mkdocs.yml --strict
```

## Persistence And Files

### SQLite
Default local database path:
- `data/sopotek_trading.db`

### Logs
Repo evidence shows logs in:
- `logs/`
- `src/logs/`

### Screenshots And Artifacts
Generated files can appear in:
- `output/screenshots/`
- `output/docs-site/`
- `src/reports/`
- `src/output/`

## Operational Notes

- Oanda currently uses polling market data in the application flow.
- Detached chart layouts are restored through `QSettings`.
- Runtime settings, checklist state, and integration preferences persist across sessions.
- Telegram and OpenAI integrations should be validated independently from core trading before live use.
- A quick manual order smoke test is still the best first end-to-end health check before relying on AI trading.

## Container Assets

`Dockerfile` and `docker-compose.yml` are present, but they are not the primary documented run path for the current desktop UI. If you plan to rely on them, validate them separately with a real Docker build and runtime pass.
