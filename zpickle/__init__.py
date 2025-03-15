"""
zpickle - Transparent compression for Python's pickle.

This module provides a drop-in replacement for the standard pickle module,
with transparent compression of serialized objects.
"""

# Version management with setuptools_scm
try:
    # First try to get the version from the generated _version.py file
    from ._version import version as __version__
except ImportError:
    # Fall back to an unknown version
    __version__ = "0.0.0+unknown"

# Import core functionality
from .core import dumps, loads, dump, load
from .compat import Pickler, Unpickler
from .config import configure, get_config, ZpickleConfig

# Make this module a drop-in replacement for pickle
__all__ = [
    # Core functions
    "dumps",
    "loads",
    "dump",
    "load",
    # Classes
    "Pickler",
    "Unpickler",
    # Configuration
    "configure",
    "get_config",
    "ZpickleConfig",
    # Version
    "__version__",
]

# Re-export pickle's extended API for complete compatibility
try:
    from pickle import (
        PickleError,
        PicklingError,
        UnpicklingError,
        HIGHEST_PROTOCOL,
        DEFAULT_PROTOCOL,
    )

    __all__.extend(
        [
            "PickleError",
            "PicklingError",
            "UnpicklingError",
            "HIGHEST_PROTOCOL",
            "DEFAULT_PROTOCOL",
        ]
    )
except ImportError:
    pass
