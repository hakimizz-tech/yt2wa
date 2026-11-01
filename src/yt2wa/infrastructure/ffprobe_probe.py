"""Read real file properties with ffprobe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yt2wa.domain.errors import TranscodeError
from yt2wa.domain.models import StreamFacts
from yt2wa.domain.mp4_atoms import is_faststart, parse_box_header
from yt2wa.infrastructure.process import run_capture


def _rate(text: str | None) -> float:
    """Turn '30000/1001' into a float."""
    if not text or "/" not in text:
        return float(text or 0)
    top, bottom = text.split("/", 1)
    return float(top) / float(bottom) if float(bottom) else 0.0


def _rotation(stream: dict[str, Any]) -> int:
    """Return the rotation in degrees (0, 90, 180 or 270)."""
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        value = float(tags["rotate"])
    else:
        value = 0.0
        for side in stream.get("side_data_list") or []:
            if "rotation" in side:
                value = float(side["rotation"])
    return int(round(abs(value))) % 360


def _optional_int(value: Any) -> int | None:
    """Convert a value to int, or None when it is missing."""
    return int(value) if value not in (None, "") else None


def parse_ffprobe_json(
    data: dict[str, Any], size_bytes: int, faststart: bool | None
) -> StreamFacts:
    """Turn ffprobe's JSON output into StreamFacts."""
    streams = data.get("streams", [])
    video: dict[str, Any] = next(
        (s for s in streams if s.get("codec_type") == "video"), {}
    )
    audio: dict[str, Any] = next(
        (s for s in streams if s.get("codec_type") == "audio"), {}
    )
    fmt = data.get("format", {})
    fps = _rate(video.get("avg_frame_rate")) or _rate(
        video.get("r_frame_rate")
    )
    return StreamFacts(
        container=fmt.get("format_name", ""),
        vcodec=video.get("codec_name"),
        vprofile=video.get("profile"),
        vlevel=_optional_int(video.get("level")),
        pix_fmt=video.get("pix_fmt"),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=fps,
        rotation=_rotation(video),
        acodec=audio.get("codec_name"),
        aprofile=audio.get("profile"),
        channels=_optional_int(audio.get("channels")),
        sample_rate=_optional_int(audio.get("sample_rate")),
        size_bytes=size_bytes,
        duration_s=float(fmt.get("duration") or video.get("duration") or 0),
        faststart=faststart,
    )


def read_top_level_boxes(path: Path, limit: int = 64) -> list[str]:
    """List top-level MP4 boxes, stopping at the first moov or mdat."""
    boxes: list[str] = []
    total = path.stat().st_size
    offset = 0
    with path.open("rb") as handle:
        while offset < total and len(boxes) < limit:
            handle.seek(offset)
            header = handle.read(16)
            if len(header) < 8:
                break
            box_type, size, header_len = parse_box_header(header)
            boxes.append(box_type)
            if box_type in ("moov", "mdat") or size == 0:
                break
            if size < header_len:
                break
            offset += size
    return boxes


class FfprobeMediaProbe:
    """MediaProbe implemented with the ffprobe program."""

    def __init__(self, ffprobe_bin: str = "ffprobe") -> None:
        self._bin = ffprobe_bin

    def inspect(self, path: Path) -> StreamFacts:
        """Return the facts about a media file."""
        result = run_capture(
            [
                self._bin,
                "-v", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ]  # fmt: skip
        )
        if result.returncode != 0:
            raise TranscodeError(
                f"ffprobe could not read {path.name}.",
                hint=result.stderr.strip()[-300:] or None,
            )
        data = json.loads(result.stdout or "{}")
        names = data.get("format", {}).get("format_name", "")
        faststart = None
        if "mp4" in names.split(","):
            faststart = is_faststart(read_top_level_boxes(path))
        return parse_ffprobe_json(data, path.stat().st_size, faststart)
