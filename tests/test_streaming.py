"""
Tests for streaming compression/decompression functionality.
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


@pytest.fixture
def large_data():
    """Fixture that returns a large dataset for streaming tests."""
    return {
        "large_list": list(range(100000)),
        "large_string": "x" * 100000,
        "nested": {"level1": {"level2": {"data": list(range(10000))}}},
    }


class TestStreamingBasic:
    """Test basic streaming functionality."""

    def test_dump_streaming_load_streaming_roundtrip(self, test_data):
        """Test basic roundtrip with streaming functions."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == test_data
        assert isinstance(restored["object"], SampleObject)

    def test_dump_streaming_load_regular_roundtrip(self, test_data):
        """Test that streaming dump can be read by regular load."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer)

        buffer.seek(0)
        restored = zpickle.load(buffer)

        assert restored == test_data

    def test_dump_regular_load_streaming_roundtrip(self, test_data):
        """Test that regular dump can be read by streaming load."""
        buffer = io.BytesIO()
        zpickle.dump(test_data, buffer)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == test_data

    def test_streaming_with_disk_file(self, test_data):
        """Test streaming with actual disk files."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            try:
                zpickle.dump_streaming(test_data, temp)
                temp.close()

                with open(temp.name, "rb") as f:
                    restored = zpickle.load_streaming(f)

                assert restored == test_data
            finally:
                if os.path.exists(temp.name):
                    os.unlink(temp.name)


class TestStreamingAlgorithms:
    """Test streaming with different compression algorithms."""

    @pytest.mark.parametrize("algorithm", ["zstd", "brotli", "zlib", "lzma", "none"])
    def test_streaming_all_algorithms(self, test_data, algorithm):
        """Test streaming with all supported algorithms."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer, algorithm=algorithm)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == test_data

    @pytest.mark.parametrize("level", [1, 3, 5, 9])
    def test_streaming_compression_levels(self, test_data, level):
        """Test streaming with different compression levels."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer, algorithm="zstd", level=level)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == test_data


class TestStreamingLargeData:
    """Test streaming with large datasets."""

    def test_streaming_large_data(self, large_data):
        """Test streaming with large data."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(large_data, buffer)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == large_data

    def test_streaming_custom_chunk_size(self, large_data):
        """Test streaming with custom chunk sizes."""
        for chunk_size in [1024, 4096, 64 * 1024, 256 * 1024]:
            buffer = io.BytesIO()
            zpickle.dump_streaming(large_data, buffer, chunk_size=chunk_size)

            buffer.seek(0)
            restored = zpickle.load_streaming(buffer, chunk_size=chunk_size)

            assert restored == large_data


class TestNonSeekableStreams:
    """Test support for non-seekable streams."""

    def test_load_from_non_seekable_stream_zpickle_format(self, test_data):
        """Test loading zpickle data from a non-seekable stream."""
        # First create zpickle data
        buffer = io.BytesIO()
        zpickle.dump(test_data, buffer)
        data = buffer.getvalue()

        # Create a non-seekable stream wrapper
        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, n=-1):
                if n == -1:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + n]
                    self._pos += n
                return result

        stream = NonSeekableStream(data)
        restored = zpickle.load(stream)
        assert restored == test_data

    def test_load_from_non_seekable_stream_pickle_format(self, test_data):
        """Test loading regular pickle data from a non-seekable stream."""
        # Create regular pickle data
        data = pickle.dumps(test_data)

        # Create a non-seekable stream wrapper
        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, n=-1):
                if n == -1:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + n]
                    self._pos += n
                return result

        stream = NonSeekableStream(data)
        restored = zpickle.load(stream)
        assert restored == test_data

    def test_load_streaming_from_non_seekable_stream(self, test_data):
        """Test load_streaming from a non-seekable stream."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer)
        data = buffer.getvalue()

        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, n=-1):
                if n == -1:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + n]
                    self._pos += n
                return result

        stream = NonSeekableStream(data)
        restored = zpickle.load_streaming(stream)
        assert restored == test_data

    def test_unpickler_with_non_seekable_stream_zpickle(self, test_data):
        """Test Unpickler class with non-seekable stream (zpickle format)."""
        buffer = io.BytesIO()
        zpickle.dump(test_data, buffer)
        data = buffer.getvalue()

        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, n=-1):
                if n == -1:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + n]
                    self._pos += n
                return result

        stream = NonSeekableStream(data)
        unpickler = zpickle.Unpickler(stream)
        restored = unpickler.load()
        assert restored == test_data

    def test_unpickler_with_non_seekable_stream_pickle(self, test_data):
        """Test Unpickler class with non-seekable stream (regular pickle)."""
        data = pickle.dumps(test_data)

        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, n=-1):
                if n == -1:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + n]
                    self._pos += n
                return result

        stream = NonSeekableStream(data)
        unpickler = zpickle.Unpickler(stream)
        restored = unpickler.load()
        assert restored == test_data


class TestStreamingSmallData:
    """Test streaming behavior with small data (below min_size threshold)."""

    def test_streaming_small_data_skips_compression(self):
        """Test that small data is not compressed even with streaming."""
        small_data = {"a": 1}
        buffer = io.BytesIO()
        zpickle.dump_streaming(small_data, buffer)

        buffer.seek(0)
        # Check that algorithm is 'none' (id=0) in header
        header = buffer.read(8)
        assert header[5] == 0  # Algorithm ID for 'none'

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)
        assert restored == small_data


class TestStreamingPickleProtocols:
    """Test streaming with different pickle protocols."""

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_streaming_all_protocols(self, test_data, protocol):
        """Test streaming with all pickle protocols."""
        buffer = io.BytesIO()
        zpickle.dump_streaming(test_data, buffer, protocol=protocol)

        buffer.seek(0)
        restored = zpickle.load_streaming(buffer)

        assert restored == test_data


class TestDefaultChunkSize:
    """Test the DEFAULT_CHUNK_SIZE constant."""

    def test_default_chunk_size_exported(self):
        """Test that DEFAULT_CHUNK_SIZE is exported."""
        assert hasattr(zpickle, "DEFAULT_CHUNK_SIZE")
        assert zpickle.DEFAULT_CHUNK_SIZE == 64 * 1024  # 64KB
