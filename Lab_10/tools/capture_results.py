"""Capture actual local quality checks; do not invent unavailable Docker/CI evidence."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results"


def run(name, arguments):
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    (RESULTS / f"{name}.txt").write_text(
        "$ " + " ".join(arguments) + "\n" + result.stdout + result.stderr,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"{name} failed; see docs/results/{name}.txt")


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    for name, args in [
        ("lint", ["-m", "ruff", "check", "."]),
        ("format", ["-m", "ruff", "format", "--check", "."]),
        ("mypy", ["-m", "mypy", "src"]),
        ("tests", ["-m", "pytest", "-v", "--junitxml=docs/results/tests.xml"]),
        ("build", ["-m", "build"]),
    ]:
        run(name, [sys.executable, *args])
    run(
        "twine",
        [
            sys.executable,
            "-m",
            "twine",
            "check",
            *map(str, sorted((ROOT / "dist").glob("*"))),
        ],
    )
    for ext in ["json", "xml"]:
        shutil.copy2(ROOT / f"coverage.{ext}", RESULTS / f"coverage.{ext}")
    shutil.copytree(ROOT / "htmlcov", ROOT / "docs/coverage/html", dirs_exist_ok=True)
    cases = ET.parse(RESULTS / "tests.xml").findall(".//testcase")
    artifacts = [
        dict(
            name=p.name,
            bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in sorted((ROOT / "dist").glob("*"))
    ]
    summary = dict(
        tests=len(cases),
        failed=sum(
            c.find("failure") is not None or c.find("error") is not None for c in cases
        ),
        coverage=json.loads((RESULTS / "coverage.json").read_text())["totals"],
        quality={
            "lint": "PASS",
            "format": "PASS",
            "mypy": "PASS",
            "build": "PASS",
            "twine": "PASS",
        },
        artifacts=artifacts,
        docker="NOT_RUN: Engine unavailable; Docker Desktop access denied",
        ci="NOT_RUN: push rejected without OAuth workflow scope; user deferred authorization",
        publication="DEFERRED_BY_USER",
    )
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
