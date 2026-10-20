import csv
import io

# Spreadsheet apps run cells starting with these as formulas (CSV injection).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

STUDENT_COLUMNS = [
    ("Name", "full_name"),
    ("Email", "email"),
    ("Student ID", "student_id"),
    ("Department", "department"),
    ("Email verified", "is_email_verified"),
    ("Active", "is_active"),
    ("Joined", "date_joined"),
    ("Listings", "listing_count"),
    ("Active listings", "active_listing_count"),
    ("Exchange requests", "request_count"),
]


def _cell(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if hasattr(value, "date"):
        return value.date().isoformat()
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def students_csv(students):
    """The student roster as CSV text, one row per student."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _ in STUDENT_COLUMNS])
    for student in students:
        writer.writerow([_cell(getattr(student, field)) for _, field in STUDENT_COLUMNS])
    return buffer.getvalue()
