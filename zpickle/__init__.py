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

from .compat import Pickler, Unpickler
from .config import ZpickleConfig, configure, get_config

# Import core functionality
from .core import (
    DEFAULT_CHUNK_SIZE,
    dump,
    dumps,
    load,
    loads,
)

# Make this module a drop-in replacement for pickle
__all__ = [
    # Core functions
    "dumps",
    "loads",
    "dump",
    "load",
    "DEFAULT_CHUNK_SIZE",
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
        DEFAULT_PROTOCOL as DEFAULT_PROTOCOL,
        HIGHEST_PROTOCOL as HIGHEST_PROTOCOL,
        PickleError as PickleError,
        PicklingError as PicklingError,
        UnpicklingError as UnpicklingError,
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
