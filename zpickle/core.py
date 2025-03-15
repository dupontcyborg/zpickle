"""
Core serialization functions for zpickle.

This module implements the main serialization and deserialization
functions (dumps, loads, dump, load) with compression support.
"""

import pickle
from typing import Any, BinaryIO, Optional, Union

from compress_utils import compress, decompress

from .config import get_config
from .format import (
    HEADER_SIZE, encode_header, decode_header,
    is_zpickle_data
)

def dumps(obj: Any, 
          protocol: Optional[int] = None, 
          *, 
          fix_imports: bool = True,
          buffer_callback: Optional[Any] = None,
          algorithm: Optional[str] = None,
          level: Optional[int] = None) -> bytes:
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
        obj, protocol, 
        fix_imports=fix_imports, 
        buffer_callback=buffer_callback
    )

    # Get compression settings
    config = get_config()
    alg = algorithm or config.algorithm
    lvl = level or config.level

    # Skip compression for very small objects
    if len(pickled_data) < config.min_size or alg == 'none':
        # Still add header for consistency
        header = encode_header('none', 0)
        return header + pickled_data

    # Compress the pickle data
    compressed_data = compress(pickled_data, alg, lvl)

    # Create header and combine with compressed data
    header = encode_header(alg, lvl)
    return header + compressed_data

def loads(data: bytes, 
          *, 
          fix_imports: bool = True, 
          encoding: str = 'ASCII', 
          errors: str = 'strict',
          buffers: Optional[Any] = None) -> Any:
    """Decompress and unpickle an object from a bytes object.
    
    Args:
        data: The compressed pickled bytes to load
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        
    Returns:
        Any: The unpickled Python object
        
    Example:
        >>> import zpickle
        >>> data = zpickle.dumps({"example": "data"})
        >>> obj = zpickle.loads(data)
        >>> obj
        {'example': 'data'}
    """
    # Check if this is zpickle data
    if is_zpickle_data(data):
        # Extract header info
        _, algorithm, _, _ = decode_header(data)

        # Get the compressed data (after header)
        compressed_data = data[HEADER_SIZE:]

        # If algorithm is 'none', data wasn't compressed
        if algorithm == 'none':
            pickled_data = compressed_data
        else:
            # Decompress the data
            pickled_data = decompress(compressed_data, algorithm)
    else:
        # Fallback to regular pickle data
        pickled_data = data

    # Unpickle and return
    return pickle.loads(
        pickled_data, 
        fix_imports=fix_imports, 
        encoding=encoding, 
        errors=errors,
        buffers=buffers
    )

def dump(obj: Any, 
         file: BinaryIO, 
         protocol: Optional[int] = None, 
         *, 
         fix_imports: bool = True,
         buffer_callback: Optional[Any] = None,
         algorithm: Optional[str] = None,
         level: Optional[int] = None) -> None:
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
        obj, protocol, 
        fix_imports=fix_imports, 
        buffer_callback=buffer_callback,
        algorithm=algorithm,
        level=level
    )
    file.write(data)

def load(file: BinaryIO, 
         *, 
         fix_imports: bool = True, 
         encoding: str = 'ASCII', 
         errors: str = 'strict',
         buffers: Optional[Any] = None) -> Any:
    """Decompress and unpickle an object from a file.
    
    Args:
        file: A file-like object with read and seek methods
        fix_imports: Fix imports for Python 2 compatibility
        encoding: Encoding for 8-bit string instances unpickled from str
        errors: Error handling scheme for decode errors
        buffers: Optional iterables of buffer-enabled objects
        
    Returns:
        Any: The unpickled Python object
        
    Example:
        >>> import zpickle
        >>> with open('data.zpkl', 'rb') as f:
        ...     data = zpickle.load(f)
    """
    # Read the header first to determine format
    header = file.read(HEADER_SIZE)

    if header[:4] == b'ZPKL':
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
    else:
        # Fallback to regular pickle data, reset file position and read all
        file.seek(0)
        pickled_data = file.read()

    # Unpickle and return
    return pickle.loads(
        pickled_data,
        fix_imports=fix_imports,
        encoding=encoding,
        errors=errors,
        buffers=buffers
    )
