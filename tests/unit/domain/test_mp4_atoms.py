import pytest

from yt2wa.domain.mp4_atoms import is_faststart, parse_box_header


def box(kind: bytes, size: int) -> bytes:
    return size.to_bytes(4, "big") + kind


def test_parse_regular_header():
    assert parse_box_header(box(b"ftyp", 24)) == ("ftyp", 24, 8)


def test_parse_large_header():
    data = (1).to_bytes(4, "big") + b"mdat" + (5000).to_bytes(8, "big")
    assert parse_box_header(data) == ("mdat", 5000, 16)


def test_short_data_is_rejected():
    with pytest.raises(ValueError):
        parse_box_header(b"abc")


def test_faststart_detection():
    assert is_faststart(["ftyp", "moov", "mdat"]) is True
    assert is_faststart(["ftyp", "mdat", "moov"]) is False
    assert is_faststart(["ftyp"]) is None
