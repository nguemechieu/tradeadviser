"""FastAPI application shell for the Sopotek server trading core."""

import sys
from types import ModuleType

# Register this backend directory as the 'sopotek' module for backwards compatibility
# This allows imports like: from sopotek.shared.contracts import ...
backend_module = sys.modules[__name__]
sopotek_module = ModuleType('sopotek')
sopotek_module.__path__ = backend_module.__path__
sopotek_module.__file__ = backend_module.__file__
sopotek_module.__package__ = 'sopotek'
sys.modules['sopotek'] = sopotek_module

# Import shared so it's available as sopotek.shared
from . import shared  # noqa: F401
sopotek_module.shared = shared

