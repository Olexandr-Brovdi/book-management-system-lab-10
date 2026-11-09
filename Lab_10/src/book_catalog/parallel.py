"""The same page statistics with explicit threads and spawn-safe processes."""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from math import sqrt
import multiprocessing as mp
from pathlib import Path
from threading import Barrier, Lock, Thread

from book_catalog.analytics import PageStatistics


def partial_statistics(values):
    count = len(values)
    if not count:
        return 0, 0, 0, 0, 0
    total = squared = 0
    minimum = maximum = values[0]
    for value in values:
        total += value
        squared += value * value
        minimum = min(minimum, value)
        maximum = max(maximum, value)
    return count, total, squared, minimum, maximum


def merge_statistics(parts) -> PageStatistics:
    parts = [part for part in parts if part[0]]
    count = sum(part[0] for part in parts)
    if not count:
        return PageStatistics(0, 0.0, 0.0, 0.0, 0.0)
    average = sum(part[1] for part in parts) / count
    variance = max(0.0, sum(part[2] for part in parts) / count - average * average)
    return PageStatistics(
        count,
        average,
        float(min(p[3] for p in parts)),
        float(max(p[4] for p in parts)),
        sqrt(variance),
    )


def partition(values, workers: int):
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError("workers must be an integer in 1..32")
    step = max(1, (len(values) + workers - 1) // workers)
    return [values[i : i + step] for i in range(0, len(values), step)]


def statistics_threads(values, workers: int = 4) -> PageStatistics:
    chunks = partition(values, workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return merge_statistics(executor.map(partial_statistics, chunks))


def statistics_processes(values, workers: int = 4) -> PageStatistics:
    chunks = partition(values, workers)
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=mp.get_context("spawn")
    ) as executor:
        return merge_statistics(executor.map(partial_statistics, chunks, chunksize=1))


def statistics_raw_threads(values, workers: int = 4) -> tuple[PageStatistics, int]:
    chunks = partition(values, workers)
    results = [None] * len(chunks)
    processed = 0
    lock = Lock()

    def worker(index, chunk):
        nonlocal processed
        result = partial_statistics(chunk)
        with lock:
            results[index] = result
            processed += len(chunk)

    threads = [Thread(target=worker, args=(i, chunk)) for i, chunk in enumerate(chunks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return merge_statistics(results), processed


def _process_worker(values, queue):
    queue.put(partial_statistics(values))


def statistics_raw_process(values) -> PageStatistics:
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_process_worker, args=(values, queue))
    process.start()
    try:
        result = queue.get(timeout=30)
        process.join(timeout=30)
        if process.exitcode != 0:
            raise RuntimeError("Worker did not complete successfully")
        return merge_statistics([result])
    finally:
        if process.is_alive():
            process.terminate()
            process.join()
        queue.close()
        queue.join_thread()


def load_catalog_files(paths: list[Path], workers: int = 1) -> list[list[dict]]:
    """Actual JSON disk reads; no synthetic sleep or latency is added."""
    import json

    def load(path):
        return json.loads(path.read_text(encoding="utf-8"))

    partition([], workers)  # Validate the public worker argument.
    if workers == 1:
        return [load(path) for path in paths]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(load, paths))


def race_condition_demo(workers: int = 4) -> dict[str, int]:
    partition([], workers)
    counter = 0
    barrier = Barrier(workers)

    def unsafe():
        nonlocal counter
        snapshot = counter
        barrier.wait()  # Force all reads before writes to reproduce lost updates.
        counter = snapshot + 1

    threads = [Thread(target=unsafe) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    unsafe_result = counter
    counter = 0
    lock = Lock()

    def safe():
        nonlocal counter
        with lock:
            counter += 1

    threads = [Thread(target=safe) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return {"expected": workers, "unsafe": unsafe_result, "locked": counter}
