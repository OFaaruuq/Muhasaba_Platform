"""Optional contact field normalization."""


def normalize_optional_email(value):
    cleaned = (value or "").strip()
    return cleaned or None


def normalize_optional_phone(value):
    cleaned = (value or "").strip()
    return cleaned or None
