# Development Notes

## Primary Runtime Files

- `src/main.py`: app bootstrap and event loop startup
- `src/frontend/ui/app_controller.py`: runtime controller and orchestration layer
- `src/frontend/ui/terminal.py`: main terminal workspace and most user-facing tools
- `src/frontend/ui/dashboard.py`: pre-terminal launch workflow
- `src/frontend/ui/chart/chart_widget.py`: chart engine and chart interactions

## Repo Layout

### UI
- `src/frontend/ui/`
- `src/frontend/ui/chart/`
- `src/frontend/console/`

### Brokers
- `src/broker/`

### Trading Core
- `src/core/`
- `src/execution/`
- `src/strategy/`
- `src/risk/`

### Data And Storage
- `src/storage/`
- `src/market_data/`

### Analytics And Backtesting
- `src/backtesting/`
- `src/engines/`

### Tests
- `src/tests/`

## Dependency Notes

- `requirements.txt` is the best evidence for the full desktop runtime dependency set.
- `pyproject.toml` is useful for packaging and metadata, but it may lag the full operational dependency list.
- Voice, OpenAI, Telegram, and GUI features are all runtime-sensitive and should be validated in the environment you actually use.

## Documentation Stack

- MkDocs config: `docs/mkdocs.yml`
- Docs site source: `docs/`
- Docs landing page: `docs/index.md`
- Contributor guide: `docs/contributing.md`

## Current Development Guidance

- Treat `src/frontend/ui/terminal.py` as the heaviest integration surface in the repo.
- Prefer validating changes with focused tests plus a quick UI sanity pass when the feature is heavily visual.
- Keep broker-specific behavior isolated in adapters whenever possible.
- Generated output and screenshots should stay out of commits unless explicitly intended.
- Documentation should be updated whenever terminal workflows, Telegram commands, Sopotek Pilot behavior, or safety controls change, because those are fast-moving user-facing surfaces.

## Recommended Next Improvements

- deeper broker capability introspection in the UI
- more dedicated tests around detached window workflows
- more coverage for Telegram + chart capture + Sopotek Pilot interaction together
- exported reports or PDFs from checklist, journal, and review workflows
