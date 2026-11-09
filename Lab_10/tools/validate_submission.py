"""Validate Lab_10 code, reports, packages and actual Docker/CI evidence."""

from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate():
    reports = (
        [ROOT / "report/report.docx"]
        if ROOT.name == "Lab_10"
        else [
            ROOT / "docs/Lab_10_Report_Variant_2.docx",
            ROOT / "Lab_10/report/report.docx",
        ]
    )
    for report in reports:
        with ZipFile(report) as archive:
            raw = archive.read("word/document.xml")
        assert b"Aspose" not in raw
        tree = ET.fromstring(raw)
        text = " ".join(
            t.text or ""
            for t in tree.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            )
        ).casefold()
        for phrase in [
            "лабораторної роботи №10",
            "варіант №2",
            "система обліку книг",
            "бровді олександр",
            "феп-32",
            "09.11.2026",
            "222 passed",
            "70.",
            "success",
            "workflow",
            "docker",
            "wheel",
            "sdist",
            "mypy",
            "github actions",
        ]:
            assert phrase in text, phrase
        assert set(re.findall(r"варіант\s*№?\s*(\d+)", text)) == {"2"}
    assert {
        p.resolve()
        for p in ROOT.rglob("*.docx")
        if not {".venv", ".wheel-check", "build"}.intersection(p.parts)
    } == {p.resolve() for p in reports}
    if len(reports) == 2:
        assert reports[0].read_bytes() == reports[1].read_bytes()
        for folder in [
            "src",
            "tests",
            "migrations",
            "benchmarks",
            "data",
            "tools",
            "docs",
            "dist",
            ".github",
        ]:
            for path in (ROOT / folder).rglob("*"):
                if (
                    path.is_file()
                    and path.suffix != ".docx"
                    and "__pycache__" not in path.parts
                    and not any(p.endswith(".egg-info") for p in path.parts)
                ):
                    assert (
                        path.read_bytes()
                        == (ROOT / "Lab_10" / path.relative_to(ROOT)).read_bytes()
                    ), path
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["name"] == "book-catalog" and project["version"] == "1.0.0"
    assert project["authors"][0]["name"] == "Бровді Олександр"
    summary = load("docs/results/summary.json")
    cases = ET.parse(ROOT / "docs/results/tests.xml").findall(".//testcase")
    assert summary["tests"] == len(cases) == 222 and summary["failed"] == 0
    assert not any(
        c.find("failure") is not None or c.find("error") is not None for c in cases
    )
    assert all(value == "PASS" for value in summary["quality"].values())
    assert summary["coverage"]["percent_covered"] >= 85
    assert summary["ci"] == summary["docker"] == "PASS"
    assert summary["publication"] == "PUBLISHED"
    ci = load("docs/results/ci.json")
    assert ci["conclusion"] == "success" and ci["status"] == "completed"
    assert len(ci["jobs"]) == 3
    assert all(job["conclusion"] == "success" for job in ci["jobs"])
    docker = load("docs/results/docker.json")
    assert docker["status"] == docker["volume_restart_persistence"] == "PASS"
    assert docker["container_state"] == "running"
    assert docker["docker_health"] == "healthy"
    assert docker["configured_user"] == "appuser"
    assert docker["health"]["environment"] == "production"
    assert docker["created_book"]["title"] == "Захар Беркут"
    assert load("docs/results/wheel.json")["status"] == "PASS"
    assert ".wheel-check" in load("docs/results/wheel.json")["module"]
    assert len(load("docs/control_answers.json")) == 70
    for artifact in summary["artifacts"]:
        path = ROOT / "dist" / artifact["name"]
        assert path.stat().st_size == artifact["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    with ZipFile(ROOT / "dist/book_catalog-1.0.0-py3-none-any.whl") as wheel:
        names = wheel.namelist()
        assert any("migration_assets/versions/0002" in name for name in names)
        assert any("swagger-ui-bundle.js" in name for name in names)
        assert not any(
            "__pycache__" in name or name.endswith(".pyc") or name.endswith("/.env")
            for name in names
        )
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for command in [
        "ruff check .",
        "ruff format --check .",
        "mypy src",
        "pytest -v",
        "python -m build",
        "docker build",
        "docker_smoke.py",
        "wheel_smoke.py",
    ]:
        assert command in workflow, command
    assert len(re.findall(r"uses: actions/[\w-]+@[0-9a-f]{40}", workflow)) >= 5
    ignore = (ROOT / ".gitignore").read_text()
    assert ".env" in ignore and "!.env.example" in ignore
    for path in (ROOT / "src").rglob("*.py"):
        assert not re.search(
            r"gh[pousr]_[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----",
            path.read_text(encoding="utf-8"),
        ), path
    print(
        "PASS: local Lab_10 variant2; identical reports/source;222 tests; quality/build/clean wheel;70 answers; Docker runtime and green CI verified."
    )


if __name__ == "__main__":
    validate()
