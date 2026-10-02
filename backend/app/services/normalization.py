import re


def normalize_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Full name is required.")
    return normalized


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Email is required.")
    return normalized


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        raise ValueError("Phone must contain exactly 11 digits.")
    return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"


def normalize_cep(value: str) -> str:
    normalized = value.strip()
    if not re.fullmatch(r"\d{5}-?\d{3}", normalized):
        raise ValueError("CEP must contain exactly 8 digits, with an optional hyphen.")
    return normalized.replace("-", "")


def normalize_source(value: str | None) -> str | None:
    return value.strip() if value is not None else None
