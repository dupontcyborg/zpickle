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
    data = dumps(
        obj,
        protocol,
        fix_imports=fix_imports,
        buffer_callback=buffer_callback,
        algorithm=algorithm,
        level=level,
    )
    file.write(data)


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

    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     data = zpickle.load(f)
    """
    # Read the header first to determine format
    header = file.read(HEADER_SIZE)

    if is_zpickle_data(header):
        try:
            # This is zpickle data, get algorithm info
            _, algorithm, _, _ = decode_header(header, strict)

            # Read the rest of the file
            compressed_data = file.read()

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
            # Buffer header bytes for non-seekable stream support
            pickled_data = header + file.read()
    else:
        # Not zpickle format - include header bytes in pickled data
        # This handles non-seekable streams properly
        pickled_data = header + file.read()

    # Unpickle and return
    return pickle.loads(
        pickled_data,
        fix_imports=fix_imports,
        encoding=encoding,
        errors=errors,
        buffers=buffers,
    )


def dump_streaming(
    obj: Any,
    file: BinaryIO,
    protocol: Optional[int] = None,
    *,
    fix_imports: bool = True,
    buffer_callback: Optional[Any] = None,
    algorithm: Optional[str] = None,
    level: Optional[int] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Pickle and compress an object using streaming compression.

    This function uses streaming compression to reduce memory usage when
    serializing large objects. Instead of compressing all data at once,
    it processes the data in chunks.

    Args:
        obj: The Python object to pickle and compress
        file: A file-like object with a write method
        protocol: The pickle protocol to use
        fix_imports: Fix imports for Python 2 compatibility
        buffer_callback: Callback for handling buffer objects
        algorithm: Compression algorithm to use (overrides global config)
        level: Compression level to use (overrides global config)
        chunk_size: Size of chunks for streaming compression (default 64KB)

    Example:
        >>> import zpickle
        >>> large_data = {"example": list(range(1000000))}
        >>> with open('data.zpkl', 'wb') as f:
        ...     zpickle.dump_streaming(large_data, f)
    """
    # Get compression settings
    config = get_config()
    alg = algorithm or config.algorithm
    lvl = level or config.level

    # First, pickle the object to a buffer
    # We need to pickle first to know the size and to stream it
    pickled_buffer = io.BytesIO()
    pickle.dump(
        obj,
        pickled_buffer,
        protocol,
        fix_imports=fix_imports,
        buffer_callback=buffer_callback,
    )
    pickled_buffer.seek(0)

    # Skip compression for very small objects or if algorithm is 'none'
    pickled_size = pickled_buffer.seek(0, 2)  # Seek to end to get size
    pickled_buffer.seek(0)  # Reset to beginning

    if pickled_size < config.min_size or alg == "none":
        # Still add header for consistency
        header = encode_header("none", 0)
        file.write(header)
        # Write pickled data directly
        while True:
            chunk = pickled_buffer.read(chunk_size)
            if not chunk:
                break
            file.write(chunk)
        return

    # Write header first
    header = encode_header(alg, lvl)
    file.write(header)

    # Create streaming compressor
    compressor = CompressStream(alg, lvl)

    # Stream compress and write
    while True:
        chunk = pickled_buffer.read(chunk_size)
        if not chunk:
            break
        compressed_chunk = compressor.compress(chunk)
        if compressed_chunk:
            file.write(compressed_chunk)

    # Finish compression and write any remaining data
    final_chunk = compressor.finish()
    if final_chunk:
        file.write(final_chunk)


def load_streaming(
    file: BinaryIO,
    *,
    fix_imports: bool = True,
    encoding: str = "ASCII",
    errors: str = "strict",
    buffers: Optional[Any] = None,
    strict: bool = True,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Any:
    """Decompress and unpickle an object using streaming decompression.

    This function uses streaming decompression to reduce memory usage when
    deserializing large objects. Instead of decompressing all data at once,
    it processes the data in chunks.

    Args:
        file: A file-like object with read method
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        strict: If True, raises errors for unsupported versions/algorithms.
               If False, attempts to load the data with warnings.
        chunk_size: Size of chunks for streaming decompression (default 64KB)

    Returns:
        Any: The unpickled Python object

    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     data = zpickle.load_streaming(f)
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

            if algorithm == "none":
                # No compression, stream directly to buffer
                pickled_buffer = io.BytesIO()
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    pickled_buffer.write(chunk)
                pickled_data = pickled_buffer.getvalue()
            else:
                # Create streaming decompressor
                decompressor = DecompressStream(algorithm)
                pickled_buffer = io.BytesIO()

                # Stream decompress
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    decompressed_chunk = decompressor.decompress(chunk)
                    if decompressed_chunk:
                        pickled_buffer.write(decompressed_chunk)

                # Finish decompression
                final_chunk = decompressor.finish()
                if final_chunk:
                    pickled_buffer.write(final_chunk)

                pickled_data = pickled_buffer.getvalue()

        except Exception as e:
            if strict:
                raise

            # In non-strict mode, fall back to treating as regular pickle
            warnings.warn(
                f"Error processing zpickle data, falling back to regular pickle: {e}",
                RuntimeWarning,
            )
            # For streaming, we can't seek back, so we need to include header
            pickled_data = header + file.read()
    else:
        # Not zpickle format - include header bytes in pickled data
        # This handles non-seekable streams properly
        remaining_data = file.read()
        pickled_data = header + remaining_data

    # Unpickle and return
    return pickle.loads(
        pickled_data,
        fix_imports=fix_imports,
        encoding=encoding,
        errors=errors,
        buffers=buffers,
    )
