"""A transcription of the physical disc's matrix, scoped to one rip."""


def observed_matrix(value: str | None) -> str:
    if value is None or value == "":
        return ""
    if (
        not isinstance(value, str)
        or len(value) > 250
        or any(not char.isprintable() for char in value)
    ):
        raise ValueError("Matrix/runout must be one line of up to 250 printable characters")
    return value.strip()
