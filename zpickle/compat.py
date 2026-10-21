"""
Compatibility classes for pickle API.

This module provides Pickler and Unpickler classes that are compatible
with the pickle API but add transparent compression support.
"""

import io
import pickle

from compress_utils import DecompressStream, compress

from .config import get_config
from .core import DecompressingReader, HeaderPrependReader
from .format import HEADER_SIZE, decode_header, encode_header, is_zpickle_data


class Pickler(pickle.Pickler):
    """Subclass of pickle.Pickler that produces compressed output.

    Args:
        file: A file-like object with a write method
        protocol: The pickle protocol to use
        fix_imports: Fix imports for Python 2 compatibility
        buffer_callback: Callback for handling buffer objects
        algorithm: Compression algorithm to use (overrides global config)
        level: Compression level to use (overrides global config)

    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'wb') as f:
        ...     pickler = zpickle.Pickler(f)
        ...     pickler.dump({"example": "data"})
    """

    def __init__(
        self,
        file,
        protocol=None,
        *,
        fix_imports=True,
        buffer_callback=None,
        algorithm=None,
        level=None,
    ):
        self.file = file
        config = get_config()
        self.algorithm = algorithm or config.algorithm
        self.level = level or config.level
        self.min_size = config.min_size

        # Create a temporary BytesIO for the pickle data
        self._buffer = io.BytesIO()

        # Initialize the pickler with our buffer
        super().__init__(
            self._buffer,
            protocol,
            fix_imports=fix_imports,
            buffer_callback=buffer_callback,
        )

    def dump(self, obj):
        """Write a compressed pickled representation of obj to the file.

        Args:
            obj: The Python object to pickle and compress
        """
        # First pickle to our internal buffer
        super().dump(obj)

        # Get the pickled data
        self._buffer.seek(0)
        pickled_data = self._buffer.getvalue()
        self._buffer.seek(0)
        self._buffer.truncate(0)

        # Skip compression for very small objects or if algorithm is 'none'
        if len(pickled_data) < self.min_size or self.algorithm == "none":
            # Still add header for consistency
            header = encode_header("none", 0)
            self.file.write(header + pickled_data)
            return

        # Compress the pickle data
        compressed_data = compress(pickled_data, self.algorithm, self.level)

        # Create header and write with compressed data
        header = encode_header(self.algorithm, self.level)
        self.file.write(header + compressed_data)


class _CurrentObjectReader:
    """File object pickle.Unpickler reads from, forwarding to the current object.

    pickle.Unpickler binds its file once, at construction. Each zpickle object
    has its own header and compressed stream, so load() points this at a new
    reader per object while the same unpickler, and its memo, is reused.
    """

    def __init__(self):
        self.source = None

    def read(self, size=-1):
        return self.source.read(size)

    def readline(self):
        return self.source.readline()


class Unpickler(pickle.Unpickler):
    """Subclass of pickle.Unpickler that handles compressed input.

    Args:
        file: A file-like object with a read method (seek not required)
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects

    Note:
        This class supports non-seekable streams (pipes, sockets) by
        buffering the header bytes instead of seeking.

        As with pickle.Unpickler, each load() call reads the next object, so
        objects written by repeated Pickler.dump() calls can be read back
        (see zpickle.load() for the file types this needs).

    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     unpickler = zpickle.Unpickler(f)
        ...     data = unpickler.load()
    """

    def __init__(
        self, file, *, fix_imports=True, encoding="ASCII", errors="strict", buffers=None
    ):
        self.file = file
        self._reader = _CurrentObjectReader()
        # Bytes read while checking for a header that a short regular pickle
        # didn't use; they start the next object
        self._pending = b""

        super().__init__(
            self._reader,
            fix_imports=fix_imports,
            encoding=encoding,
            errors=errors,
            buffers=buffers,
        )

    def load(self):
        """Read and decompress the next pickled object from the file.

        Returns:
            The unpickled Python object
        """
        header = self._pending + self.file.read(HEADER_SIZE - len(self._pending))
        self._pending = b""

        if not is_zpickle_data(header):
            # Regular pickle data
            prefixed = HeaderPrependReader(header, self.file)
            self._reader.source = prefixed
            obj = super().load()
            self._pending = prefixed.header
            return obj

        _, algorithm, _, _ = decode_header(header)

        if algorithm == "none":
            # Data wasn't compressed, read it directly from the file
            self._reader.source = self.file
            return super().load()

        stream = DecompressingReader(
            self.file, DecompressStream(algorithm, single_stream=True)
        )
        self._reader.source = stream
        obj = super().load()
        stream.drain()
        return obj
