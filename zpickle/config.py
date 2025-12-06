"""
Configuration management for zpickle.

This module handles the configuration settings for zpickle, including
algorithm selection, compression level, and minimum size thresholds.
"""

from typing import Optional

# Default settings
DEFAULT_ALGORITHM = "zstd"
DEFAULT_LEVEL = 3
MIN_SIZE_FOR_COMPRESSION = 64  # Don't compress very small objects


class ZpickleConfig:
    """Configuration for zpickle compression.

    Attributes:
        algorithm (str): Compression algorithm to use.
            Options: 'zstd', 'brotli', 'zlib', 'lzma', 'bzip2', 'lz4', 'none'
        level (int): Compression level (1-10, higher = more compression)
        min_size (int): Minimum size in bytes before compression is applied
    """

    def __init__(
        self,
        algorithm: str = DEFAULT_ALGORITHM,
        level: int = DEFAULT_LEVEL,
        min_size: int = MIN_SIZE_FOR_COMPRESSION,
    ):
        self.algorithm = algorithm
        self.level = level
        self.min_size = min_size

    def __repr__(self) -> str:
        return (
            f"ZpickleConfig(algorithm='{self.algorithm}', "
            f"level={self.level}, min_size={self.min_size})"
        )


# Global configuration
_config = ZpickleConfig()


def get_config() -> ZpickleConfig:
    """Get the current global configuration.

    Returns:
        ZpickleConfig: The current configuration object
    """
    return _config


def configure(
    algorithm: Optional[str] = None,
    level: Optional[int] = None,
    min_size: Optional[int] = None,
) -> None:
    """Configure global zpickle settings.

    Args:
        algorithm (str, optional): Compression algorithm to use.
            Options: 'zstd', 'brotli', 'zlib', 'lzma', 'bzip2', 'lz4', 'none'
        level (int, optional): Compression level (1-10, higher = more compression)
        min_size (int, optional): Minimum size in bytes before compression is applied

    Example:
        >>> import zpickle
        >>> zpickle.configure(algorithm='brotli', level=5)
    """
    global _config
    if algorithm is not None:
        _config.algorithm = algorithm
    if level is not None:
        _config.level = level
    if min_size is not None:
        _config.min_size = min_size
