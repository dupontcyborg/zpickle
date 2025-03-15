"""
Compatibility classes for pickle API.

This module provides Pickler and Unpickler classes that are compatible
with the pickle API but add transparent compression support.
"""

import io
import pickle
from typing import Any, BinaryIO, Optional

from compress_utils import compress, decompress

from .config import get_config
from .format import (
    HEADER_SIZE, encode_header, decode_header,
    is_zpickle_data
)

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
    def __init__(self, file, protocol=None, *, fix_imports=True, 
                buffer_callback=None, algorithm=None, level=None):
        self.file = file
        config = get_config()
        self.algorithm = algorithm or config.algorithm
        self.level = level or config.level
        self.min_size = config.min_size

        # Create a temporary BytesIO for the pickle data
        self._buffer = io.BytesIO()

        # Initialize the pickler with our buffer
        super().__init__(
            self._buffer, protocol, 
            fix_imports=fix_imports, 
            buffer_callback=buffer_callback
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
        if len(pickled_data) < self.min_size or self.algorithm == 'none':
            # Still add header for consistency
            header = encode_header('none', 0)
            self.file.write(header + pickled_data)
            return

        # Compress the pickle data
        compressed_data = compress(pickled_data, self.algorithm, self.level)

        # Create header and write with compressed data
        header = encode_header(self.algorithm, self.level)
        self.file.write(header + compressed_data)

class Unpickler(pickle.Unpickler):
    """Subclass of pickle.Unpickler that handles compressed input.
    
    Args:
        file: A file-like object with read and seek methods
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        
    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     unpickler = zpickle.Unpickler(f)
        ...     data = unpickler.load()
    """
    def __init__(self, file, *, fix_imports=True, encoding='ASCII', 
                errors='strict', buffers=None):
        self.file = file

        # Read the header to check format
        header = file.read(HEADER_SIZE)

        if is_zpickle_data(header):
            # This is zpickle data, get algorithm info
            _, algorithm, _, _ = decode_header(header)

            # Read the rest of the file
            compressed_data = file.read()

            # If algorithm is 'none', data wasn't compressed
            if algorithm == 'none':
                pickled_data = compressed_data
            else:
                # Decompress the data
                pickled_data = decompress(compressed_data, algorithm)

            # Create a BytesIO with the unpickled data
            self._buffer = io.BytesIO(pickled_data)

            # Initialize the unpickler with our buffer
            super().__init__(
                self._buffer, 
                fix_imports=fix_imports, 
                encoding=encoding, 
                errors=errors, 
                buffers=buffers
            )
        else:
            # Assume it's regular pickle data, reset file position
            file.seek(0)

            # Initialize the unpickler with the original file
            super().__init__(
                file, 
                fix_imports=fix_imports, 
                encoding=encoding, 
                errors=errors, 
                buffers=buffers
            )
