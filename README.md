# zpickle

<p align="center">
  <img src="https://img.shields.io/github/workflow/status/dupontcyborg/zpickle/test_and_package_wheel" alt="Build Status"/>
  <img src="https://img.shields.io/pypi/v/zpickle" alt="PyPI Version"/>
  <img src="https://img.shields.io/github/v/release/dupontcyborg/zpickle" alt="GitHub Release"/>
</p>
<p align="center">
  <img src="https://img.shields.io/pypi/pyversions/zpickle" alt="Python Versions"/>
  <img src="https://img.shields.io/github/license/dupontcyborg/zpickle" alt="License"/>
  <img src="https://static.pepy.tech/badge/zpickle" alt="PyPI Downloads">
</p>

**Transparent, drop-in compression for Python's pickle — smaller files, same API.**

`zpickle` adds high-performance compression to your serialized Python objects using multiple state-of-the-art algorithms without changing how you work with pickle.

```python
# Replace this:
import pickle

# With this:
import zpickle as pickle

# Everything else stays the same!
```

## Features

- **Drop-in replacement** for the standard `pickle` module
- **Transparent compression** — everything happens automatically
- **Multiple algorithms** — choose `zstd`, `brotli`, `zlib`, or `lzma` (powered by [`compress_utils`](https://github.com/dupontcyborg/compress-utils))
- **Configure once, use everywhere** — set global defaults for your entire app
- **Smaller data** — 2-10× smaller serialized data (depending on content and algorithm)
- **Backward compatible** — automatically reads both compressed and regular pickle data
- **Complete API compatibility** — all pickle functions work as expected

## Installation

```bash
pip install zpickle
```

## Quick Start

### Basic Usage

```python
import zpickle as pickle

# Serializing works exactly like pickle
data = {"complex": ["nested", {"data": "structure"}], "with": "lots of repetition"}
serialized = pickle.dumps(data)  # Automatically compressed!

# Deserializing works the same way
restored = pickle.loads(serialized)  # Automatically decompressed!

# File operations work too
with open("data.zpkl", "wb") as f:
    pickle.dump(data, f)

with open("data.zpkl", "rb") as f:
    restored = pickle.load(f)
```

### Custom Configuration

```python
import zpickle

# Configure global settings
zpickle.configure(algorithm='brotli', level=9)  # Higher compression

# Or configure for a single operation
data = [1, 2, 3] * 1000
compressed = zpickle.dumps(data, algorithm='zstd', level=6)
```

## Performance

Compression ratios versus standard pickle (higher is better):

| Data Type | zstd (default) | brotli | zlib | lzma |
|-----------|----------------|--------|------|------|
| Dict/List | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| NumPy     | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Text      | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Binary    | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

Compression speed (MB/s, higher is better):

| Algorithm  | Level 1 | Level 3 (default) | Level 9 |
|------------|---------|-------------------|---------|
| `zstd`       | _TBD_ | _TBD_ | _TBD_ |
| `brotli`     | _TBD_ | _TBD_ | _TBD_ |
| `zlib`       | _TBD_ | _TBD_ | _TBD_ |
| `lzma`       | _TBD_ | _TBD_ | _TBD_ |

*Note: Performance varies by data characteristics. Run benchmarks on your specific data for accurate results.*

## How It Works

`zpickle` applies compression with minimal overhead:

1. Objects are first serialized using standard pickle
2. The pickle data is compressed using the selected algorithm
3. A small header (7 bytes) is added to identify the format and algorithm
4. When deserializing, `zpickle` auto-detects the format and decompresses if needed

## API Reference

`zpickle` maintains complete API compatibility with the standard pickle module:

### Core Functions

- `dumps(obj, protocol=None, ..., algorithm=None, level=None)` - Serialize and compress object
- `loads(data, ...)` - Deserialize and decompress object
- `dump(obj, file, protocol=None, ..., algorithm=None, level=None)` - Serialize to file
- `load(file, ...)` - Deserialize from file

### Configuration

- `configure(algorithm=None, level=None, min_size=None)` - Set global defaults
- `get_config()` - Get current configuration

### Classes

- `Pickler(file, ...)` - Subclass of pickle.Pickler with compression
- `Unpickler(file, ...)` - Subclass of pickle.Unpickler with decompression

## Alternatives

- **Standard `pickle`**: No compression, but native to Python
- **`compressed_pickle`**: Similar concept, but less configurable
- **`joblib`**: More focused on large NumPy arrays and parallel processing
- **`msgpack`, `protobuf`**: Different serialization formats (not pickle-compatible)

## License

This project is distributed under the MIT License. [Read more >](LICENSE)

## Links

- [GitHub Repository](https://github.com/dupontcyborg/zpickle)
- [PyPI Package](https://pypi.org/project/zpickle/)
- [Issue Tracker](https://github.com/dupontcyborg/zpickle/issues)
- [compress-utils](https://github.com/dupontcyborg/compress-utils) - The underlying compression library