"""Pure helpers for reading MP4 box (atom) headers."""

from __future__ import annotations

from collections.abc import Iterable


def parse_box_header(data: bytes) -> tuple[str, int, int]:
    """Read one MP4 box header.

    Returns:
        (box type, total box size, header length). A size of 0 means
        the box runs to the end of the file.
    """
    if len(data) < 8:
        raise ValueError("need at least 8 bytes")
    size = int.from_bytes(data[:4], "big")
    box_type = data[4:8].decode("latin-1")
    header_len = 8
    if size == 1:
        if len(data) < 16:
            raise ValueError("need 16 bytes for a large box")
        size = int.from_bytes(data[8:16], "big")
        header_len = 16
    return box_type, size, header_len


def is_faststart(box_types: Iterable[str]) -> bool | None:
    """Return True when 'moov' comes before 'mdat'.

    Returns None when neither box was seen, so the answer is unknown.
    """
    for box_type in box_types:
        if box_type == "moov":
            return True
        if box_type == "mdat":
            return False
    return None
