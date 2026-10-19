import pytest

from books.isbn import InvalidISBN, to_isbn10, to_isbn13


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("978-0-262-03384-8", "9780262033848"),
        ("0262033844", "9780262033848"),
        ("0-8044-2957-X", "9780804429573"),
        (" 9780134685991 ", "9780134685991"),
    ],
)
def test_to_isbn13_normalises(raw, expected):
    assert to_isbn13(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "9780262033849", "0262033845", "abcdefghij"])
def test_to_isbn13_rejects_invalid(raw):
    with pytest.raises(InvalidISBN):
        to_isbn13(raw)


def test_to_isbn10_round_trip():
    assert to_isbn10("9780262033848") == "0262033844"
    assert to_isbn10("9780804429573") == "080442957X"
    assert to_isbn10("9791234567896") is None
