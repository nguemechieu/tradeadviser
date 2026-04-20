# Contributing Guide

Sopotek Quant System is a proprietary desktop trading application. Contributions should stay aligned with operator safety, documentation quality, and a careful validation workflow.

## Contribution Principles

- keep changes scoped and intentional rather than mixing unrelated refactors into one pass
- prefer operator safety and runtime clarity over cleverness
- update docs whenever a user-facing workflow, command surface, or safety behavior changes
- avoid reverting unrelated local work you did not create

## Local Setup

1. Create and activate a virtual environment.
2. Install the full runtime from `requirements.txt`.
3. Install any dev tools you plan to use, such as `pytest`, `ruff`, or `mkdocs`.
4. Launch the app with `python main.py`.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .[dev,docs]
```

## Before You Start

- read [Getting Started](getting-started.md) if you are new to the runtime flow
- read [Development Notes](development.md) for the current repo layout and workflow expectations
- check [Integrations](integrations.md) before changing Telegram, OpenAI, speech, or screenshot behavior
- confirm whether your change affects operator docs, testing notes, or troubleshooting guidance

## Change Types

### Code Changes

- keep broker-specific behavior in adapters where possible
- prefer focused tests around the changed surface
- add or update docs when UI text, Telegram commands, settings, or workflows change
- if the feature is visual, do a quick sanity pass in the desktop app before considering it done

### Documentation Changes

- treat `docs/` as the source of truth for the MkDocs site
- keep page titles, navigation labels, and README links in sync
- prefer practical setup steps over abstract descriptions when writing operator docs
- if a new doc is important enough to discover directly, add it to `docs/mkdocs.yml`

## Validation Expectations

At minimum, contributors should run the most relevant checks for the area they touched.

Examples:

```powershell
python -m pytest src\tests -q
python -m py_compile src\integrations\telegram_service.py
python -m mkdocs build -f docs\mkdocs.yml
```

Focus especially on:

- broker adapters after changing order or market-data behavior
- Telegram tests after changing `src/integrations/telegram_service.py`
- UI sanity checks after changing terminal, dashboard, chart, or settings flows
- docs build checks after changing navigation or adding pages

## Docs And Release Hygiene

Update documentation when you change:

- Telegram commands, menus, or callbacks
- Sopotek Pilot behavior or OpenAI setup flow
- settings fields or integration onboarding
- risk controls, kill-switch flows, or live-trading safety language
- packaging metadata or first-release positioning

For release-facing changes, keep these aligned:

- `pyproject.toml`
- `README.md`
- release notes in `docs/release-notes.md`
- relevant operational docs in `docs/`

## Pull Request Checklist

- the change is scoped to one main goal
- relevant tests or sanity checks were run
- docs were updated where user behavior changed
- generated logs, screenshots, and runtime output were not committed by accident
- release-facing changes mention exact version numbers and dates where useful
