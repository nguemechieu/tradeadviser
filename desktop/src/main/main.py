"""Backward-compatible launcher helpers."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


def _desktop_entrypoint_module() -> ModuleType:
    import sys
    module_path = Path(__file__).resolve().parents[1] / "main.py"
    src_dir = Path(__file__).resolve().parents[1]
    project_root = src_dir.parent.parent
    
    # Add directories to sys.path so imports in main.py work
    # 1. Project root: for imports like sqs_server, shared
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    # 2. src directory: for imports like ui, config, etc
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    spec = spec_from_file_location("sopotek_desktop_main", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load desktop entrypoint from {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ENTRYPOINT_MODULE = _desktop_entrypoint_module()

for _name, _value in vars(_ENTRYPOINT_MODULE).items():
    if _name.startswith("__"):
        continue
    globals()[_name] = _value

main = _ENTRYPOINT_MODULE.main
