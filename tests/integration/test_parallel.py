from dataclasses import asdict
import json
import pytest
from book_catalog.analytics import generate_books, statistics_python
from book_catalog.parallel import (
    load_catalog_files,
    partition,
    race_condition_demo,
    statistics_processes,
    statistics_raw_process,
    statistics_raw_threads,
    statistics_threads,
)
from book_catalog.profiling import memory_call, profile_call


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_real_thread_and_spawn_process_pools_preserve_results(workers):
    values = [book.pages for book in generate_books(1234)]
    expected = asdict(statistics_python(values))
    for function in [statistics_threads, statistics_processes]:
        assert asdict(function(values, workers)) == pytest.approx(expected, abs=1e-8)


def test_empty_singleton_and_raw_workers():
    for values in [[], [80]]:
        assert statistics_threads(values) == statistics_python(values)
        assert statistics_processes(values) == statistics_python(values)
    result, count = statistics_raw_threads([80, 192, 160], 4)
    assert count == 3 and asdict(result) == pytest.approx(
        asdict(statistics_python([80, 192, 160])), abs=1e-8
    )
    assert asdict(statistics_raw_process([80, 192, 160])) == pytest.approx(
        asdict(result), abs=1e-8
    )


@pytest.mark.parametrize("workers", [0, -1, 33, True, 1.5])
def test_invalid_workers(workers):
    with pytest.raises(ValueError):
        partition([1, 2], workers)


def test_controlled_race_and_lock():
    assert race_condition_demo(4) == {"expected": 4, "unsafe": 1, "locked": 4}


def test_actual_json_file_loading(tmp_path):
    paths = []
    for index in range(4):
        path = tmp_path / f"books-{index}.json"
        path.write_text(
            json.dumps([b.to_dict() for b in generate_books(index)]), encoding="utf-8"
        )
        paths.append(path)
    sequential = load_catalog_files(paths, 1)
    assert load_catalog_files(paths, 4) == sequential
    paths[0].write_text("invalid", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_catalog_files(paths, 2)


def test_profile_and_memory_evidence(tmp_path):
    profile = profile_call(statistics_python, tmp_path / "test", [80, 192, 160])
    assert any(
        row["function"] == "statistics_python" and row["ncalls"] == 1
        for row in profile["functions"]
    )
    assert (tmp_path / "test.prof").stat().st_size > 0 and (
        tmp_path / "test.txt"
    ).is_file()
    memory = memory_call(statistics_python, [80, 192, 160])
    assert memory["peak_bytes"] >= memory["current_bytes"] >= 0
