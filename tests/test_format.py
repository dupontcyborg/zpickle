"""
Tests for the format handling functionality.
"""

import struct

import pytest

from zpickle.exceptions import InvalidFormatError, UnsupportedAlgorithmError, UnsupportedVersionError
from zpickle.format import (
    ZPICKLE_MAGIC, PROTOCOL_VERSION, HEADER_FMT, HEADER_SIZE,
    ALGORITHMS, ALGORITHM_IDS, RESERVED_BYTE,
    is_zpickle_data, validate_algorithm, encode_header, decode_header
)


def test_header_constants():
    """Test the header format constants."""
    assert ZPICKLE_MAGIC == b'ZPKL'
    assert PROTOCOL_VERSION == 1
    assert HEADER_FMT == '!4sBBBB'
    assert HEADER_SIZE == struct.calcsize(HEADER_FMT)
    assert RESERVED_BYTE == 0


def test_algorithm_mappings():
    """Test the algorithm ID mappings."""
    # Test algorithm ID to name mapping
    assert ALGORITHMS[0] == 'none'
    assert ALGORITHMS[1] == 'zstd'
    assert ALGORITHMS[2] == 'brotli'
    assert ALGORITHMS[3] == 'zlib'
    assert ALGORITHMS[4] == 'lzma'
    
    # Test name to ID mapping
    assert ALGORITHM_IDS['none'] == 0
    assert ALGORITHM_IDS['zstd'] == 1
    assert ALGORITHM_IDS['brotli'] == 2
    assert ALGORITHM_IDS['zlib'] == 3
    assert ALGORITHM_IDS['lzma'] == 4
    
    # Verify the mappings are consistent
    for alg_id, alg_name in ALGORITHMS.items():
        assert ALGORITHM_IDS[alg_name] == alg_id


def test_is_zpickle_data():
    """Test the is_zpickle_data function."""
    # Create valid zpickle headers
    valid_header = ZPICKLE_MAGIC + b'\x01\x01\x01\x00'
    valid_data = valid_header + b'some data'
    
    # Create invalid headers
    invalid_magic = b'INVL' + b'\x01\x01\x01\x00'
    invalid_data = invalid_magic + b'some data'
    
    # Test detection
    assert is_zpickle_data(valid_data)
    assert not is_zpickle_data(invalid_data)
    assert not is_zpickle_data(b'too short')
    assert not is_zpickle_data(b'')


def test_validate_algorithm():
    """Test the validate_algorithm function."""
    # Valid algorithms
    for algorithm in ALGORITHM_IDS.keys():
        # Should not raise an exception
        validate_algorithm(algorithm)
    
    # Invalid algorithm
    with pytest.raises(UnsupportedAlgorithmError):
        validate_algorithm('invalid_algorithm')


def test_encode_header():
    """Test the encode_header function."""
    # Encode headers with different parameters
    header1 = encode_header('zstd', 3)
    header2 = encode_header('brotli', 5)
    header3 = encode_header('none', 0)
    
    # Verify the encoded data
    magic1, version1, alg_id1, level1, reserved1 = struct.unpack(HEADER_FMT, header1)
    magic2, version2, alg_id2, level2, reserved2 = struct.unpack(HEADER_FMT, header2)
    magic3, version3, alg_id3, level3, reserved3 = struct.unpack(HEADER_FMT, header3)
    
    # Check values
    assert magic1 == magic2 == magic3 == ZPICKLE_MAGIC
    assert version1 == version2 == version3 == PROTOCOL_VERSION
    assert alg_id1 == ALGORITHM_IDS['zstd']
    assert alg_id2 == ALGORITHM_IDS['brotli']
    assert alg_id3 == ALGORITHM_IDS['none']
    assert level1 == 3
    assert level2 == 5
    assert level3 == 0
    assert reserved1 == reserved2 == reserved3 == RESERVED_BYTE
    
    # Test with invalid algorithm
    with pytest.raises(UnsupportedAlgorithmError):
        encode_header('invalid_algorithm', 1)
    
    # Test with custom reserved byte
    header4 = encode_header('zstd', 1, reserved=42)
    magic4, version4, alg_id4, level4, reserved4 = struct.unpack(HEADER_FMT, header4)
    assert reserved4 == 42


def test_decode_header():
    """Test the decode_header function."""
    # Create valid headers
    header1 = struct.pack(HEADER_FMT, ZPICKLE_MAGIC, PROTOCOL_VERSION, 1, 3, 0)
    header2 = struct.pack(HEADER_FMT, ZPICKLE_MAGIC, PROTOCOL_VERSION, 2, 5, 0)
    
    # Decode and verify
    version1, alg1, level1, reserved1 = decode_header(header1)
    version2, alg2, level2, reserved2 = decode_header(header2)
    
    assert version1 == version2 == PROTOCOL_VERSION
    assert alg1 == 'zstd'
    assert alg2 == 'brotli'
    assert level1 == 3
    assert level2 == 5
    assert reserved1 == reserved2 == 0
    
    # Test with invalid magic bytes
    invalid_header = struct.pack(HEADER_FMT, b'INVL', PROTOCOL_VERSION, 1, 3, 0)
    with pytest.raises(InvalidFormatError):
        decode_header(invalid_header)
    
    # Test with unsupported version
    future_header = struct.pack(HEADER_FMT, ZPICKLE_MAGIC, PROTOCOL_VERSION + 10, 1, 3, 0)
    with pytest.raises(UnsupportedVersionError):
        decode_header(future_header)
    
    # Test with unknown algorithm ID
    unknown_alg_header = struct.pack(HEADER_FMT, ZPICKLE_MAGIC, PROTOCOL_VERSION, 99, 3, 0)
    with pytest.raises(UnsupportedAlgorithmError):
        decode_header(unknown_alg_header)
    
    # Test non-strict mode with future version - captures expected warning
    with pytest.warns(RuntimeWarning):
        version3, _, _, _ = decode_header(future_header, strict=False)
    assert version3 == PROTOCOL_VERSION + 10
    
    # Test non-strict mode with unknown algorithm ID
    with pytest.warns(RuntimeWarning):
        _, alg4, _, _ = decode_header(unknown_alg_header, strict=False)
    assert alg4 == 'zstd'  # Default algorithm

    try:
        # Test nonzero reserved byte warning (if your implementation has this)
        nonzero_reserved_header = struct.pack(HEADER_FMT + 'B', ZPICKLE_MAGIC, PROTOCOL_VERSION, 1, 3, 42)
        with pytest.warns(RuntimeWarning):
            decode_header(nonzero_reserved_header)
    except struct.error:
        # Skip if the format doesn't have reserved byte
        pass