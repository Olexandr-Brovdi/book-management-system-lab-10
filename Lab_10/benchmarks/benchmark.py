"""Real repeated experiments. Run from project root; spawning requires main guard."""

from dataclasses import asdict
from functools import partial
from hashlib import sha256
from pathlib import Path
from statistics import mean, median
from time import perf_counter
import argparse
import csv
import json
import os
import platform
import sys
import tempfile
import timeit

from book_catalog.analytics import (
    CachedAuthorAnalytics,
    analyze_catalog,
    generate_books,
    statistics_numpy,
    statistics_python,
)
from book_catalog.catalog import Catalog
from book_catalog.models import Book
from book_catalog.parallel import (
    load_catalog_files,
    race_condition_demo,
    statistics_processes,
    statistics_raw_process,
    statistics_raw_threads,
    statistics_threads,
)
from book_catalog.profiling import memory_call, profile_call

ROOT = Path(__file__).resolve().parents[1]


def equivalent(actual, expected):
    import math

    assert actual.count == expected.count
    for field in ["average", "minimum", "maximum", "std"]:
        assert math.isclose(
            getattr(actual, field),
            getattr(expected, field),
            rel_tol=1e-10,
            abs_tol=1e-8,
        ), field


def measure(function, repeats):
    samples = []
    for _ in range(repeats):
        start = perf_counter()
        result = function()
        samples.append(perf_counter() - start)
    return result, samples


def run(sizes=(100_000, 200_000, 300_000), workers=(1, 2, 4, 8), repeats=5):
    import numpy as np

    if repeats < 3 or len(sizes) < 3 or len(workers) < 3:
        raise ValueError(
            "Use >=3 dataset sizes, >=3 worker configurations and >=3 repeats"
        )
    output = ROOT / "benchmarks/results"
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(
        python=sys.version,
        platform=platform.platform(),
        processor=platform.processor(),
        cpu_count=os.cpu_count(),
        numpy=np.__version__,
        sizes=sizes,
        workers=workers,
        repeats=repeats,
        timer="perf_counter",
        process_start="spawn",
        process_timing="cold pool per repeat: startup, partition, serialization and shutdown included",
        memory_scope="tracemalloc incremental Python allocations in parent only; excludes input created before tracking and child-process RSS; not total physical memory",
    )
    (output / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    records, datasets, caches, io_records = [], [], [], []
    for size in sizes:
        print(f"Dataset {size:,} books", flush=True)
        books = generate_books(size)
        catalog = Catalog(books)
        pages = [book.pages for book in books]
        expected = statistics_python(pages)
        datasets.append(
            dict(
                size=size,
                seed=42,
                authors=100,
                years=[1800, 2026],
                pages=[40, 1200],
                sha256_pages=sha256(",".join(map(str, pages)).encode()).hexdigest(),
                expected=asdict(expected),
            )
        )
        profile = profile_call(analyze_catalog, output / f"catalog-{size}", catalog)
        before = profile_call(statistics_python, output / f"baseline-{size}", pages)
        after = profile_call(statistics_numpy, output / f"numpy-{size}", pages)
        (output / f"profile-{size}.json").write_text(
            json.dumps(
                dict(catalog=profile, baseline=before, optimized=after), indent=2
            ),
            encoding="utf-8",
        )
        array = np.asarray(pages, dtype=np.float64)
        datasets[-1].update(
            list_container_bytes=sys.getsizeof(pages),
            unique_integer_bytes=sum(
                sys.getsizeof(value) for value in {id(x): x for x in pages}.values()
            ),
            numpy_payload_bytes=array.nbytes,
        )
        methods = [
            ("Sequential", 1, partial(statistics_python, pages)),
            ("NumPy_list", 1, partial(statistics_numpy, pages)),
            ("NumPy_array", 1, partial(statistics_numpy, array)),
        ]
        for count in workers:
            methods.extend(
                [
                    ("Threads", count, partial(statistics_threads, pages, count)),
                    ("Processes", count, partial(statistics_processes, pages, count)),
                ]
            )
        baseline_time = None
        for name, count, function in methods:
            # Import/warm-up effects excluded. Every timed pool still starts cold.
            if name in ("Sequential", "NumPy_list", "NumPy_array"):
                equivalent(function(), expected)
            result, samples = measure(function, repeats)
            equivalent(result, expected)
            memory = memory_call(function)
            if name == "Sequential":
                baseline_time = mean(samples)
            record = dict(
                dataset=size,
                method=name,
                workers=count,
                samples=samples,
                mean_seconds=mean(samples),
                median_seconds=median(samples),
                peak_parent_mib=memory["peak_bytes"] / 1024**2,
                current_parent_mib=memory["current_bytes"] / 1024**2,
                speedup=baseline_time / mean(samples),
                correctness="PASS",
                result=asdict(result),
                memory_top=memory["top_allocations"],
            )
            records.append(record)
            print(
                f"  {name:13} workers={count} mean={record['mean_seconds']:.6f}s speedup={record['speedup']:.2f}x",
                flush=True,
            )

        cache = CachedAuthorAnalytics(books)
        cold_samples = []
        for _ in range(repeats):
            cache.replace_books(books)
            start = perf_counter()
            cold_result = cache.statistics("Автор 042")
            cold_samples.append(perf_counter() - start)
        warm_samples = [
            value / 1000
            for value in timeit.repeat(
                lambda: cache.statistics("Автор 042"), number=1000, repeat=repeats
            )
        ]
        equivalent(cache.statistics("Автор 042"), cold_result)
        info = cache.cache_info()._asdict()
        cache.add_book(Book(f"new-{size}", "Нова книга", "Автор 042", 2026, 1200))
        cleared = cache.cache_info()._asdict()
        changed = cache.statistics("Автор 042")
        assert changed.count == cold_result.count + 1 and cleared["currsize"] == 0
        caches.append(
            dict(
                dataset=size,
                cold_seconds=cold_samples,
                warm_seconds=warm_samples,
                cold_mean=mean(cold_samples),
                warm_mean=mean(warm_samples),
                speedup=mean(cold_samples) / mean(warm_samples),
                before=asdict(cold_result),
                after=asdict(changed),
                cache_info=info,
                after_invalidation=cleared,
                version=cache.version,
                timer="timeit warm calls number=1000; perf_counter cold calculation only, cache invalidation excluded",
            )
        )
        with tempfile.TemporaryDirectory(prefix="lab09-catalog-") as temporary:
            paths = []
            for index in range(8):
                path = Path(temporary) / f"catalog-{index}.json"
                path.write_text(
                    json.dumps(
                        [book.to_dict() for book in books[index::8]], ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                paths.append(path)
            reference = load_catalog_files(paths, 1)
            sequential = None
            for count in workers:
                result, samples = measure(
                    partial(load_catalog_files, paths, count), repeats
                )
                assert result == reference
                if count == 1:
                    sequential = mean(samples)
                io_records.append(
                    dict(
                        dataset=size,
                        workers=count,
                        samples=samples,
                        mean_seconds=mean(samples),
                        speedup=sequential / mean(samples),
                        files=8,
                        total_bytes=sum(p.stat().st_size for p in paths),
                        correctness="PASS",
                    )
                )
        del books, catalog, pages, array, methods

    demo_values = [80, 192, 160]
    raw_threads, processed = statistics_raw_threads(demo_values, 4)
    equivalent(raw_threads, statistics_python(demo_values))
    raw_process = statistics_raw_process(demo_values)
    equivalent(raw_process, statistics_python(demo_values))
    demos = dict(
        raw_threads=asdict(raw_threads),
        processed=processed,
        raw_process=asdict(raw_process),
        race=race_condition_demo(4),
    )
    report = dict(
        environment=environment,
        datasets=datasets,
        benchmarks=records,
        caching=caches,
        io=io_records,
        demos=demos,
    )
    (output / "experiments.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "benchmark_results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        fields = [
            "dataset",
            "method",
            "workers",
            *[f"run_{i + 1}_seconds" for i in range(repeats)],
            "mean_seconds",
            "median_seconds",
            "peak_parent_mib",
            "speedup",
            "correctness",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            flat = {key: row[key] for key in fields if key in row}
            flat.update(
                {
                    f"run_{i + 1}_seconds": sample
                    for i, sample in enumerate(row["samples"])
                }
            )
            writer.writerow(flat)
    with (output / "io_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "dataset",
                "workers",
                "mean_seconds",
                "speedup",
                "files",
                "total_bytes",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {key: row[key] for key in writer.fieldnames} for row in io_records
        )
    print("Experiments complete; every result checked against baseline", flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Lab_09 variant 2 measured book analytics"
    )
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    run(repeats=args.repeats)
