"""
Basic functionality tests for zpickle.
"""

import io
import os
import pickle
import tempfile

import pytest

import zpickle


class SampleObject:
    """Simple test class for pickle compatibility."""
    def __init__(self, value):
        self.value = value
    
    def __eq__(self, other):
        if not isinstance(other, SampleObject):
            return False
        return self.value == other.value


@pytest.fixture
def test_data():
    """Fixture that returns a dict with various data types."""
    return {
        "string": "hello world",
        "int": 42,
        "float": 3.14159,
        "list": [1, 2, 3, 4, 5],
        "dict": {"a": 1, "b": 2, "c": 3},
        "tuple": (1, "two", 3.0),
        "none": None,
        "bool": True,
        "object": SampleObject("test value"),
    }


def test_dumps_loads_roundtrip(test_data):
    """Test basic roundtrip with dumps and loads."""
    serialized = zpickle.dumps(test_data)
    restored = zpickle.loads(serialized)
    assert restored == test_data
    assert isinstance(restored["object"], SampleObject)
    assert restored["object"].value == "test value"


def test_dump_load_file_roundtrip(test_data):
    """Test roundtrip with dump and load using file objects."""
    # In-memory file object
    buffer = io.BytesIO()
    zpickle.dump(test_data, buffer)
    
    # Reset position for reading
    buffer.seek(0)
    restored = zpickle.load(buffer)
    
    assert restored == test_data
    assert isinstance(restored["object"], SampleObject)


def test_dump_load_disk_file(test_data):
    """Test roundtrip with dump and load using actual files."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        try:
            # Write to the file
            zpickle.dump(test_data, temp)
            temp.close()
            
            # Read from the file
            with open(temp.name, 'rb') as f:
                restored = zpickle.load(f)
            
            assert restored == test_data
            assert isinstance(restored["object"], SampleObject)
            
        finally:
            # Clean up
            if os.path.exists(temp.name):
                os.unlink(temp.name)


def test_compression_algorithms(test_data):
    """Test all supported compression algorithms."""
    algorithms = ['zstd', 'brotli', 'zlib', 'lzma', 'none']
    
    for algorithm in algorithms:
        # Compress with specific algorithm
        serialized = zpickle.dumps(test_data, algorithm=algorithm)
        
        # Validate header contains the right algorithm
        algo_id = zpickle.format.ALGORITHM_IDS.get(algorithm, 0)
        # Skip validation for 'none' as it's a special case
        if algorithm != 'none':
            assert serialized[5] == algo_id
        
        # Decompress and verify data
        restored = zpickle.loads(serialized)
        assert restored == test_data


def test_compression_levels(test_data):
    """Test different compression levels."""
    algorithm = 'zstd'  # Use zstd as it's the default
    
    for level in range(1, 10):
        # Compress with specific level
        serialized = zpickle.dumps(test_data, algorithm=algorithm, level=level)
        
        # Validate header contains the right level
        assert serialized[6] == level
        
        # Decompress and verify data
        restored = zpickle.loads(serialized)
        assert restored == test_data


def test_compatibility_with_pickle(test_data):
    """Test that zpickle can read regular pickle data."""
    # Serialize with standard pickle
    pickle_data = pickle.dumps(test_data)
    
    # Deserialize with zpickle
    restored = zpickle.loads(pickle_data)
    
    assert restored == test_data


def test_pickle_protocols(test_data):
    """Test compatibility with different pickle protocols."""
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        # Serialize with specific protocol
        serialized = zpickle.dumps(test_data, protocol=protocol)
        
        # Deserialize and verify
        restored = zpickle.loads(serialized)
        assert restored == test_data


def test_pickler_unpickler_classes(test_data):
    """Test the Pickler and Unpickler classes."""
    buffer = io.BytesIO()
    
    # Use Pickler class
    pickler = zpickle.Pickler(buffer)
    pickler.dump(test_data)
    
    # Reset position
    buffer.seek(0)
    
    # Use Unpickler class
    unpickler = zpickle.Unpickler(buffer)
    restored = unpickler.load()
    
    assert restored == test_data