"""ISBN parsing and normalisation. Everything is stored as ISBN-13."""

import re


class InvalidISBN(ValueError):
    pass


def _clean(raw: str) -> str:
    return re.sub(r"[\s-]", "", str(raw or "")).upper()


def _isbn10_valid(isbn: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", isbn):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
    return total % 11 == 0


def _isbn13_check_digit(first12: str) -> str:
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(first12))
    return str((10 - total % 10) % 10)


def _isbn13_valid(isbn: str) -> bool:
    return bool(re.fullmatch(r"\d{13}", isbn)) and _isbn13_check_digit(isbn[:12]) == isbn[12]


def to_isbn13(raw: str) -> str:
    """Return the canonical ISBN-13 for an ISBN-10/13 (hyphens/spaces allowed)."""
    isbn = _clean(raw)
    if len(isbn) == 13 and _isbn13_valid(isbn):
        return isbn
    if len(isbn) == 10 and _isbn10_valid(isbn):
        first12 = "978" + isbn[:9]
        return first12 + _isbn13_check_digit(first12)
    raise InvalidISBN(f"'{raw}' is not a valid ISBN-10 or ISBN-13.")


def to_isbn10(isbn13: str) -> str | None:
    """ISBN-10 equivalent of a 978-prefixed ISBN-13, else None."""
    if not isbn13.startswith("978"):
        return None
    core = isbn13[3:12]
    total = sum((10 - i) * int(c) for i, c in enumerate(core))
    check = (11 - total % 11) % 11
    return core + ("X" if check == 10 else str(check))
