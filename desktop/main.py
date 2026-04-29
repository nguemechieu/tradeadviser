"""Bootstrap wrapper for the SQS (Sopotek Quant System) desktop workspace.


This entrypoint lives inside ``desktop_app/`` so the desktop product has its
own dedicated folder, while still delegating execution to the canonical source
tree at ``../src/main.py``.
"""
import sys
import os
from pathlib import Path


if __name__ == "__main__":
    # Get the project root (parent of sqs_desktop)
    desktop_dir = Path(__file__).resolve().parent
    project_root = desktop_dir.parent
    src_dir = desktop_dir / "src"

    # Add paths to Python path so imports work correctly
    # 1. Project root: so sqs_desktop package can be imported
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 2. sqs_desktop/src: so ui, config, etc can be imported
    #    as top-level modules
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # Check for venv
    venv_python = (
        desktop_dir / ".venv" / "Scripts" / "python.exe"
    )
    current_python = Path(sys.executable).resolve()

    if (
        venv_python.exists()
        and current_python != venv_python.resolve()
    ):
        os.execv(
            str(venv_python),
            [str(venv_python), str(__file__), *sys.argv[1:]],
        )

    # Import and run the main module from the main package
    # Path: desktop/src/main/__init__.py
    from src.main import main

    sys.exit(main())
