import pytest

from book_catalog.exceptions import ImportError, ValidationError
from book_catalog.importers import read_books

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "row",
    [
        "id,title\n1,x\n",
        "isbn,title,author,year,pages\nx,t,a,wrong,1\n",
        "isbn,title,author,year,pages\nx,t,a,2000\n",
        "isbn,title,author,year,pages\nx,t,a,2000,1,extra\n",
        'isbn,title,author,year,pages\n"unterminated',
    ],
)
def test_malformed_csv_is_custom_import_error(tmp_path, policy, row):
    path = tmp_path / "bad.csv"
    path.write_text(row, encoding="utf-8")
    with pytest.raises(ImportError) as error:
        read_books(path, policy)
    assert error.value.__cause__ is not None


def test_numeric_conversion_retains_two_level_exception_chain(tmp_path, policy):
    path = tmp_path / "bad.csv"
    path.write_text("isbn,title,author,year,pages\nx,title,author,2000,wrong\n")
    with pytest.raises(ImportError) as error:
        read_books(path, policy)
    assert isinstance(error.value.__cause__, ValidationError)
    assert "line 2" in str(error.value.__cause__)
    assert isinstance(error.value.__cause__.__cause__, ValueError)


def test_missing_input_file_is_chained(tmp_path, policy):
    with pytest.raises(ImportError) as error:
        read_books(tmp_path / "absent.csv", policy)
    assert isinstance(error.value.__cause__, FileNotFoundError)
