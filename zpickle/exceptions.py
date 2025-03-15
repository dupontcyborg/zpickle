"""
Custom exceptions for zpickle.

This module defines custom exceptions raised by zpickle.
"""

class ZpickleError(Exception):
    """Base class for all zpickle exceptions."""
    pass

class CompressionError(ZpickleError):
    """Exception raised when compression fails."""
    pass

class DecompressionError(ZpickleError):
    """Exception raised when decompression fails."""
    pass

class InvalidFormatError(ZpickleError):
    """Exception raised when data has an invalid format."""
    pass

class UnsupportedAlgorithmError(ZpickleError):
    """Exception raised when an unsupported compression algorithm is requested."""
    pass

class UnsupportedVersionError(ZpickleError):
    """Exception raised when the format version is not supported."""
    pass