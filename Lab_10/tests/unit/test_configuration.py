import pytest
import yaml

from book_catalog.config import get_environment, load_config
from book_catalog.exceptions import ConfigurationError

pytestmark = pytest.mark.unit


def test_default_environment(monkeypatch):
    monkeypatch.delenv("BOOK_ENV", raising=False)
    assert get_environment() == "development"


def test_environment_override(monkeypatch):
    monkeypatch.setenv("BOOK_ENV", "testing")
    assert get_environment() == "testing"


def test_max_year_override(config_path, monkeypatch):
    monkeypatch.setenv("BOOK_MAX_YEAR", "2000")
    assert load_config(config_path).policy.max_year == 2000


@pytest.mark.parametrize("value", ["not-a-number", "1799"])
def test_invalid_env_override_is_configuration_error(config_path, monkeypatch, value):
    monkeypatch.setenv("BOOK_MAX_YEAR", value)
    with pytest.raises(ConfigurationError) as error:
        load_config(config_path)
    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "content",
    [
        "[",
        "[]",
        "min_year: 1800",
        "min_year: true\nmax_year: 2026\ninput: x\noutput: y",
        "min_year: 2000\nmax_year: 1900\ninput: x\noutput: y",
    ],
)
def test_invalid_yaml_and_schema(tmp_path, content):
    path = tmp_path / "bad.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="configuration") as error:
        load_config(path)
    assert error.value.__cause__ is not None


@pytest.mark.parametrize(
    "field,value",
    [("input", ""), ("output", 42), ("output", "books.csv"), ("output", "config.yaml")],
)
def test_bad_configuration_paths(config_path, field, value):
    data = yaml.safe_load(config_path.read_text())
    data[field] = value
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(config_path)


def test_missing_configuration_file(tmp_path):
    with pytest.raises(ConfigurationError) as error:
        load_config(tmp_path / "absent.yaml")
    assert isinstance(error.value.__cause__, FileNotFoundError)


def test_config_file_cannot_also_be_input(config_path):
    data = yaml.safe_load(config_path.read_text())
    data["input"] = config_path.name
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(config_path)
