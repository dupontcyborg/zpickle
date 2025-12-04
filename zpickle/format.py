"""
Format definitions and header handling for zpickle.

This module defines the binary format used by zpickle, including
header structure, magic numbers, and algorithm mappings.
"""

import struct
import warnings
from typing import Tuple

from .exceptions import (
    InvalidFormatError,
    UnsupportedAlgorithmError,
    UnsupportedVersionError,
)

# Format constants
ZPICKLE_MAGIC = b"ZPKL"
PROTOCOL_VERSION = 1  # Format version
HEADER_FMT = (
    "!4sBBBB"  # Magic (4), Version (1), Algorithm ID (1), Level (1), Reserved (1)
)
HEADER_SIZE = struct.calcsize(HEADER_FMT)

# Reserved byte should be zero in version 1
RESERVED_BYTE = 0

# Algorithm mapping (byte ID to name)
ALGORITHMS = {
    0: "none",  # No compression
    1: "zstd",  # Zstandard compression
    2: "brotli",  # Brotli compression
    3: "zlib",  # zlib/gzip compression
    4: "lzma",  # LZMA/xz compression
}

# Reverse mapping (name to byte ID)
ALGORITHM_IDS = {v: k for k, v in ALGORITHMS.items()}


def is_zpickle_data(data: bytes) -> bool:
    """Check if the data appears to be in zpickle format.

    Args:
        data (bytes): The binary data to check

    Returns:
        bool: True if the data has a valid zpickle header, False otherwise
    """
    return len(data) >= HEADER_SIZE and data[:4] == ZPICKLE_MAGIC


def validate_algorithm(algorithm: str) -> None:
    """Validate that the algorithm name is supported.

    Args:
        algorithm (str): Algorithm name to validate

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not supported
    """
    if algorithm not in ALGORITHM_IDS:
        supported = ", ".join(f"'{alg}'" for alg in sorted(ALGORITHM_IDS.keys()))
        raise UnsupportedAlgorithmError(
            f"Unsupported compression algorithm: '{algorithm}'. "
            f"Supported algorithms are: {supported}"
        )


def encode_header(algorithm: str, level: int, reserved: int = RESERVED_BYTE) -> bytes:
    """Create a zpickle header with the specified algorithm and level.

    Args:
        algorithm (str): The compression algorithm name
        level (int): The compression level
        reserved (int, optional): Reserved byte for future extensions.
            Defaults to RESERVED_BYTE.

    Returns:
        bytes: The encoded header

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not supported
    """
    # Validate algorithm
    validate_algorithm(algorithm)

    alg_id = ALGORITHM_IDS[algorithm]
    return struct.pack(
        HEADER_FMT, ZPICKLE_MAGIC, PROTOCOL_VERSION, alg_id, level, reserved
    )


def decode_header(data: bytes, strict: bool = True) -> Tuple[int, str, int, int]:
    """Extract version, algorithm, level, and reserved byte from zpickle header.

    Args:
        data (bytes): The binary data, starting with the zpickle header
        strict (bool, optional): If True, raises an error for unrecognized algorithms
                                or unsupported versions. Defaults to True.

    Returns:
        tuple: (version, algorithm_name, level, reserved)

    Raises:
        InvalidFormatError: If the header magic bytes are incorrect
        UnsupportedAlgorithmError: If strict=True and algorithm ID is not recognized
        UnsupportedVersionError: If version is higher than supported and strict=True
    """
    if not data.startswith(ZPICKLE_MAGIC):
        raise InvalidFormatError(
            f"Invalid zpickle header: expected magic bytes {ZPICKLE_MAGIC!r}, "
            f"got {data[:4]!r}"
        )

    _, version, alg_id, level, reserved = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])

    # Check if version is supported
    if version > PROTOCOL_VERSION:
        msg = (
            f"File uses zpickle format version {version}, but this library only "
            f"supports up to version {PROTOCOL_VERSION}. "
            f"Try upgrading: pip install --upgrade zpickle"
        )
        if strict:
            raise UnsupportedVersionError(msg)
        else:
            warnings.warn(f"{msg} Attempting to read anyway.", RuntimeWarning)

    # Check if algorithm ID is recognized
    algorithm = ALGORITHMS.get(alg_id)
    if algorithm is None:
        known_ids = ", ".join(f"{k}={v}" for k, v in sorted(ALGORITHMS.items()))
        if strict:
            raise UnsupportedAlgorithmError(
                f"Unrecognized compression algorithm ID: {alg_id}. "
                f"Known algorithm IDs: {known_ids}. "
                f"This file may have been created with a newer version of zpickle. "
                f"Try upgrading: pip install --upgrade zpickle"
            )
        else:
            warnings.warn(
                f"Unrecognized algorithm ID: {alg_id}. Known IDs: {known_ids}. "
                f"Falling back to zstd.",
                RuntimeWarning,
            )
            # Fall back to zstd if not in strict mode
            algorithm = "zstd"

    # In version 1, reserved byte should be zero
    # Future versions may use this byte for specific features
    if version == 1 and reserved != 0 and strict:
        warnings.warn(
            f"Reserved byte is {reserved}, expected 0 for version 1.", RuntimeWarning
        )

    return version, algorithm, level, reserved
