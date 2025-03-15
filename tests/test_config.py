"""
Tests for the configuration functionality.
"""

import pytest

import zpickle
from zpickle.config import (
    DEFAULT_ALGORITHM,
    DEFAULT_LEVEL,
    MIN_SIZE_FOR_COMPRESSION,
    ZpickleConfig,
)


@pytest.fixture(autouse=True)
def reset_config_after_test():
    """Reset configuration to default after each test."""
    # Store original values
    orig_alg = DEFAULT_ALGORITHM
    orig_level = DEFAULT_LEVEL
    orig_min_size = MIN_SIZE_FOR_COMPRESSION

    # Let the test run
    yield

    # After test, reset to the default values (not the previous test's values)
    zpickle.configure(algorithm=orig_alg, level=orig_level, min_size=orig_min_size)


def test_default_config():
    """Test that the default configuration has expected values."""
    # First reset to ensure we're testing the defaults
    zpickle.configure(
        algorithm=DEFAULT_ALGORITHM,
        level=DEFAULT_LEVEL,
        min_size=MIN_SIZE_FOR_COMPRESSION,
    )

    config = zpickle.get_config()

    assert isinstance(config, ZpickleConfig)
    assert config.algorithm == DEFAULT_ALGORITHM
    assert config.level == DEFAULT_LEVEL
    assert config.min_size == MIN_SIZE_FOR_COMPRESSION


def test_configure_function():
    """Test the configure function updates global config."""
    # First set to known values
    zpickle.configure(
        algorithm=DEFAULT_ALGORITHM,
        level=DEFAULT_LEVEL,
        min_size=MIN_SIZE_FOR_COMPRESSION,
    )

    # Change all settings
    zpickle.configure(algorithm="lzma", level=9, min_size=1000)

    # Verify changes were applied
    config = zpickle.get_config()
    assert config.algorithm == "lzma"
    assert config.level == 9
    assert config.min_size == 1000

    # Change only some settings
    zpickle.configure(algorithm="zlib")
    config = zpickle.get_config()
    assert config.algorithm == "zlib"
    assert config.level == 9  # Unchanged
    assert config.min_size == 1000  # Unchanged

    zpickle.configure(level=5)
    config = zpickle.get_config()
    assert config.algorithm == "zlib"  # Unchanged
    assert config.level == 5
    assert config.min_size == 1000  # Unchanged

    zpickle.configure(min_size=500)
    config = zpickle.get_config()
    assert config.algorithm == "zlib"  # Unchanged
    assert config.level == 5  # Unchanged
    assert config.min_size == 500


def test_config_affects_compression():
    """Test that configuration changes affect compression behavior."""
    # First reset to ensure a clean state
    zpickle.configure(
        algorithm=DEFAULT_ALGORITHM,
        level=DEFAULT_LEVEL,
        min_size=MIN_SIZE_FOR_COMPRESSION,
    )

    test_data = "hello" * 1000  # Make sure it's larger than min_size

    # Test with default config (which should be zstd)
    default_result = zpickle.dumps(test_data)

    # Change algorithm and test
    zpickle.configure(algorithm="brotli")
    brotli_result = zpickle.dumps(test_data)

    # Change compression level and test
    zpickle.configure(algorithm="brotli", level=9)
    brotli_high_result = zpickle.dumps(test_data)

    # Verify results
    assert default_result[5] == zpickle.format.ALGORITHM_IDS["zstd"]
    assert brotli_result[5] == zpickle.format.ALGORITHM_IDS["brotli"]
    assert brotli_high_result[5] == zpickle.format.ALGORITHM_IDS["brotli"]
    assert brotli_high_result[6] == 9  # Level

    # Higher compression level should generally result in smaller size
    # (not guaranteed but likely for repetitive data)
    assert len(brotli_high_result) <= len(brotli_result) + 5  # Allow some margin


def test_min_size_threshold():
    """Test that min_size controls when compression is applied."""
    # First reset to ensure a clean state
    zpickle.configure(
        algorithm=DEFAULT_ALGORITHM,
        level=DEFAULT_LEVEL,
        min_size=MIN_SIZE_FOR_COMPRESSION,
    )

    # Set min_size to a known value
    test_min_size = 100
    zpickle.configure(min_size=test_min_size)

    # Test with data smaller than threshold
    small_data = "x" * (test_min_size - 20)
    small_result = zpickle.dumps(small_data)

    # Test with data larger than threshold
    large_data = "x" * (test_min_size + 50)  # Make it well above threshold
    large_result = zpickle.dumps(large_data)

    # Verify compression was applied appropriately
    assert small_result[5] == zpickle.format.ALGORITHM_IDS["none"]  # No compression
    assert (
        large_result[5] == zpickle.format.ALGORITHM_IDS[DEFAULT_ALGORITHM]
    )  # Compressed


def test_config_repr():
    """Test the string representation of ZpickleConfig."""
    config = ZpickleConfig(algorithm="zstd", level=3, min_size=64)
    repr_str = repr(config)

    assert "ZpickleConfig" in repr_str
    assert "algorithm='zstd'" in repr_str
    assert "level=3" in repr_str
    assert "min_size=64" in repr_str
