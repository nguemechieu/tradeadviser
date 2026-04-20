from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


def _workspace_temp_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tmp" / "pytest-session-temp"


def _workspace_mkdtemp(
    suffix: str | None = None,
    prefix: str | None = None,
    dir: str | os.PathLike[str] | None = None,
) -> str:
    base_dir = Path(dir) if dir is not None else _workspace_temp_root()
    base_dir.mkdir(parents=True, exist_ok=True)
    prefix_text = str(prefix or "tmp")
    suffix_text = str(suffix or "")
    while True:
        candidate = base_dir / f"{prefix_text}{uuid4().hex}{suffix_text}"
        try:
            candidate.mkdir()
            return str(candidate)
        except FileExistsError:
            continue


class _WorkspaceTemporaryDirectory:
    """Repo-local TemporaryDirectory replacement for restricted Windows runs."""

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
        ignore_cleanup_errors: bool = False,
        *,
        delete: bool = True,
    ) -> None:
        self.name = _workspace_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self._ignore_cleanup_errors = bool(ignore_cleanup_errors)
        self._delete = bool(delete)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if self._delete:
            shutil.rmtree(self.name, ignore_errors=self._ignore_cleanup_errors)


class _WorkspaceTempPathFactory:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._counters: dict[str, int] = {}

    def getbasetemp(self) -> Path:
        return self._base_dir

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        safe_name = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in str(basename or "tmp")
        ).strip("_") or "tmp"
        if not numbered:
            candidate = self._base_dir / safe_name
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate

        counter = self._counters.get(safe_name, 0)
        while True:
            candidate = self._base_dir / f"{safe_name}{counter}"
            counter += 1
            if candidate.exists():
                continue
            candidate.mkdir(parents=True, exist_ok=False)
            self._counters[safe_name] = counter
            return candidate


def pytest_configure() -> None:
    """Keep temp-file writes inside the repository during test runs."""
    workspace_temp = _workspace_temp_root()
    workspace_temp.mkdir(parents=True, exist_ok=True)
    temp_value = str(workspace_temp)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = temp_value
    tempfile.tempdir = temp_value
    tempfile.mkdtemp = _workspace_mkdtemp
    tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory


@pytest.fixture(scope="session")
def tmp_path_factory() -> _WorkspaceTempPathFactory:
    session_root = Path(_workspace_mkdtemp(prefix="pytest-paths-", dir=_workspace_temp_root()))
    factory = _WorkspaceTempPathFactory(session_root)
    try:
        yield factory
    finally:
        shutil.rmtree(session_root, ignore_errors=True)


@pytest.fixture
def tmp_path(tmp_path_factory: _WorkspaceTempPathFactory, request: pytest.FixtureRequest) -> Path:
    return tmp_path_factory.mktemp(request.node.name, numbered=True)
