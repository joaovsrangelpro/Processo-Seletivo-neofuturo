import pytest

from app.services.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
)


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("  João Victor Rangel  ", "João Victor Rangel"),
        ("João   Victor    Rangel", "João Victor Rangel"),
    ],
)
def test_normalize_name(raw_name: str, expected: str) -> None:
    assert normalize_name(raw_name) == expected


@pytest.mark.parametrize(
    ("raw_email", "expected"),
    [
        ("JOAO@EMAIL.COM", "joao@email.com"),
        ("  joao@email.com  ", "joao@email.com"),
    ],
)
def test_normalize_email(raw_email: str, expected: str) -> None:
    assert normalize_email(raw_email) == expected


@pytest.mark.parametrize(
    "raw_phone",
    [
        "21987654321",
        "(21) 98765-4321",
    ],
)
def test_normalize_phone(raw_phone: str) -> None:
    assert normalize_phone(raw_phone) == "(21) 98765-4321"


def test_normalize_phone_rejects_incorrect_digit_count() -> None:
    with pytest.raises(ValueError, match="exactly 11 digits"):
        normalize_phone("21 8765-4321")
