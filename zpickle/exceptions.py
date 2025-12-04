"""
Custom exceptions for zpickle.

This module defines custom exceptions raised by zpickle.
"""

# Supported algorithms for helpful error messages
SUPPORTED_ALGORITHMS = ("zstd", "brotli", "zlib", "lzma", "none")


class ZpickleError(Exception):
    """Base class for all zpickle exceptions."""

    pass


class CompressionError(ZpickleError):
    """Exception raised when compression fails.

    This may occur if the compression library encounters an error,
    or if the data cannot be compressed with the specified algorithm.
    """

    pass


class DecompressionError(ZpickleError):
    """Exception raised when decompression fails.

    This typically occurs when:
    - The compressed data is corrupted
    - The wrong algorithm is used for decompression
    - The data was truncated or modified
    """

    pass


class InvalidFormatError(ZpickleError):
    """Exception raised when data has an invalid format.

    This occurs when the data does not have a valid zpickle header.
    Zpickle files should start with the magic bytes 'ZPKL'.
    """

    pass


class UnsupportedAlgorithmError(ZpickleError):
    """Exception raised when an unsupported compression algorithm is requested.

    Supported algorithms are: zstd, brotli, zlib, lzma, none
    """

    def __init__(self, message=None, algorithm=None):
        if message is None and algorithm is not None:
            supported = ", ".join(f"'{a}'" for a in SUPPORTED_ALGORITHMS)
            message = (
                f"Unsupported compression algorithm: '{algorithm}'. "
                f"Supported algorithms are: {supported}"
            )
        super().__init__(message)
        self.algorithm = algorithm


class UnsupportedVersionError(ZpickleError):
    """Exception raised when the format version is not supported.

    This occurs when trying to read a file created with a newer version
    of zpickle. Consider upgrading zpickle: pip install --upgrade zpickle
    """

    def __init__(self, message=None, version=None, max_supported=None):
        if message is None and version is not None:
            message = (
                f"Unsupported zpickle format version: {version}. "
                f"This library supports up to version {max_supported or 'unknown'}. "
                f"Try upgrading: pip install --upgrade zpickle"
            )
        super().__init__(message)
        self.version = version
        self.max_supported = max_supported
