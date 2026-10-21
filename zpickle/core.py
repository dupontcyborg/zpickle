"""
Core serialization functions for zpickle.

This module implements the main serialization and deserialization
functions (dumps, loads, dump, load) with compression support.
"""

import io
import pickle
import warnings
from typing import Any, BinaryIO, Optional

from compress_utils import compress, decompress, CompressStream, DecompressStream

from .config import get_config
from .format import HEADER_SIZE, decode_header, encode_header, is_zpickle_data

# Default chunk size for streaming operations (64KB)
DEFAULT_CHUNK_SIZE = 64 * 1024

# Minimum batch size handed to the compressor. compress-utils releases the GIL
# for calls of at least 256KB, so batching pickle's ~64KB frames lets other
# threads run while we compress.
COMPRESS_BATCH_SIZE = 256 * 1024


class CompressingWriter:
    """Wrapper that compresses data as it's written."""

    def __init__(self, file: BinaryIO, compressor: CompressStream):
        self.file = file
        self.compressor = compressor
        self.pending = bytearray()

    def write(self, data: bytes) -> int:
        """Buffer data and compress it in batches to the underlying file."""
        # Protocol 5 (the default from Python 3.14) passes large buffers as
        # PickleBuffer objects, which support the buffer protocol but not len()
        with memoryview(data) as view:
            size = view.nbytes
        if not self.pending and size >= COMPRESS_BATCH_SIZE:
            # Large writes (e.g. big bytes objects) skip the buffer copy
            compressed = self.compressor.compress(data)
        else:
            self.pending += data
            if len(self.pending) < COMPRESS_BATCH_SIZE:
                return size
            compressed = self.compressor.compress(self.pending)
            self.pending = bytearray()
        if compressed:
            self.file.write(compressed)
        return size  # Return original data length for pickle

    def finish(self):
        """Compress any buffered data and end the compressed stream."""
        final = self.compressor.compress(self.pending) if self.pending else b""
        final += self.compressor.finish()
        self.pending = bytearray()
        if final:
            self.file.write(final)


class DecompressingReader:
    """Wrapper that decompresses data as it's read.

    The decompressor must be a single_stream DecompressStream, so reading stops
    at the end of the compressed stream. Bytes read past that end are handed
    back to the file, leaving it positioned at whatever follows the stream
    (e.g. the next zpickle object).
    """

    def __init__(
        self,
        file: BinaryIO,
        decompressor: DecompressStream,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.file = file
        self.decompressor = decompressor
        # bytearray appends and front deletions are amortized O(1), so large
        # reads assembled from many chunks don't re-copy the whole buffer
        self.buffer = bytearray()
        self.chunk_size = chunk_size
        self.finished = False
        # Seekable files take back over-read bytes with a seek. Non-seekable
        # buffered streams (pipes, sockets) are peeked instead, consuming only
        # the bytes the decompressor used. Other files lose any over-read bytes.
        seekable = getattr(file, "seekable", None)
        self.seekable = bool(seekable and seekable())
        self._peek = None if self.seekable else getattr(file, "peek", None)

    def read(self, size: int = -1) -> bytes:
        """Read and decompress data from the underlying file."""
        # If size=-1, read everything
        if size is None or size < 0:
            # Read and decompress all remaining data
            while not self.finished:
                self._decompress_next_chunk()
            size = len(self.buffer)
        else:
            # Read enough to satisfy the request
            while len(self.buffer) < size and not self.finished:
                self._decompress_next_chunk()

        # Return requested amount from buffer
        with memoryview(self.buffer) as view, view[:size] as head:
            result = bytes(head)
        del self.buffer[:size]
        return result

    def readline(self) -> bytes:
        """Read a line - pickle doesn't actually use this but requires it."""
        # Pickle requires this method but doesn't use it for protocol >= 2
        return b""

    def drain(self):
        """Read to the end of the compressed stream.

        pickle stops reading at its STOP opcode, which can come before the end
        of the compressed stream (e.g. a trailing checksum). Draining verifies
        the rest of the stream and leaves the file just past it.
        """
        while not self.finished:
            self._decompress_next_chunk()

    def _decompress_next_chunk(self):
        """Read and decompress the next chunk from file."""
        if self._peek is not None:
            compressed_chunk = self._peek(self.chunk_size)
        else:
            compressed_chunk = self.file.read(self.chunk_size)

        if not compressed_chunk:
            # File exhausted before the end of the stream: finish() raises if
            # the stream is truncated
            final = self.decompressor.finish()
            if final:
                self.buffer += final
            self.finished = True
            return

        decompressed = self.decompressor.decompress(compressed_chunk)
        if decompressed:
            self.buffer += decompressed

        unused = len(self.decompressor.unused_data) if self.decompressor.eof else 0
        if self._peek is not None:
            self.file.read(len(compressed_chunk) - unused)
        elif unused and self.seekable:
            self.file.seek(-unused, io.SEEK_CUR)
        if self.decompressor.eof:
            self.finished = True


def dumps(
    obj: Any,
    protocol: Optional[int] = None,
    *,
    fix_imports: bool = True,
    buffer_callback: Optional[Any] = None,
    algorithm: Optional[str] = None,
    level: Optional[int] = None,
) -> bytes:
    """Pickle and compress an object to a bytes object.

    Args:
        obj: The Python object to pickle and compress
        protocol: The pickle protocol to use
        fix_imports: Fix imports for Python 2 compatibility
        buffer_callback: Callback for handling buffer objects
        algorithm: Compression algorithm to use (overrides global config)
        level: Compression level to use (overrides global config)

    Returns:
        bytes: The compressed pickled object with zpickle header

    Example:
        >>> import zpickle
        >>> data = {"example": "data"}
        >>> compressed = zpickle.dumps(data)
    """
    # Use pickle to serialize the object
    pickled_data = pickle.dumps(
        obj, protocol, fix_imports=fix_imports, buffer_callback=buffer_callback
    )

    # Get compression settings
    config = get_config()
    alg = algorithm or config.algorithm
    lvl = level or config.level

    # Skip compression for very small objects
    if len(pickled_data) < config.min_size or alg == "none":
        # Still add header for consistency
        header = encode_header("none", 0)
        return header + pickled_data

    # Compress the pickle data
    compressed_data = compress(pickled_data, alg, lvl)

    # Create header and combine with compressed data
    header = encode_header(alg, lvl)
    return header + compressed_data


def loads(
    data: bytes,
    *,
    fix_imports: bool = True,
    encoding: str = "ASCII",
    errors: str = "strict",
    buffers: Optional[Any] = None,
    strict: bool = True,
) -> Any:
    """Decompress and unpickle an object from a bytes object.

    Args:
        data: The compressed pickled bytes to load
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        strict: If True, raises errors for unsupported versions/algorithms.
               If False, attempts to load the data with warnings.

    Returns:
        Any: The unpickled Python object

    Example:
        >>> import zpickle
        >>> data = zpickle.dumps({"example": "data"})
        >>> obj = zpickle.loads(data)
        >>> obj
        {'example': 'data'}
    """
    # Check that data is a bytes-like object
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"A bytes-like object is required, not '{type(data).__name__}'")

    # Check if this is zpickle data
    if is_zpickle_data(data):
        try:
            # Extract header info
            _, algorithm, _, _ = decode_header(data, strict)

            # Get the compressed data (after header)
            compressed_data = data[HEADER_SIZE:]

            # Decompress based on algorithm
            if algorithm == "none":
                pickled_data = compressed_data
            else:
                # Decompress the data
                pickled_data = decompress(compressed_data, algorithm)

        except Exception as e:
            if strict:
                raise

            # In non-strict mode, fall back to treating as regular pickle
            warnings.warn(
                f"Error processing zpickle data, falling back to regular pickle: {e}",
                RuntimeWarning,
            )
            pickled_data = data
    else:
        # Fallback to regular pickle data
        pickled_data = data

    # Unpickle and return
    return pickle.loads(
        pickled_data,
        fix_imports=fix_imports,
        encoding=encoding,
        errors=errors,
        buffers=buffers,
    )


def dump(
    obj: Any,
    file: BinaryIO,
    protocol: Optional[int] = None,
    *,
    fix_imports: bool = True,
    buffer_callback: Optional[Any] = None,
    algorithm: Optional[str] = None,
    level: Optional[int] = None,
) -> None:
    """Pickle and compress an object, writing the result to a file.

    This function uses streaming compression to reduce memory usage when
    serializing objects. The data is compressed as pickle writes it, avoiding
    the need to buffer the entire pickled object in memory.

    Args:
        obj: The Python object to pickle and compress
        file: A file-like object with a write method
        protocol: The pickle protocol to use
        fix_imports: Fix imports for Python 2 compatibility
        buffer_callback: Callback for handling buffer objects
        algorithm: Compression algorithm to use (overrides global config)
        level: Compression level to use (overrides global config)

    Example:
        >>> import zpickle
        >>> data = {"example": "data"}
        >>> with open('data.zpkl', 'wb') as f:
        ...     zpickle.dump(data, f)
    """
    # Get compression settings
    config = get_config()
    alg = algorithm or config.algorithm
    lvl = level or config.level

    # Write header first
    header = encode_header(alg, lvl)
    file.write(header)

    # Skip compression for 'none' algorithm
    if alg == "none":
        # Write pickled data directly (no compression)
        pickle.dump(
            obj,
            file,
            protocol,
            fix_imports=fix_imports,
            buffer_callback=buffer_callback,
        )
        return

    # Create streaming compressor
    compressor = CompressStream(alg, lvl)
    writer = CompressingWriter(file, compressor)

    # Stream pickle → compress → file
    pickle.dump(
        obj,
        writer,
        protocol,
        fix_imports=fix_imports,
        buffer_callback=buffer_callback,
    )

    # Compress any buffered data and end the stream
    writer.finish()


def load(
    file: BinaryIO,
    *,
    fix_imports: bool = True,
    encoding: str = "ASCII",
    errors: str = "strict",
    buffers: Optional[Any] = None,
    strict: bool = True,
) -> Any:
    """Decompress and unpickle an object from a file.

    This function uses streaming decompression to reduce memory usage when
    deserializing objects. The data is decompressed as pickle reads it, avoiding
    the need to buffer the entire compressed object in memory.

    Args:
        file: A file-like object with a read method (seek not required)
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        strict: If True, raises errors for unsupported versions/algorithms.
               If False, attempts to load the data with warnings.

    Returns:
        Any: The unpickled Python object

    Note:
        This function supports non-seekable streams (pipes, sockets) by
        buffering the header bytes instead of seeking.

        As with pickle, objects written by consecutive dump() calls can be
        read back by consecutive load() calls: each load() leaves the file
        positioned at the next object. This needs a seekable file or one with
        a peek() method (e.g. io.BufferedReader, which covers pipes and
        sockets opened in binary mode).

    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     data = zpickle.load(f)
    """
    # Read the header first to determine format
    header = file.read(HEADER_SIZE)

    if len(header) < HEADER_SIZE:
        # Not enough data for header, treat as regular pickle
        # Buffer the header bytes for non-seekable streams
        pickled_data = header + file.read()
        return pickle.loads(
            pickled_data,
            fix_imports=fix_imports,
            encoding=encoding,
            errors=errors,
            buffers=buffers,
        )

    if is_zpickle_data(header):
        try:
            # This is zpickle data, get algorithm info
            _, algorithm, _, _ = decode_header(header, strict)

            # Handle uncompressed data
            if algorithm == "none":
                # No compression, read directly from file
                return pickle.load(
                    file,
                    fix_imports=fix_imports,
                    encoding=encoding,
                    errors=errors,
                    buffers=buffers,
                )

            # Create streaming decompressor that stops at the end of this
            # object's stream, so further objects in the file can be loaded
            decompressor = DecompressStream(algorithm, single_stream=True)
            reader = DecompressingReader(file, decompressor)

            # Stream file → decompress → pickle.load()
            obj = pickle.load(
                reader,
                fix_imports=fix_imports,
                encoding=encoding,
                errors=errors,
                buffers=buffers,
            )
            reader.drain()
            return obj

        except Exception as e:
            if strict:
                raise

            # In non-strict mode, fall back to treating as regular pickle
            warnings.warn(
                f"Error processing zpickle data, falling back to regular pickle: {e}",
                RuntimeWarning,
            )
            # For non-seekable streams, we can't go back - this is best effort
            pickled_data = header + file.read()
            return pickle.loads(
                pickled_data,
                fix_imports=fix_imports,
                encoding=encoding,
                errors=errors,
                buffers=buffers,
            )
    else:
        # Not zpickle format - include header bytes for non-seekable streams
        # We need to wrap the file with a reader that first yields the header
        class HeaderPrependReader:
            def __init__(self, header_bytes, file_obj):
                self.header = header_bytes
                self.file = file_obj
                self.header_consumed = False

            def read(self, size=-1):
                if not self.header_consumed:
                    self.header_consumed = True
                    if size == -1:
                        return self.header + self.file.read()
                    elif size <= len(self.header):
                        result = self.header[:size]
                        self.header = self.header[size:]
                        self.header_consumed = len(self.header) == 0
                        return result
                    else:
                        remaining = size - len(self.header)
                        result = self.header + self.file.read(remaining)
                        self.header = b""
                        return result
                else:
                    return self.file.read(size)

            def readline(self):
                """Read a line - pickle doesn't actually use this but requires it."""
                return b""

        reader = HeaderPrependReader(header, file)
        return pickle.load(
            reader,
            fix_imports=fix_imports,
            encoding=encoding,
            errors=errors,
            buffers=buffers,
        )
