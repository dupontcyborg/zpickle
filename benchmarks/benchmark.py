#!/usr/bin/env python
"""
Benchmark script for zpickle comparing performance across algorithms and data types.

This script downloads or creates realistic test data, benchmarks compression/decompression speed,
measures compression ratios, and produces tables and graphs comparing results.
"""

import argparse
import gc
import json
import os
import pickle
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request

# Try to import visualization dependencies
try:
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns
    HAS_PLOTTING = True
except ImportError:
    HAS_PLOTTING = False
    print("Warning: matplotlib, pandas, or seaborn not found. Visualizations will be skipped.")

# Try to import optional dependencies for additional data types
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("Warning: NumPy not found. NumPy array tests will be skipped.")

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    import zpickle
except ImportError:
    print("Error: zpickle package not found. Please install it first.")
    sys.exit(1)

# Constants for algorithms
ALGORITHMS = [
    "none",    # Standard pickle (no compression)
    "zstd",    # Zstandard (default in zpickle)
    "brotli",  # Brotli compression
    "zlib",    # zlib/gzip compression
    "lzma",    # LZMA/xz compression
]

# Dataset definitions - each has a name, type, and source
# Dataset definitions - each has a name, type, and source
DATASETS = [
    # {
    #     "name": "Text", 
    #     "type": "text",
    #     "description": "Sample of book texts",
    #     "url": "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",
    #     "file": "shakespeare.txt"
    # },
    {
        "name": "Complex Objects",
        "type": "python",
        "description": "Complex Python object structures",
        "generated": True,
        "generator": "generate_complex_objects"
    },
    {
        "name": "NumPy Arrays",
        "type": "numpy",
        "description": "Various NumPy array types",
        "generated": True,
        "generator": "generate_numpy_arrays"
    },
    {
        "name": "JSON",
        "type": "json",
        "description": "City data in JSON format",
        "url": "https://github.com/lutangar/cities.json/raw/master/cities.json",
        "file": "cities.json"
    },
    # {
    #     "name": "Tabular Data",
    #     "type": "numpy",
    #     "description": "Structured numerical data",
    #     "generated": True,
    #     "generator": "generate_tabular_data"
    # },
]

@dataclass
class BenchmarkResult:
    """Stores benchmark results for a specific algorithm and dataset."""
    algorithm: str
    dataset: str
    data_size_mb: float
    compression_time: float
    decompression_time: float
    compressed_size_mb: float
    
    @property
    def compression_speed(self) -> float:
        """Compression speed in MB/s."""
        return self.data_size_mb / self.compression_time if self.compression_time > 0 else 0
    
    @property
    def decompression_speed(self) -> float:
        """Decompression speed in MB/s."""
        return self.data_size_mb / self.decompression_time if self.decompression_time > 0 else 0
    
    @property
    def compression_ratio(self) -> float:
        """Compression ratio (N:1)."""
        return self.data_size_mb / self.compressed_size_mb if self.compressed_size_mb > 0 else 1.0


def ensure_dataset_dir() -> Path:
    """Create and return the dataset directory path."""
    # Get the current directory
    file_path = os.path.abspath(__file__)
    file_path = os.path.dirname(file_path)

    dataset_dir = Path(os.path.join(file_path, 'datasets'))
    dataset_dir.mkdir(exist_ok=True)
    return dataset_dir


def download_file(url: str, filename: str) -> Path:
    """Download a file if it doesn't exist already."""
    dataset_dir = ensure_dataset_dir()
    filepath = dataset_dir / filename
    
    if filepath.exists():
        print(f"Using cached file: {filepath}")
        return filepath
    
    print(f"Downloading {url} to {filepath}...")
    urllib.request.urlretrieve(url, filepath)
    return filepath


def generate_repetitive_text(size_mb: float = 5.0) -> str:
    """Generate text with many repetitive patterns."""
    target_bytes = int(size_mb * 1024 * 1024)
    
    # Create some repeated patterns
    patterns = [
        "The quick brown fox jumps over the lazy dog. ",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ",
        "To be or not to be, that is the question. ",
        "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty. ",
    ]
    
    # Repeat patterns to create a large text
    result = ""
    while len(result.encode('utf-8')) < target_bytes:
        # Repeat a random pattern multiple times
        pattern = patterns[len(result) % len(patterns)]
        repeat_count = min(100, (target_bytes - len(result.encode('utf-8'))) // len(pattern.encode('utf-8')))
        result += pattern * max(1, repeat_count)
    
    return result


def generate_tabular_data(size_mb: float = 5.0) -> np.ndarray:
    """Generate tabular data with patterns."""
    if not HAS_NUMPY:
        return []
    
    # Calculate shape based on target size (each float64 is 8 bytes)
    target_bytes = int(size_mb * 1024 * 1024)
    num_elements = target_bytes // 8
    
    # Create a 2D array with some patterns
    rows = int(num_elements ** 0.5)
    cols = int(num_elements / rows)
    
    # Create structured data (not just random)
    data = np.zeros((rows, cols))
    
    # Add some patterns that are compressible
    for i in range(rows):
        # Create row patterns
        if i % 3 == 0:
            # Repeating values
            data[i, :] = np.sin(np.arange(cols) * 0.1) * 10
        elif i % 3 == 1:
            # Linear pattern
            data[i, :] = np.linspace(0, 100, cols)
        else:
            # Some randomness
            data[i, :] = np.random.normal(size=cols)
    
    return data


class Person:
    def __init__(self, name, age, friends=None):
        self.name = name
        self.age = age
        self.friends = friends or []
        self._private = "private data"
        
    def greet(self):
        return f"Hello, my name is {self.name}"
        
    def add_friend(self, friend):
        self.friends.append(friend)
        
    def __eq__(self, other):
        if not isinstance(other, Person):
            return False
        return (self.name == other.name and 
                self.age == other.age and 
                self.friends == other.friends)

def generate_complex_objects(size_mb: float = 5.0) -> List:
    """Generate complex Python object structures."""
    print(f"Generating complex Python objects (≈{size_mb} MB)...")
    
    # Create objects to reach approximately the target size
    result = []
    current_size = 0
    target_bytes = int(size_mb * 1024 * 1024)
    
    # Create various complex structures
    while current_size < target_bytes:
        # Add various types of complex objects
        
        # Nested dictionaries
        nested_dict = {}
        for i in range(50):
            nested_dict[f"key_{i}"] = {
                "name": f"value_{i}",
                "data": [j for j in range(i)],
                "nested": {
                    "a": i * 10,
                    "b": [f"item_{j}" for j in range(5)],
                    "c": {j: j**2 for j in range(10)}
                }
            }
        result.append(nested_dict)
        
        # Custom objects
        people = []
        for i in range(20):
            person = Person(f"Person_{i}", 20 + i % 40)
            # Add some friends to create a network
            for j in range(i % 5):
                friend = Person(f"Friend_{i}_{j}", 20 + j % 30)
                person.add_friend(friend)
            people.append(person)
        
        # Create circular references for some people
        for i in range(len(people) - 1):
            people[i].add_friend(people[i+1])
        # Add a circular reference
        if people:
            people[-1].add_friend(people[0])
            
        result.append(people)
        
        # Recursive structures
        recursive_list = [1, 2, 3]
        recursive_list.append(recursive_list)  # Self-reference
        result.append(recursive_list)
        
        # Mixed type collections
        for i in range(10):
            mixed = {
                "tuple": tuple(range(100)),
                "set": {f"item_{j}" for j in range(50)},
                "bytes": os.urandom(1000),
                "float": 3.14159265358979323846,
                "complex": complex(1, 2),
                "bool": i % 2 == 0,
                "none": None,
                "frozenset": frozenset(["a", "b", "c"]),
                "bytes_array": bytearray(range(255))
            }
            result.append(mixed)
        
        # Check current size
        current_size = len(pickle.dumps(result))
    
    return result

def generate_numpy_arrays(size_mb: float = 5.0) -> Dict[str, np.ndarray]:
    """Generate various NumPy array types."""
    if not HAS_NUMPY:
        return None
    
    print(f"Generating NumPy arrays (≈{size_mb} MB)...")

    # Create a collection of different array types
    arrays = {}
    
    # Basic arrays with different dtypes
    arrays["float64"] = np.linspace(0, 1, 10000, dtype=np.float64)
    arrays["float32"] = np.linspace(0, 1, 10000, dtype=np.float32)
    arrays["int64"] = np.arange(10000, dtype=np.int64)
    arrays["int32"] = np.arange(10000, dtype=np.int32)
    arrays["complex"] = np.exp(1j * np.linspace(0, 2*np.pi, 5000))
    
    # 2D arrays
    n = 1000  # Size that gives us ~8MB for float64
    arrays["matrix"] = np.zeros((n, n // 10), dtype=np.float64)
    
    # Fill with patterns
    for i in range(arrays["matrix"].shape[0]):
        if i % 3 == 0:
            # Sin wave
            arrays["matrix"][i, :] = np.sin(np.linspace(0, 10, arrays["matrix"].shape[1]))
        elif i % 3 == 1:
            # Linear gradient
            arrays["matrix"][i, :] = np.linspace(0, 1, arrays["matrix"].shape[1])
        else:
            # Constant value
            arrays["matrix"][i, :] = i % 5
    
    # 3D array (smaller due to size)
    arrays["tensor"] = np.zeros((50, 50, 50), dtype=np.float32)
    
    # Fill with a pattern
    for i in range(arrays["tensor"].shape[0]):
        arrays["tensor"][i, :, :] = i % 10
    
    # Structured array
    dt = np.dtype([('name', 'S10'), ('age', 'i4'), ('weight', 'f4')])
    arrays["structured"] = np.zeros(1000, dtype=dt)
    
    # Fill with data
    for i in range(len(arrays["structured"])):
        arrays["structured"][i] = (f"Name{i}".encode('ascii'), 20 + i % 50, 150 + i % 50)
    
    # Masked array
    data = np.arange(1000, dtype=float)
    mask = np.zeros(1000, dtype=bool)
    mask[::10] = True  # Mask every 10th element
    arrays["masked"] = np.ma.array(data, mask=mask)
    
    return arrays


def load_dataset(dataset_config: Dict[str, Any], size_mb: Optional[float] = None) -> Any:
    """Load or generate a dataset based on its configuration."""
    name = dataset_config["name"]
    data_type = dataset_config["type"]
    
    # Handle generated datasets
    if dataset_config.get("generated", False):
        if name == "Repetitive Text":
            print(f"Generating repetitive text dataset (≈{size_mb or 5.0} MB)...")
            return generate_repetitive_text(size_mb or 5.0)
        elif name == "Tabular Data" and HAS_NUMPY:
            print(f"Generating tabular data dataset (≈{size_mb or 5.0} MB)...")
            return generate_tabular_data(size_mb or 5.0)
        elif name == "Complex Objects":
            print(f"Generating complex objects dataset (≈{size_mb or 5.0} MB)...")
            return generate_complex_objects(size_mb or 5.0)
        elif name == "NumPy Arrays" and HAS_NUMPY:
            print(f"Generating NumPy arrays dataset (≈{size_mb or 5.0} MB)...")
            return generate_numpy_arrays(size_mb or 5.0)
        else:
            print(f"Unknown generated dataset: {name}")
            return None
    
    # Handle downloaded datasets
    try:
        url = dataset_config["url"]
        filename = dataset_config["file"]
        filepath = download_file(url, filename)
        
        print(f"Loading dataset {name} from {filepath}...")
        
        if data_type == "json":
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif data_type == "text":
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f"Unknown dataset type: {data_type}")
            return None
    except Exception as e:
        print(f"Error loading dataset {name}: {e}")
        return None


def benchmark_algorithm(algorithm: str, data: Any, dataset_name: str) -> BenchmarkResult:
    """Benchmark a specific algorithm with the given data."""
    # Measure original size
    pickle_data = pickle.dumps(data)
    data_size_mb = len(pickle_data) / (1024 * 1024)
    
    # Free memory
    del pickle_data
    gc.collect()
    
    # Compression benchmark
    if algorithm == "none":
        # Just use standard pickle (no compression)
        start_time = time.time()
        compressed = pickle.dumps(data)
        compression_time = time.time() - start_time
        
        start_time = time.time()
        pickle.loads(compressed)
        decompression_time = time.time() - start_time
    else:
        # Configure zpickle with the specified algorithm
        zpickle.configure(algorithm=algorithm)
        
        # Measure compression time
        start_time = time.time()
        compressed = zpickle.dumps(data)
        compression_time = time.time() - start_time
        
        # Measure decompression time
        start_time = time.time()
        zpickle.loads(compressed)
        decompression_time = time.time() - start_time
    
    # Calculate compressed size
    compressed_size_mb = len(compressed) / (1024 * 1024)
    
    # Free memory
    del compressed
    gc.collect()
    
    return BenchmarkResult(
        algorithm=algorithm,
        dataset=dataset_name,
        data_size_mb=data_size_mb,
        compression_time=compression_time,
        decompression_time=decompression_time,
        compressed_size_mb=compressed_size_mb
    )


def run_benchmarks(data_size_mb: float = 5.0, repetitions: int = 3) -> List[BenchmarkResult]:
    """Run benchmarks for all algorithms and datasets."""
    results = []
    
    for dataset_config in DATASETS:
        dataset_name = dataset_config["name"]
        
        # Skip numpy datasets if numpy is not available
        if dataset_config["type"] == "numpy" and not HAS_NUMPY:
            print(f"Skipping dataset {dataset_name} (NumPy not available)")
            continue
        
        data = load_dataset(dataset_config, data_size_mb)
        if data is None:
            print(f"Skipping dataset {dataset_name} (failed to load)")
            continue
        
        for algorithm in ALGORITHMS:
            print(f"Benchmarking {algorithm} with {dataset_name} dataset...")
            
            # Run multiple repetitions
            dataset_results = []
            for i in range(repetitions):
                print(f"  Repetition {i+1}/{repetitions}...")
                try:
                    result = benchmark_algorithm(algorithm, data, dataset_name)
                    dataset_results.append(result)
                except Exception as e:
                    print(f"  Error during benchmark: {e}")
                    continue
            
            if not dataset_results:
                print(f"  No valid results for {algorithm} on {dataset_name}")
                continue
            
            # Average the results
            avg_result = BenchmarkResult(
                algorithm=algorithm,
                dataset=dataset_name,
                data_size_mb=sum(r.data_size_mb for r in dataset_results) / len(dataset_results),
                compression_time=sum(r.compression_time for r in dataset_results) / len(dataset_results),
                decompression_time=sum(r.decompression_time for r in dataset_results) / len(dataset_results),
                compressed_size_mb=sum(r.compressed_size_mb for r in dataset_results) / len(dataset_results)
            )
            
            results.append(avg_result)
            
            # Print interim result
            ratio = avg_result.compression_ratio
            comp_speed = avg_result.compression_speed
            decomp_speed = avg_result.decompression_speed
            print(f"  Results: Ratio={ratio:.2f}:1, Compression={comp_speed:.2f} MB/s, Decompression={decomp_speed:.2f} MB/s")
        
        # Free memory after each dataset
        del data
        gc.collect()
    
    return results


def print_tables(results: List[BenchmarkResult]):
    """Print formatted tables of benchmark results."""
    # Get all dataset names
    datasets = sorted(set(r.dataset for r in results))
    
    # Create nested dictionaries for results
    data = {}
    for r in results:
        if r.algorithm not in data:
            data[r.algorithm] = {}
        data[r.algorithm][r.dataset] = {
            "compression_speed": r.compression_speed,
            "decompression_speed": r.decompression_speed,
            "compression_ratio": r.compression_ratio
        }
    
    # Print compression speed table
    print("\nCompression Speed (MB/s):")
    print("-" * 100)
    header = "Algorithm".ljust(15)
    for dataset in datasets:
        header += f"{dataset[:12].ljust(15)}"
    print(header)
    print("-" * 100)
    
    for algorithm in ALGORITHMS:
        if algorithm not in data:
            continue
        line = algorithm.ljust(15)
        for dataset in datasets:
            if dataset in data[algorithm]:
                speed = data[algorithm][dataset]["compression_speed"]
                line += f"{speed:.2f}".ljust(15)
            else:
                line += "N/A".ljust(15)
        print(line)
    
    # Print decompression speed table
    print("\nDecompression Speed (MB/s):")
    print("-" * 100)
    header = "Algorithm".ljust(15)
    for dataset in datasets:
        header += f"{dataset[:12].ljust(15)}"
    print(header)
    print("-" * 100)
    
    for algorithm in ALGORITHMS:
        if algorithm not in data:
            continue
        line = algorithm.ljust(15)
        for dataset in datasets:
            if dataset in data[algorithm]:
                speed = data[algorithm][dataset]["decompression_speed"]
                line += f"{speed:.2f}".ljust(15)
            else:
                line += "N/A".ljust(15)
        print(line)
    
    # Print compression ratio table
    print("\nCompression Ratio (N:1):")
    print("-" * 100)
    header = "Algorithm".ljust(15)
    for dataset in datasets:
        header += f"{dataset[:12].ljust(15)}"
    print(header)
    print("-" * 100)
    
    for algorithm in ALGORITHMS:
        if algorithm not in data:
            continue
        line = algorithm.ljust(15)
        for dataset in datasets:
            if dataset in data[algorithm]:
                ratio = data[algorithm][dataset]["compression_ratio"]
                line += f"{ratio:.2f}".ljust(15)
            else:
                line += "N/A".ljust(15)
        print(line)


def create_visualizations(results: List[BenchmarkResult], output_dir: str):
    """Create and save visualizations if plotting libraries are available."""
    if not HAS_PLOTTING:
        print("Skipping visualizations due to missing dependencies.")
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Convert results to DataFrame for easier plotting
    data = []
    for r in results:
        data.append({
            "Algorithm": r.algorithm,
            "Dataset": r.dataset,
            "Compression Speed (MB/s)": r.compression_speed,
            "Decompression Speed (MB/s)": r.decompression_speed,
            "Compression Ratio": r.compression_ratio
        })
    
    df = pd.DataFrame(data)
    
    # Set the plot style
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (14, 10)
    
    # Create compression speed plot
    plt.figure()
    sns.barplot(
        data=df,
        x="Algorithm",
        y="Compression Speed (MB/s)",
        hue="Dataset"
    )
    plt.title("Compression Speed by Algorithm and Dataset")
    plt.ylabel("Speed (MB/s)")
    plt.xticks(rotation=0)
    plt.legend(title="Dataset", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path / "compression_speed.png", dpi=300)
    plt.close()
    
    # Create decompression speed plot
    plt.figure()
    sns.barplot(
        data=df,
        x="Algorithm",
        y="Decompression Speed (MB/s)",
        hue="Dataset"
    )
    plt.title("Decompression Speed by Algorithm and Dataset")
    plt.ylabel("Speed (MB/s)")
    plt.xticks(rotation=0)
    plt.legend(title="Dataset", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path / "decompression_speed.png", dpi=300)
    plt.close()
    
    # Create compression ratio plot
    plt.figure()
    sns.barplot(
        data=df,
        x="Algorithm",
        y="Compression Ratio",
        hue="Dataset"
    )
    plt.title("Compression Ratio by Algorithm and Dataset")
    plt.ylabel("Ratio (N:1)")
    plt.xticks(rotation=0)
    plt.legend(title="Dataset", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path / "compression_ratio.png", dpi=300)
    plt.close()
    
    # Create a radar plot showing relative performance across all metrics
    if len(df['Dataset'].unique()) <= 5:  # Only create radar plot if we have a reasonable number of datasets
        plt.figure(figsize=(15, 15))
        
        # Normalize values for radar chart
        metrics = ['Compression Speed (MB/s)', 'Decompression Speed (MB/s)', 'Compression Ratio']
        df_radar = df.copy()
        
        for metric in metrics:
            max_val = df_radar[metric].max()
            if max_val > 0:
                df_radar[metric] = df_radar[metric] / max_val
        
        # Create a radar chart per dataset
        for i, dataset in enumerate(sorted(df_radar['Dataset'].unique())):
            plt.subplot(2, 3, i+1, polar=True)
            dataset_df = df_radar[df_radar['Dataset'] == dataset]
            
            # Set angles for each metric
            angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
            angles += angles[:1]  # Close the loop
            
            for algorithm in sorted(dataset_df['Algorithm'].unique()):
                alg_data = dataset_df[dataset_df['Algorithm'] == algorithm]
                values = [alg_data[metric].values[0] for metric in metrics]
                values += values[:1]  # Close the loop
                
                # Plot algorithm line
                plt.plot(angles, values, linewidth=2, label=algorithm)
                plt.fill(angles, values, alpha=0.1)
            
            # Set chart properties
            plt.xticks(angles[:-1], metrics)
            plt.yticks([0.25, 0.5, 0.75], ['25%', '50%', '75%'], color='gray')
            plt.ylim(0, 1)
            plt.title(f"Performance Profile: {dataset}")
            plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
        
        plt.tight_layout()
        plt.savefig(output_path / "performance_radar.png", dpi=300)
        plt.close()
    
    # Save raw data as CSV for further analysis
    df.to_csv(output_path / "benchmark_results.csv", index=False)
    
    print(f"Visualizations and data saved to {output_path}")


def main():
    """Main function to run the benchmarks."""

    # Get the current directory
    file_path = os.path.abspath(__file__)
    file_path = os.path.dirname(file_path)

    print(f"Running benchmarks from: {file_path}")
    parser = argparse.ArgumentParser(description="Benchmark zpickle compression performance")
    parser.add_argument("--size", type=float, default=10.0, help="Approximate size in MB for each test dataset")
    parser.add_argument("--repetitions", type=int, default=3, help="Number of repetitions for more reliable results")
    parser.add_argument("--output", type=str, default=os.path.join(file_path, "results"), help="Output directory for visualizations")
    
    args = parser.parse_args()
    
    print("Running zpickle benchmarks with real-world datasets")
    print(f"- Generated data size: ~{args.size} MB per category")
    print(f"- Repetitions: {args.repetitions}")
    print(f"- Testing algorithms: {', '.join(ALGORITHMS)}")
    print(f"- Testing datasets: {', '.join(d['name'] for d in DATASETS)}")
    
    # Run the benchmarks
    results = run_benchmarks(data_size_mb=args.size, repetitions=args.repetitions)
    
    # Print tables
    print_tables(results)
    
    # Create visualizations
    create_visualizations(results, args.output)
    
    print("\nBenchmarks complete!")


if __name__ == "__main__":
    main()