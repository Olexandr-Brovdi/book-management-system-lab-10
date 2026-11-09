import json
import sys

import pytest

from book_catalog.config import load_config
from book_catalog.main import main, run

pytestmark = pytest.mark.integration


def test_real_yaml_paths_and_application_pipeline(config_path, books):
    config = load_config(config_path)
    assert config.input.parent == config_path.parent
    assert config.policy.min_year == 1800
    assert config.policy.max_year == 2026
    assert run(config_path, "Франко") == 2
    assert json.loads(config.output.read_text(encoding="utf-8")) == [
        b.to_dict() for b in books[1:]
    ]


def test_cli_success(config_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["book-catalog", "--config", str(config_path), "--author", "Франко"],
    )
    main()
    assert capsys.readouterr().out == "Exported books: 2\n"


def test_cli_failure_exits_with_code_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["book-catalog", "--config", str(tmp_path / "missing.yaml")]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "Catalog error" in capsys.readouterr().err
