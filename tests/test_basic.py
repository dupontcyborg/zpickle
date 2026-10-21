"""
Basic functionality tests for zpickle.
"""

import io
import os
import pickle
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor

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
            with open(temp.name, "rb") as f:
                restored = zpickle.load(f)

            assert restored == test_data
            assert isinstance(restored["object"], SampleObject)

        finally:
            # Clean up
            if os.path.exists(temp.name):
                os.unlink(temp.name)


def test_compression_algorithms(test_data):
    """Test all supported compression algorithms."""
    algorithms = [
        "zstd",
        "brotli",
        "zlib",
        "lzma",
        "bzip2",
        "lz4",
        "snappy",
        "gzip",
        "deflate",
        "none",
    ]

    for algorithm in algorithms:
        # Compress with specific algorithm
        serialized = zpickle.dumps(test_data, algorithm=algorithm)

        # Validate header contains the right algorithm
        algo_id = zpickle.format.ALGORITHM_IDS.get(algorithm, 0)
        # Skip validation for 'none' as it's a special case
        if algorithm != "none":
            assert serialized[5] == algo_id

        # Decompress and verify data
        restored = zpickle.loads(serialized)
        assert restored == test_data


def test_compression_levels(test_data):
    """Test different compression levels."""
    algorithm = "zstd"  # Use zstd as it's the default

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


def test_dump_load_large_data_with_streaming():
    """Test that dump() uses streaming compression for large data."""
    # Create a large dataset (10MB of repetitive data that compresses well)
    large_data = {
        "repeated_string": "This is a test string. " * 100000,  # ~2.3MB
        "large_list": list(range(100000)) * 10,  # ~10MB when pickled
        "nested": {
            "data": ["x" * 1000 for _ in range(1000)],  # ~1MB
        },
    }

    # Test with zpickle using dump() (should use streaming compression)
    zpickle_buffer = io.BytesIO()
    zpickle.dump(large_data, zpickle_buffer)
    zpickle_size = len(zpickle_buffer.getvalue())

    # Test with regular pickle for comparison
    pickle_buffer = io.BytesIO()
    pickle.dump(large_data, pickle_buffer)
    pickle_size = len(pickle_buffer.getvalue())

    # Verify zpickle is significantly smaller (at least 50% compression)
    compression_ratio = zpickle_size / pickle_size
    assert compression_ratio < 0.5, (
        f"Expected >50% compression, got {compression_ratio:.1%}"
    )

    # Verify we can load it back correctly with load() (streaming decompression)
    zpickle_buffer.seek(0)
    restored = zpickle.load(zpickle_buffer)

    # Verify data integrity
    assert restored == large_data
    assert len(restored["large_list"]) == 1000000
    assert restored["repeated_string"].startswith("This is a test string. ")

    # Test with actual file to ensure streaming works with real files
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        try:
            zpickle.dump(large_data, temp)
            temp.close()

            file_size = os.path.getsize(temp.name)
            assert file_size < pickle_size * 0.5, (
                "File should be compressed with streaming"
            )

            with open(temp.name, "rb") as f:
                restored_from_file = zpickle.load(f)

            assert restored_from_file == large_data

        finally:
            if os.path.exists(temp.name):
                os.unlink(temp.name)


@pytest.mark.parametrize("algorithm", sorted(zpickle.format.ALGORITHM_IDS))
def test_streaming_large_binary_roundtrip(algorithm):
    """Streaming dump/load of payloads spanning many chunks and write batches."""
    rng = random.Random(0)
    # Low-redundancy bytes compress poorly, so load() reads many chunks
    blob = rng.randbytes(3 * zpickle.DEFAULT_CHUNK_SIZE + 123)
    data = {
        "blob": blob,
        "records": [{"id": i, "name": f"item{i}"} for i in range(20000)],
        "tail": blob[:1000],
    }

    buffer = io.BytesIO()
    zpickle.dump(data, buffer, algorithm=algorithm)
    buffer.seek(0)

    assert zpickle.load(buffer) == data


def test_concurrent_roundtrips():
    """Round-trips from many threads at once (parallel on free-threaded Python)."""
    algorithms = ["zstd", "lz4", "gzip", "deflate"]

    def roundtrip(i):
        data = {"id": i, "values": list(range(i, i + 50000)), "text": "abc" * i}
        algorithm = algorithms[i % len(algorithms)]
        assert zpickle.loads(zpickle.dumps(data, algorithm=algorithm)) == data

        buffer = io.BytesIO()
        zpickle.dump(data, buffer, algorithm=algorithm)
        buffer.seek(0)
        assert zpickle.load(buffer) == data

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(roundtrip, range(32)))


@pytest.mark.parametrize("algorithm", ["zstd", "lz4", "none"])
def test_streaming_protocol5_picklebuffer(algorithm):
    """Protocol 5 (default from 3.14) writes large buffers as PickleBuffer."""
    payload = bytearray(rng_bytes := random.Random(1).randbytes(1_000_000))
    data = {"buffer": pickle.PickleBuffer(payload), "small": [1, 2, 3]}

    buffer = io.BytesIO()
    zpickle.dump(data, buffer, protocol=5, algorithm=algorithm)
    buffer.seek(0)
    restored = zpickle.load(buffer)

    assert restored["buffer"] == rng_bytes
    assert restored["small"] == [1, 2, 3]


MULTI_OBJECTS = [
    {"first": list(range(1000))},
    "second " * 500,
    [SampleObject(i) for i in range(100)],
]


@pytest.mark.parametrize("algorithm", sorted(zpickle.format.ALGORITHM_IDS))
def test_consecutive_dump_load(algorithm):
    """Consecutive load() calls read back objects from consecutive dump() calls."""
    buffer = io.BytesIO()
    for obj in MULTI_OBJECTS:
        zpickle.dump(obj, buffer, algorithm=algorithm)
    buffer.write(b"trailing bytes")
    buffer.seek(0)

    assert [zpickle.load(buffer) for _ in MULTI_OBJECTS] == MULTI_OBJECTS
    # The file is left just past the last object
    assert buffer.read() == b"trailing bytes"


def test_consecutive_dump_load_mixed_and_large(tmp_path):
    """Objects spanning many read chunks, with mixed algorithms, on a disk file."""
    rng = random.Random(2)
    objects = [
        rng.randbytes(3 * zpickle.DEFAULT_CHUNK_SIZE + 7),
        {"small": 1},
        rng.randbytes(zpickle.DEFAULT_CHUNK_SIZE),
        list(range(50000)),
    ]
    algorithms = ["zstd", "snappy", "none", "lzma"]

    path = tmp_path / "multi.zpkl"
    with open(path, "wb") as f:
        for obj, algorithm in zip(objects, algorithms):
            zpickle.dump(obj, f, algorithm=algorithm)

    with open(path, "rb") as f:
        assert [zpickle.load(f) for _ in objects] == objects
        assert f.read() == b""


@pytest.mark.parametrize("algorithm", ["zstd", "gzip", "snappy"])
def test_consecutive_load_from_pipe(algorithm):
    """Non-seekable buffered streams are peeked so no following bytes are lost."""
    rng = random.Random(3)
    objects = [rng.randbytes(200_000), {"middle": True}, rng.randbytes(100_000)]

    payload = io.BytesIO()
    for obj in objects:
        zpickle.dump(obj, payload, algorithm=algorithm)

    read_fd, write_fd = os.pipe()

    def writer():
        with os.fdopen(write_fd, "wb") as w:
            w.write(payload.getvalue())

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        with os.fdopen(read_fd, "rb") as r:
            assert not r.seekable()
            assert [zpickle.load(r) for _ in objects] == objects
            assert r.read() == b""
        future.result()


def test_load_from_unseekable_reader_without_peek():
    """A bare read()-only file still loads a single object."""

    class ReadOnly:
        def __init__(self, data):
            self._buffer = io.BytesIO(data)

        def read(self, size=-1):
            return self._buffer.read(size)

        def readline(self):
            return self._buffer.readline()

    data = {"values": list(range(10000))}
    buffer = io.BytesIO()
    zpickle.dump(data, buffer)

    assert zpickle.load(ReadOnly(buffer.getvalue())) == data


@pytest.mark.parametrize(
    "algorithm", sorted(set(zpickle.format.ALGORITHM_IDS) - {"none"})
)
def test_load_truncated_stream_raises(algorithm):
    """A stream cut short is an error even when pickle's STOP opcode was read."""
    buffer = io.BytesIO()
    zpickle.dump({"values": list(range(10000))}, buffer, algorithm=algorithm)

    with pytest.raises(Exception):
        zpickle.load(io.BytesIO(buffer.getvalue()[:-3]))
