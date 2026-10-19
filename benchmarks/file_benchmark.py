#!/usr/bin/env python
"""
File benchmark for zpickle: streaming dump()/load() against a real disk.

Each dataset is written with dump() (fsync'd) and read back with load(). With
--drop-caches (Linux, needs passwordless sudo or root) the page cache is
dropped before every load, so reads come from the device rather than RAM.
Speeds are MB/s of *uncompressed pickle*, so codecs and plain pickle compare
end-to-end. The README charts come from this script.

Usage:
    python -m benchmarks.file_benchmark run --dir /mnt/bench --out results.jsonl
    python -m benchmarks.file_benchmark plot results.jsonl --out-dir benchmarks/results
"""

import argparse
import importlib.util
import json
import os
import pickle
import platform
import subprocess
import sys
import time
from pathlib import Path

ALGORITHMS = [
    "zstd",
    "brotli",
    "zlib",
    "lzma",
    "bzip2",
    "lz4",
    "snappy",
    "gzip",
    "deflate",
]

DATASETS = {
    "complex-objects": "Complex objects",
    "cities-json": "JSON",
    "numpy-arrays": "NumPy arrays",
}

BENCHMARKS_DIR = Path(__file__).resolve().parent


def load_dataset(name: str, size_mb: float, cache_dir: Path | None):
    """Build (or load from cache) one dataset."""
    path = cache_dir / f"{name}-{size_mb:g}MB.pkl" if cache_dir else None
    if path and path.exists():
        _benchmark_module()  # so pickle can resolve its Person class
        with open(path, "rb") as f:
            return pickle.load(f)

    if name == "complex-objects":
        bench = _benchmark_module()
        # generate_complex_objects re-pickles everything per iteration
        # (quadratic), so build the target size from 1 MB batches
        data = [
            item
            for _ in range(max(1, round(size_mb)))
            for item in bench.generate_complex_objects(1.0)
        ]
    elif name == "cities-json":
        with open(BENCHMARKS_DIR / "datasets" / "cities.json") as f:
            data = json.load(f)
    elif name == "numpy-arrays":
        import numpy as np

        rng = np.random.default_rng(0)
        n = int(size_mb * 1024 * 1024 / 4)
        # Sensor-like float32 series: smooth signal + quantized noise
        signal = np.cumsum(rng.normal(0, 0.01, n)).astype(np.float32)
        data = {
            "signal": np.round(signal, 2),
            "ids": np.arange(n // 4, dtype=np.int64),
        }
    else:
        raise ValueError(f"Unknown dataset: {name}")

    if path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=4)
    return data


def _benchmark_module():
    """Import benchmarks/benchmark.py under a name pickle can resolve."""
    if "zp_bench" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "zp_bench", BENCHMARKS_DIR / "benchmark.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["zp_bench"] = module
        spec.loader.exec_module(module)
    return sys.modules["zp_bench"]


def drop_caches():
    os.sync()
    if os.geteuid() == 0:
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3\n")
    else:
        subprocess.run(
            ["sudo", "-n", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
            check=True,
        )


def best_time(fn, reps, setup=None):
    times = []
    for _ in range(reps):
        if setup:
            setup()
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


def run(args):
    import compress_utils
    import zpickle

    def dump_file(obj, path, alg):
        with open(path, "wb") as f:
            if alg == "pickle":
                pickle.dump(obj, f)
            else:
                zpickle.dump(obj, f, algorithm=alg)
            f.flush()
            os.fsync(f.fileno())

    def load_file(path, alg):
        with open(path, "rb") as f:
            return pickle.load(f) if alg == "pickle" else zpickle.load(f)

    bench_dir = Path(args.dir)
    bench_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "machine": args.machine or platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "compress_utils": compress_utils.version(),
        "zpickle": zpickle.__version__,
        "drop_caches": args.drop_caches,
        "reps": args.reps,
    }
    print(json.dumps(meta))
    setup = drop_caches if args.drop_caches else None
    datasets = args.datasets or list(DATASETS)
    algorithms = ["pickle"] + (args.algorithms or ALGORITHMS)

    with open(args.out, "a") as out:
        for name in datasets:
            obj = load_dataset(
                name, args.size, Path(args.cache) if args.cache else None
            )
            raw_mb = len(pickle.dumps(obj)) / 1e6
            for alg in algorithms:
                path = bench_dir / f"bench-{name}-{alg}.bin"
                dump_s = best_time(lambda: dump_file(obj, path, alg), args.reps)
                ratio = raw_mb * 1e6 / path.stat().st_size
                load_s = best_time(lambda: load_file(path, alg), args.reps, setup)
                path.unlink()
                row = dict(
                    meta,
                    dataset=name,
                    algorithm=alg,
                    raw_mb=raw_mb,
                    ratio=ratio,
                    dump_mb_s=raw_mb / dump_s,
                    load_mb_s=raw_mb / load_s,
                )
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(
                    f"{name:16} {alg:8} {raw_mb:6.1f} MB  ratio {ratio:5.2f}  "
                    f"dump {row['dump_mb_s']:7.0f} MB/s  load {row['load_mb_s']:7.0f} MB/s",
                    flush=True,
                )


# Chart colors and ink (light, dark): one accent hue for the codecs, a neutral
# for the uncompressed pickle baseline; text uses ink tokens, never series color.
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "codec": "#2a78d6",
        "baseline": "#93928b",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
    },
    "dark": {
        "surface": "#1a1a19",
        "codec": "#3987e5",
        "baseline": "#6b6a65",
        "ink": "#f0efec",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
    },
}


def plot(args):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle

    with open(args.results) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = args.datasets or list(DATASETS)
    datasets = [d for d in wanted if any(r["dataset"] == d for r in rows)]
    rows = [r for r in rows if r["dataset"] in datasets]

    charts = [
        ("load_speed", "load_mb_s", "{:,.0f}", "Load speed from disk (MB/s)"),
        ("compression_ratio", "ratio", "{:.1f}×", "Compression ratio vs. pickle"),
    ]
    plt.rcParams["font.family"] = ["Helvetica Neue", "Arial", "DejaVu Sans"]
    dpi = 200

    for stem, key, fmt, title in charts:
        for mode, t in THEMES.items():
            fig, axes = plt.subplots(
                1,
                len(datasets),
                figsize=(4 * len(datasets) + 0.5, 4.4),
                dpi=dpi,
                facecolor=t["surface"],
                squeeze=False,
            )
            fig.suptitle(
                title, x=0.012, y=0.975, ha="left", fontsize=15, color=t["ink"]
            )
            for ax, name in zip(axes[0], datasets):
                data = sorted(
                    (r for r in rows if r["dataset"] == name),
                    key=lambda r: r[key],
                )
                labels = [r["algorithm"] for r in data]
                values = [r[key] for r in data]
                raw_mb = data[0]["raw_mb"]

                ax.set_facecolor(t["surface"])
                xmax = max(values) * 1.22
                ax.set_xlim(0, xmax)
                ax.set_ylim(-0.6, len(values) - 0.4)
                fig.canvas.draw()
                bbox = ax.get_window_extent()
                px_x = bbox.width / xmax  # pixels per x unit
                px_y = bbox.height / len(values)  # pixels per y unit
                height = min(0.62, 24 * dpi / 100 / px_y)  # cap bar thickness
                radius_px = 4 * dpi / 100

                for i, (alg, value) in enumerate(zip(labels, values)):
                    color = t["baseline"] if alg == "pickle" else t["codec"]
                    radius = min(radius_px / px_x, value / 2)
                    # Rounded data-end, square at the baseline
                    ax.add_patch(
                        FancyBboxPatch(
                            (0, i - height / 2),
                            value,
                            height,
                            boxstyle=f"round,pad=0,rounding_size={radius}",
                            mutation_aspect=px_x / px_y,
                            facecolor=color,
                            edgecolor="none",
                        )
                    )
                    ax.add_patch(
                        Rectangle(
                            (0, i - height / 2),
                            max(value - radius, 0),
                            height,
                            facecolor=color,
                            edgecolor="none",
                        )
                    )
                    ax.text(
                        value + xmax * 0.015,
                        i,
                        fmt.format(value),
                        va="center",
                        fontsize=10,
                        color=t["ink2"],
                    )

                ax.set_yticks(range(len(labels)))
                ax.set_yticklabels(
                    labels,
                    fontsize=10.5,
                    color=t["ink"],
                )
                ax.tick_params(axis="y", length=0, pad=6)
                ax.tick_params(axis="x", colors=t["muted"], labelsize=9, length=0)
                ax.xaxis.set_major_locator(plt.MaxNLocator(4))
                ax.grid(axis="x", color=t["grid"], linewidth=0.8)
                ax.set_axisbelow(True)
                for side in ("top", "right", "bottom"):
                    ax.spines[side].set_visible(False)
                ax.spines["left"].set_color(t["axis"])
                ax.set_title(
                    f"{DATASETS[name]} ({raw_mb:.0f} MB)",
                    loc="left",
                    fontsize=12,
                    color=t["ink"],
                    pad=10,
                )

            meta = rows[0]
            fig.text(
                0.012,
                0.015,
                f"{args.machine_note or meta['machine']} · Python {meta['python']} · "
                f"compress-utils {meta['compress_utils']} · level 3 · "
                + (
                    "page cache dropped before each load · "
                    if meta["drop_caches"]
                    else ""
                )
                + f"best of {meta['reps']}",
                fontsize=9,
                color=t["muted"],
            )
            fig.tight_layout(rect=(0, 0.05, 1, 0.97), w_pad=3)
            suffix = "" if mode == "light" else "_dark"
            fig.savefig(out_dir / f"{stem}{suffix}.png", facecolor=t["surface"])
            plt.close(fig)
            print(f"Wrote {out_dir / f'{stem}{suffix}.png'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the benchmark")
    p_run.add_argument("--dir", required=True, help="directory for benchmark files")
    p_run.add_argument("--out", required=True, help="append JSON lines here")
    p_run.add_argument("--size", type=float, default=50.0, help="target dataset MB")
    p_run.add_argument("--reps", type=int, default=5)
    p_run.add_argument("--datasets", nargs="+", choices=list(DATASETS))
    p_run.add_argument("--algorithms", nargs="+", choices=ALGORITHMS)
    p_run.add_argument("--cache", help="cache generated datasets here")
    p_run.add_argument("--machine", help="machine label stored with results")
    p_run.add_argument(
        "--drop-caches", action="store_true", help="drop page cache before loads"
    )

    p_plot = sub.add_parser("plot", help="draw README charts from results")
    p_plot.add_argument("results")
    p_plot.add_argument("--out-dir", default=str(BENCHMARKS_DIR / "results"))
    p_plot.add_argument("--machine-note", help="override the machine footnote")
    p_plot.add_argument(
        "--datasets", nargs="+", choices=list(DATASETS), help="datasets to chart"
    )

    args = parser.parse_args()
    if args.command == "run":
        run(args)
    else:
        plot(args)


if __name__ == "__main__":
    main()
