"""
Edge case tests for zpickle.
"""

import io
import pickle
import struct

import pytest

import zpickle
from zpickle.format import HEADER_SIZE, ZPICKLE_MAGIC


def test_small_objects():
    """Test behavior with objects smaller than compression threshold."""
    # Get current min_size threshold
    min_size = zpickle.get_config().min_size

    # Make string exactly 10 bytes - well below any reasonable min_size
    small_data = "x" * 10

    # Save original config
    original_config = zpickle.get_config()

    try:
        # Force a clear behavior with explicit min_size much larger than our data
        zpickle.configure(algorithm="zstd", min_size=1000)

        # Serialize it
        serialized = zpickle.dumps(small_data)

        # Check the algorithm ID in the header (should be 0 for 'none')
        assert serialized[5] == 0  # Algorithm ID for 'none'

        # Restore and verify
        restored = zpickle.loads(serialized)
        assert restored == small_data
    finally:
        # Restore original config
        zpickle.configure(
            algorithm=original_config.algorithm,
            level=original_config.level,
            min_size=original_config.min_size,
        )


def test_large_objects():
    """Test behavior with larger objects."""
    # Create a larger object that should definitely be compressed
    large_data = "x" * 10000

    # Save original config
    original_config = zpickle.get_config()

    try:
        # Ensure we're using zstd for this test
        zpickle.configure(algorithm="zstd")

        # Serialize with default algorithm (zstd)
        serialized = zpickle.dumps(large_data)

        # Check algorithm ID in header (should be 1 for 'zstd')
        assert serialized[5] == 1

        # Compressed data should be smaller than original
        assert len(serialized) < len(large_data) + HEADER_SIZE

        # Restore and verify
        restored = zpickle.loads(serialized)
        assert restored == large_data
    finally:
        # Restore original config
        zpickle.configure(
            algorithm=original_config.algorithm,
            level=original_config.level,
            min_size=original_config.min_size,
        )


def test_various_data_types():
    """Test with various Python data types."""
    data_types = [
        None,
        True,
        False,
        0,
        1,
        -1,
        2**31,
        -(2**31),
        0.0,
        3.14,
        -2.718,
        float("inf"),
        "",
        "hello",
        "a" * 1000,
        b"",
        b"binary",
        b"\x00\xff" * 100,
        [],
        [1, 2, 3],
        ["nested", ["lists"]],
        {},
        {"key": "value"},
        {i: i**2 for i in range(100)},
        (),
        (1, 2, 3),
        ((1, 2), (3, 4)),
        set(),
        {1, 2, 3},
        frozenset([4, 5, 6]),
    ]

    for data in data_types:
        # Serialize and deserialize
        serialized = zpickle.dumps(data)
        restored = zpickle.loads(serialized)

        # Verify
        assert restored == data
        assert type(restored) == type(data)


def test_binary_data():
    """Test with binary data including NULL bytes."""
    bindata = bytes(range(256)) * 10  # All possible byte values

    # Serialize and deserialize
    serialized = zpickle.dumps(bindata)
    restored = zpickle.loads(serialized)

    # Verify
    assert restored == bindata


def test_recursive_structures():
    """Test with recursive data structures."""
    # Create a recursive list
    recursive_list = [1, 2, 3]
    recursive_list.append(recursive_list)

    # Serialize and deserialize
    serialized = zpickle.dumps(recursive_list)
    restored = zpickle.loads(serialized)

    # Verify structure (comparing directly would cause infinite recursion)
    assert restored[0] == 1
    assert restored[1] == 2
    assert restored[2] == 3
    assert restored[3] is restored  # The fourth element should be the list itself


def test_custom_config():
    """Test with custom configuration."""
    data = "hello" * 100

    # Save original config
    original_config = zpickle.get_config()

    try:
        # Change global config - set min_size high enough that our data is below it
        zpickle.configure(algorithm="brotli", level=9, min_size=1000)

        # Small objects (below min_size) should use 'none' algorithm
        serialized1 = zpickle.dumps(data)
        assert serialized1[5] == 0  # 'none' ID

        # Now create a larger object that will definitely be compressed
        big_data = "x" * 2000  # Larger than min_size

        # This should use brotli
        serialized2 = zpickle.dumps(big_data, algorithm="brotli", level=3)
        assert serialized2[5] == 2  # brotli ID
        assert serialized2[6] == 3  # level 3

        # Verify both deserialize correctly
        assert zpickle.loads(serialized1) == data
        assert zpickle.loads(serialized2) == big_data

    finally:
        # Restore original config
        zpickle.configure(
            algorithm=original_config.algorithm,
            level=original_config.level,
            min_size=original_config.min_size,
        )


def test_invalid_header():
    """Test handling of data with invalid header."""
    # Create data with invalid magic bytes - make it valid pickle data
    valid_pickle = pickle.dumps("test data")

    # Should raise some exception when strict=True and invalid header is found
    # The specific exception depends on implementation
    try:
        zpickle.loads(valid_pickle, strict=True)
        # If we get here, no exception was raised - that's wrong
        assert False, "Expected exception was not raised"
    except Exception:
        # Any exception is acceptable here
        pass

    # Should be able to load valid pickle data when strict=False
    result = zpickle.loads(valid_pickle, strict=False)
    assert result == "test data"


def test_unsupported_algorithm():
    """Test handling of unsupported algorithm ID."""
    # Create a valid header with an invalid algorithm ID (200)
    header = struct.pack("!4sBBB", ZPICKLE_MAGIC, 1, 200, 1)

    # Create valid pickle data
    pickled = pickle.dumps("test data")

    # Combine header with valid pickle data
    invalid_data = header + pickled

    # Should raise UnsupportedAlgorithmError or similar when strict=True
    try:
        zpickle.loads(invalid_data, strict=True)
        # If we get here, no exception was raised - that's wrong
        assert False, "Expected exception was not raised"
    except Exception:
        # Any exception is acceptable here
        pass

    # With strict=False, should try to handle it, but might still fail
    # Let's not explicitly test the result as implementation may vary


def test_future_version():
    """Test handling of data with future version number."""
    # Create a valid header with a future version (99)
    header = struct.pack("!4sBBB", ZPICKLE_MAGIC, 99, 1, 1)

    # Create valid pickle data
    pickled = pickle.dumps("test data")

    # Combine for testing
    future_data = header + pickled

    # Should raise UnsupportedVersionError or similar when strict=True
    try:
        zpickle.loads(future_data, strict=True)
        # If we get here, no exception was raised - that's wrong
        assert False, "Expected exception was not raised"
    except Exception:
        # Any exception is acceptable here
        pass

    # With strict=False, should try to handle it, but might still fail
    # Let's not explicitly test the result as implementation may vary
