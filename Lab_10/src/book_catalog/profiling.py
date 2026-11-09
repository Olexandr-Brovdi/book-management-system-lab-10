"""Separate instrumentation from timing; tracemalloc observes the parent only."""

import cProfile
import io
from pathlib import Path
import pstats
import tracemalloc
from typing import Protocol, TypedDict, cast


class _StatsData(Protocol):
    """Runtime pstats data attributes omitted by the installed stdlib stubs."""

    stats: dict[tuple[str, int, str], tuple[int, int, float, float, object]]
    total_tt: float


class ProfileRow(TypedDict):
    function: str
    filename: str
    line: int
    ncalls: int
    primitive_calls: int
    tottime: float
    cumtime: float


def profile_call(function, output: Path, *args) -> dict:
    profiler = cProfile.Profile()
    result = profiler.runcall(function, *args)
    profiler.dump_stats(str(output.with_suffix(".prof")))
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(25)
    data = cast(_StatsData, stats)
    output.with_suffix(".txt").write_text(stream.getvalue(), encoding="utf-8")
    rows: list[ProfileRow] = []
    for (filename, line, name), (
        primitive,
        calls,
        own,
        cumulative,
        callers,
    ) in data.stats.items():
        rows.append(
            ProfileRow(
                function=name,
                filename=filename,
                line=line,
                ncalls=calls,
                primitive_calls=primitive,
                tottime=own,
                cumtime=cumulative,
            )
        )
    rows.sort(key=lambda row: row["cumtime"], reverse=True)
    return {
        "total_seconds": data.total_tt,
        "functions": rows,
        "result_type": type(result).__name__,
    }


def memory_call(function, *args) -> dict:
    tracemalloc.start()
    try:
        result = function(*args)
        current, peak = tracemalloc.get_traced_memory()
        snapshot = tracemalloc.take_snapshot()
        top = [str(row) for row in snapshot.statistics("lineno")[:10]]
        return {
            "current_bytes": current,
            "peak_bytes": peak,
            "top_allocations": top,
            "result_type": type(result).__name__,
        }
    finally:
        tracemalloc.stop()
