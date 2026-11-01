#!/usr/bin/env bash
# Scaffold the yt2wa project in the current directory.
#
# Usage:
#   bash setup_yt2wa.sh            # create missing files only
#   FORCE=1 bash setup_yt2wa.sh    # replace files that already exist
#
# Run it from the project root (the folder that holds your .venv).
set -euo pipefail

# write_file <path>  — reads file content from stdin, skips if it already exists
write_file() {
  local f="$1"
  mkdir -p "$(dirname "$f")"
  if [[ -e "$f" && "${FORCE:-0}" != "1" ]]; then
    echo "  skip    $f"
    cat >/dev/null
  else
    cat >"$f"
    echo "  create  $f"
  fi
}

# overwrite_file <path> — for template files we must replace. Backs up the
# original once to <path>.bak and never clobbers your edits on a re-run.
overwrite_file() {
  local f="$1"
  mkdir -p "$(dirname "$f")"
  if [[ -e "$f.bak" && "${FORCE:-0}" != "1" ]]; then
    echo "  skip    $f (already replaced, original in $f.bak)"
    cat >/dev/null
    return 0
  fi
  if [[ -e "$f" && ! -e "$f.bak" ]]; then
    cp "$f" "$f.bak"
    echo "  backup  $f.bak"
  fi
  cat >"$f"
  echo "  replace $f"
}

# add_line <file> <line> — append a line if it is not already there
add_line() {
  touch "$1"
  grep -qxF -- "$2" "$1" || echo "$2" >>"$1"
}

echo "Scaffolding yt2wa in $(pwd)"
echo


# ---------------------------------------------------------------------------
# Project metadata and tooling
# ---------------------------------------------------------------------------
echo "== Project files"

overwrite_file pyproject.toml <<'PYEOF'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "yt2wa"
version = "0.1.0"
description = "Download YouTube videos and convert them for WhatsApp."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = ["yt-dlp>=2024.8.6"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "hypothesis>=6.100",
    "mypy>=1.10",
    "ruff>=0.5",
    "import-linter>=2.0",
    "pip-audit>=2.7",
]

[project.scripts]
yt2wa = "yt2wa.interface.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
yt2wa = ["py.typed"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "tests"]
addopts = "-m 'not network'"
markers = [
    "network: needs internet access",
    "ffmpeg: needs ffmpeg installed",
]

[tool.ruff]
line-length = 79
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "D"]
# D1 = "missing docstring" rules. Docstrings are short and optional.
ignore = ["D1"]

[tool.ruff.lint.isort]
known-first-party = ["yt2wa", "fakes"]

[tool.ruff.lint.pydocstyle]
convention = "pep257"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src"]

[[tool.mypy.overrides]]
module = "yt_dlp.*"
ignore_missing_imports = true

[tool.importlinter]
root_package = "yt2wa"

[[tool.importlinter.contracts]]
name = "Domain does not depend on outer layers"
type = "forbidden"
source_modules = ["yt2wa.domain"]
forbidden_modules = [
    "yt2wa.application",
    "yt2wa.infrastructure",
    "yt2wa.interface",
    "yt2wa.bootstrap",
]

[[tool.importlinter.contracts]]
name = "Application depends on the domain only"
type = "forbidden"
source_modules = ["yt2wa.application"]
forbidden_modules = [
    "yt2wa.infrastructure",
    "yt2wa.interface",
    "yt2wa.bootstrap",
]

[[tool.importlinter.contracts]]
name = "Infrastructure does not depend on outer layers"
type = "forbidden"
source_modules = ["yt2wa.infrastructure"]
forbidden_modules = [
    "yt2wa.application",
    "yt2wa.interface",
    "yt2wa.bootstrap",
]
PYEOF

# .gitignore may already exist (for example from `uv init`), so only append.
for line in \
  ".venv/" "__pycache__/" "*.py[cod]" "*.egg-info/" "build/" "dist/" \
  ".pytest_cache/" ".mypy_cache/" ".ruff_cache/" ".hypothesis/" \
  ".coverage" "out/" ".env" "cookies.txt" "tests/fixtures/*.mp4" \
  "tests/fixtures/*.webm" "tests/fixtures/*.mkv" "*.bak"; do
  add_line .gitignore "$line"
done
echo "  update  .gitignore"

write_file .env.example <<'PYEOF'
# Copy to .env for local development. Real environment variables win.
# Never put secrets in version control.

# Output intent when --target is omitted: original, chat or status.
YT2WA_DEFAULT_TARGET=chat
# Resolution when -r is omitted: 144, 240, 360, 480, 720, 1080 or best.
YT2WA_DEFAULT_RESOLUTION=480
# Size cap in MB for chat/status files (0 disables the cap).
YT2WA_MAX_SIZE_MB=16
# Lowest resolution the size guard may drop to.
YT2WA_MIN_RESOLUTION_FLOOR=360
# Optional TOML file that overrides the built-in compatibility profiles.
# YT2WA_PROFILE_FILE=config/presets.default.toml
# Scratch space for job folders (defaults to the system temp folder).
# YT2WA_WORK_DIR=/tmp/yt2wa
YT2WA_OUTPUT_DIR=./out
YT2WA_FFMPEG_BIN=ffmpeg
YT2WA_FFPROBE_BIN=ffprobe
# ffmpeg thread count (0 lets ffmpeg decide).
YT2WA_FFMPEG_THREADS=0
YT2WA_NET_RETRIES=3
# Optional cookies file for age-restricted videos (opt-in only).
# YT2WA_COOKIES_FILE=cookies.txt
YT2WA_LOG_LEVEL=INFO
# text or json
YT2WA_LOG_FORMAT=text
PYEOF

write_file config/presets.default.toml <<'PYEOF'
# Compatibility profiles. These values mirror the built-in defaults.
# Copy this file and point YT2WA_PROFILE_FILE at it to change them.
# Keys you leave out keep their built-in value. The "status" profile
# starts from the "chat" profile.

[chat]
max_long_edge = 1920
max_short_edge = 1080
max_fps = 30.0
max_h264_level = 40
allowed_h264_profiles = ["Baseline", "Constrained Baseline", "Main", "High"]
audio_bitrate_k = 128
sample_rates = [44100, 48000]
default_sample_rate = 48000
crf = 23
preset = "medium"
# WhatsApp limits change over time. Verify before relying on this value.
size_cap_mb = 16
floor_resolution = 360

[chat.min_video_bitrate_k]
144 = 60
240 = 120
360 = 250
480 = 400
720 = 800
1080 = 1500

[chat.max_video_bitrate_k]
144 = 200
240 = 400
360 = 800
480 = 1400
720 = 2800
1080 = 5500

[status]
# 9:16 is ideal for Status. Other shapes only trigger a warning.
advisory_aspect = 0.5625
advisory_max_duration_s = 60.0
PYEOF

# Makefiles need tabs, so the four-space indents below are converted.
awk '{ sub(/^    /, "\t"); print }' <<'PYEOF' | write_file Makefile
.PHONY: install test lint format type imports check docker clean

install:
    pip install -e ".[dev]"

test:
    pytest

lint:
    ruff check .

format:
    ruff format .

type:
    mypy

imports:
    lint-imports

check: lint type imports test

docker:
    docker build -t yt2wa .

clean:
    rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis
PYEOF
write_file Dockerfile <<'PYEOF'
# Build once, run anywhere. ffmpeg is bundled so dev and prod match.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install .

RUN useradd --create-home app && mkdir /out && chown app /out
USER app
ENV YT2WA_OUTPUT_DIR=/out

ENTRYPOINT ["yt2wa"]
CMD ["--help"]
PYEOF

write_file docker-compose.yml <<'PYEOF'
services:
  yt2wa:
    build: .
    image: yt2wa
    env_file:
      - path: .env
        required: false
    volumes:
      - ./out:/out
PYEOF

write_file .pre-commit-config.yaml <<'PYEOF'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.7
    hooks:
      - id: ruff
      - id: ruff-format
PYEOF

write_file LICENSE <<PYEOF
MIT License

Copyright (c) $(date +%Y) yt2wa contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
PYEOF

overwrite_file README.md <<'PYEOF'
# yt2wa

Download a YouTube video or Short with
[yt-dlp](https://github.com/yt-dlp/yt-dlp) and, when you want to share it,
convert it with [ffmpeg](https://ffmpeg.org) into a file that WhatsApp can
send as a Status or in a chat.

> **Legal note.** Downloading may break YouTube's Terms of Service or
> copyright law. Use this tool only for content you own, have permission to
> use, or that is licensed for reuse.

## Install

ffmpeg and ffprobe must be on your `PATH` (or set `YT2WA_FFMPEG_BIN` and
`YT2WA_FFPROBE_BIN`).

```bash
pip install -e ".[dev]"
yt2wa doctor
```

## Usage

```bash
# Share in a chat or group (default target, 480p).
yt2wa "https://youtu.be/VIDEO_ID"

# Post as a Status in 720p.
yt2wa "https://youtu.be/VIDEO_ID" -t status -r 720

# Keep the video as it is, for watching on your own phone.
yt2wa "https://youtu.be/VIDEO_ID" --keep-original -r best

# Check any file against the WhatsApp profile.
yt2wa verify clip.mp4 -t status
```

## Targets

| Target     | Purpose                      | Re-encode?                 |
|------------|------------------------------|----------------------------|
| `original` | Watch later, not for sharing | Never                      |
| `chat`     | Send to a person or group    | Only when the file needs it |
| `status`   | Post as a WhatsApp Status    | Only when the file needs it |

`-r/--resolution` accepts `144, 240, 360, 480, 720, 1080, best`. The number
is the short edge, so `1080` means 1920x1080 or 1080x1920. Output is never
upscaled. The default is `480`.

A passing compliance report means the file matches the recommended
settings. It is not a guarantee that WhatsApp accepts it. WhatsApp may
re-compress media. Send the file as a **Document** to keep its quality.

## Exit codes

| Code | Meaning                                  |
|------|------------------------------------------|
| 0    | Success                                  |
| 2    | Invalid usage or configuration           |
| 3    | Unsupported URL                          |
| 4    | Source unavailable                       |
| 5    | Network failure                          |
| 6    | Missing or incompatible dependency       |
| 7    | Transcode failed                         |
| 8    | Could not meet size or compliance limits |
| 130  | Interrupted                              |

## Development

```bash
make check      # ruff, mypy, import-linter and pytest
```

See `docs/architecture.md` for the design.
PYEOF

# ---------------------------------------------------------------------------
# Docs, scripts and CI
# ---------------------------------------------------------------------------
echo "== Docs, scripts and CI"

if [[ -f yt2wa-architecture.md && ! -e docs/architecture.md ]]; then
  mkdir -p docs
  cp yt2wa-architecture.md docs/architecture.md
  echo "  create  docs/architecture.md (copied from yt2wa-architecture.md)"
else
  write_file docs/architecture.md <<'PYEOF'
# Architecture

Copy `yt2wa-architecture.md` here to keep the design next to the code.
PYEOF
fi

write_file docs/adr/0001-python-and-ytdlp-library-api.md <<'PYEOF'
# 0001: Python, with the yt-dlp library API

**Status:** accepted

yt-dlp is a Python library. Calling it directly gives us progress hooks and
structured metadata, and avoids parsing command output.
PYEOF

write_file docs/adr/0002-hexagonal-architecture.md <<'PYEOF'
# 0002: Hexagonal architecture

**Status:** accepted

Dependencies point inward: interface -> application -> domain <-
infrastructure. yt-dlp and ffmpeg sit behind ports so they can be faked in
tests or replaced. `import-linter` enforces the rule in CI.
PYEOF

write_file docs/adr/0003-profile-as-data.md <<'PYEOF'
# 0003: Compatibility profiles are data

**Status:** accepted

WhatsApp limits change. They live in a profile (built-in defaults plus an
optional TOML file), never in scattered constants.
PYEOF

write_file docs/adr/0004-verify-output-not-settings.md <<'PYEOF'
# 0004: Verify the output file, not the encoder settings

**Status:** accepted

Re-encoding does not guarantee a compliant or smaller file. One pure
function, `check_compliance`, decides remux vs. transcode, verifies the
result and powers `yt2wa verify`.
PYEOF

write_file docs/whatsapp-constraints.md <<'PYEOF'
# WhatsApp constraints

Last verified: never (check before release)

| Item             | Value used by yt2wa                 |
|------------------|-------------------------------------|
| Container        | MP4 with `+faststart`               |
| Video            | H.264, yuv420p, up to 30 fps        |
| Audio            | AAC-LC, stereo, 44.1 or 48 kHz      |
| Chat resolution  | Up to 1920x1080 (long x short edge) |
| Status           | Up to 1080x1920, 9:16 is ideal      |
| Size cap         | 16 MB (media, not Document)         |
| Status duration  | Advisory warning above 60 s         |

These are recommended settings, not a guarantee of acceptance.
PYEOF

write_file scripts/release.sh <<'PYEOF'
#!/usr/bin/env bash
# Build the wheel and the Docker image for the current version.
set -euo pipefail

version="$(python -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
python -m pip install --quiet build
python -m build
docker build -t "yt2wa:${version}" .
echo "Built yt2wa ${version}"
PYEOF
chmod +x scripts/release.sh

write_file scripts/check_whatsapp_limits.py <<'PYEOF'
"""Remind us to re-check the WhatsApp limits."""

import re
import sys
from datetime import date
from pathlib import Path

MAX_AGE_DAYS = 90
DOC = Path(__file__).resolve().parents[1] / "docs" / "whatsapp-constraints.md"


def main() -> int:
    """Return 1 when the limits were not verified recently."""
    match = re.search(r"Last verified: (\d{4}-\d{2}-\d{2})", DOC.read_text())
    if match is None:
        print("WhatsApp limits have never been verified.")
        return 1
    age = (date.today() - date.fromisoformat(match.group(1))).days
    if age > MAX_AGE_DAYS:
        print(f"WhatsApp limits were last verified {age} days ago.")
        return 1
    print(f"WhatsApp limits verified {age} days ago.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF

write_file scripts/make_fixtures.sh <<'PYEOF'
#!/usr/bin/env bash
# Generate small test videos in tests/fixtures (needs ffmpeg with libx264).
set -euo pipefail

out="$(dirname "$0")/../tests/fixtures"
mkdir -p "$out"
src="testsrc=duration=3:size=854x480:rate=30"
tone="sine=frequency=440:duration=3"

# A file that already matches the WhatsApp profile.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 2 -ar 48000 \
  -movflags +faststart "$out/h264_aac_compliant.mp4"

# moov atom at the end (no faststart).
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 2 -ar 48000 \
  "$out/moov_at_end.mp4"

# Mono audio at 22.05 kHz.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 1 -ar 22050 \
  -movflags +faststart "$out/mono_22khz.mp4"

# Not H.264 and not AAC.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v mpeg4 -c:a libmp3lame "$out/mpeg4_mp3.mkv"

echo "Fixtures written to $out"
PYEOF
chmod +x scripts/make_fixtures.sh

write_file tests/fixtures/README.md <<'PYEOF'
# Fixtures

Binary fixtures are not committed. Generate them with:

```bash
scripts/make_fixtures.sh
```
PYEOF

write_file .github/workflows/ci.yml <<'PYEOF'
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: Install ffmpeg (Linux)
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - name: Install ffmpeg (macOS)
        if: runner.os == 'macOS'
        run: brew install ffmpeg
      - name: Install ffmpeg (Windows)
        if: runner.os == 'Windows'
        run: choco install ffmpeg -y
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy
      - run: lint-imports
      - run: pytest
PYEOF

write_file .github/workflows/release.yml <<'PYEOF'
name: release

on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build && python -m build
      - run: docker build -t yt2wa:${{ github.ref_name }} .
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
PYEOF


# ---------------------------------------------------------------------------
# Package skeleton
# ---------------------------------------------------------------------------
echo "== Package skeleton"

write_file src/yt2wa/__init__.py <<'PYEOF'
"""yt2wa: download YouTube videos and make them WhatsApp friendly."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yt2wa")
except PackageNotFoundError:  # Running from a source tree.
    __version__ = "0.1.0"
PYEOF

write_file src/yt2wa/__main__.py <<'PYEOF'
"""Allow ``python -m yt2wa``."""

from yt2wa.interface.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
PYEOF

write_file src/yt2wa/py.typed </dev/null

# ---------------------------------------------------------------------------
# Domain layer: pure rules, no I/O
# ---------------------------------------------------------------------------
echo "== Domain layer"

write_file src/yt2wa/domain/__init__.py <<'PYEOF'
"""Domain layer: entities and pure rules. It performs no I/O."""
PYEOF

write_file src/yt2wa/domain/models.py <<'PYEOF'
"""Entities and value objects shared by every layer.

All of them are immutable and free of I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# Resolution value that means "the highest quality available".
BEST_RESOLUTION = 0

# Short-edge sizes the tool understands, smallest first.
RESOLUTION_RUNGS = (144, 240, 360, 480, 720, 1080)


class Target(StrEnum):
    """What the output file is meant for."""

    ORIGINAL = "original"
    CHAT = "chat"
    STATUS = "status"

    @property
    def is_shareable(self) -> bool:
        """Return True when the file must suit WhatsApp."""
        return self is not Target.ORIGINAL


class SourceKind(StrEnum):
    """The kind of YouTube link we were given."""

    VIDEO = "video"
    SHORT = "short"
    UNSUPPORTED = "unsupported"


class Method(StrEnum):
    """How the output file was produced."""

    DOWNLOAD = "download"
    REMUX = "remux"
    TRANSCODE = "transcode"


class Severity(StrEnum):
    """How serious a failed check is."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class SourceRef:
    """A classified YouTube link."""

    url: str
    kind: SourceKind
    video_id: str | None = None


@dataclass(frozen=True)
class SourceMetadata:
    """Basic facts about a video, known before downloading it."""

    video_id: str
    title: str
    duration_s: float
    uploader: str | None = None


@dataclass(frozen=True)
class FormatChoice:
    """How yt-dlp should pick the streams to download."""

    selector: str
    sort: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class StreamFacts:
    """What ffprobe tells us about a media file."""

    container: str
    vcodec: str | None
    vprofile: str | None
    vlevel: int | None
    pix_fmt: str | None
    width: int
    height: int
    fps: float
    rotation: int
    acodec: str | None
    aprofile: str | None
    channels: int | None
    sample_rate: int | None
    size_bytes: int
    duration_s: float
    faststart: bool | None

    @property
    def has_audio(self) -> bool:
        """Return True when the file has an audio stream."""
        return self.acodec is not None

    @property
    def display_size(self) -> tuple[int, int]:
        """Return (width, height) as a viewer sees it after rotation."""
        if self.rotation in (90, 270):
            return self.height, self.width
        return self.width, self.height

    @property
    def short_edge(self) -> int:
        """Return the shorter side of the displayed picture."""
        return min(self.display_size)

    @property
    def aspect(self) -> float:
        """Return displayed width divided by height."""
        width, height = self.display_size
        return width / height if height else 0.0


@dataclass(frozen=True)
class Progress:
    """A progress update from a long running step."""

    stage: str
    fraction: float | None = None


ProgressCallback = Callable[[Progress], None]


def ignore_progress(progress: Progress) -> None:
    """Accept a progress update and do nothing with it."""


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one compliance check."""

    name: str
    expected: str
    actual: str
    passed: bool
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class ComplianceReport:
    """All check results for one file."""

    results: tuple[CheckResult, ...]

    @property
    def failed(self) -> tuple[CheckResult, ...]:
        """Return every check that did not pass."""
        return tuple(r for r in self.results if not r.passed)

    @property
    def errors(self) -> tuple[CheckResult, ...]:
        """Return failed checks that must be fixed."""
        return tuple(r for r in self.failed if r.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[CheckResult, ...]:
        """Return failed checks that are only advice."""
        return tuple(
            r for r in self.failed if r.severity is Severity.WARNING
        )

    @property
    def ok(self) -> bool:
        """Return True when no error-level check failed."""
        return not self.errors


@dataclass(frozen=True)
class PathDecision:
    """Whether to copy the streams or re-encode them."""

    method: Method
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LadderStep:
    """One attempt in the size guard ladder."""

    kind: str  # "crf" or "bitrate"
    resolution: int
    video_bitrate_k: int | None = None


@dataclass(frozen=True)
class Candidate:
    """A finished output file together with its compliance report."""

    path: Path
    report: ComplianceReport
    size_bytes: int
    method: Method


@dataclass(frozen=True)
class ConversionResult:
    """What the user gets back from a conversion."""

    output: Path
    target: Target
    method: Method
    title: str
    requested_resolution: int
    effective_resolution: int
    size_bytes: int
    report: ComplianceReport | None
    warnings: tuple[str, ...] = ()
    source_kept: Path | None = None


@dataclass(frozen=True)
class DryRunPlan:
    """A description of what a run would do."""

    lines: tuple[str, ...]
PYEOF

write_file src/yt2wa/domain/errors.py <<'PYEOF'
"""Domain errors.

Adapters translate third-party exceptions into these at the boundary, so
no outside exception type leaks inward.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every error the tool raises on purpose."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(DomainError):
    """The user gave invalid input."""


class ConfigError(UsageError):
    """A setting or profile file is invalid."""


class UnsupportedSourceError(DomainError):
    """The link is not a video or Short we can handle."""


class SourceUnavailableError(DomainError):
    """The video cannot be fetched."""


class PrivateVideoError(SourceUnavailableError):
    """The video is private."""


class RemovedVideoError(SourceUnavailableError):
    """The video was removed or is no longer available."""


class GeoBlockedError(SourceUnavailableError):
    """The video is blocked in this country."""


class AgeRestrictedError(SourceUnavailableError):
    """The video needs a signed-in, age-verified account."""


class NetworkError(DomainError):
    """A network problem survived all retries."""


class DependencyError(DomainError):
    """A required program is missing or too old."""


class MissingBinaryError(DependencyError):
    """An executable could not be found."""


class VersionTooOldError(DependencyError):
    """An installed program is older than we support."""


class TranscodeError(DomainError):
    """ffmpeg or ffprobe failed."""


class ConstraintError(DomainError):
    """The result cannot meet the requested limits."""


class SizeCapError(ConstraintError):
    """The video cannot be made small enough."""


class NonCompliantOutputError(ConstraintError):
    """The finished file fails the compatibility checks."""
PYEOF

write_file src/yt2wa/domain/ports.py <<'PYEOF'
"""Ports: the interfaces the application needs from the outside world."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from yt2wa.domain.models import (
    FormatChoice,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    StreamFacts,
)


class Downloader(Protocol):
    """Fetches a video from the web."""

    def probe(self, ref: SourceRef) -> SourceMetadata:
        """Return metadata without downloading the video."""
        ...

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        """Download the video into dest_dir and return the file path."""
        ...


class Transcoder(Protocol):
    """Runs ffmpeg."""

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        """Run ffmpeg with the given argument list."""
        ...


class MediaProbe(Protocol):
    """Reads the real properties of a media file."""

    def inspect(self, path: Path) -> StreamFacts:
        """Return the facts about a file."""
        ...


class Workspace(Protocol):
    """Owns temporary folders and the final output location."""

    def new_job_dir(self) -> Path:
        """Create and return a private scratch folder."""
        ...

    def publish(self, src: Path, dest_dir: Path, final_name: str) -> Path:
        """Move src into dest_dir without ever leaving a partial file."""
        ...

    def cleanup(self, job_dir: Path) -> None:
        """Delete a scratch folder."""
        ...
PYEOF

write_file src/yt2wa/domain/url_rules.py <<'PYEOF'
"""Decide what kind of YouTube link we were given."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from yt2wa.domain.models import SourceKind, SourceRef

_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_VIDEO_ID = re.compile(r"^[\w-]{11}$")
_VIDEO_PREFIXES = {"live", "embed", "v"}


def _ref(url: str, kind: SourceKind, video_id: str | None) -> SourceRef:
    """Build a reference, rejecting ids that do not look right."""
    if video_id is None or not _VIDEO_ID.match(video_id):
        return SourceRef(url, SourceKind.UNSUPPORTED)
    return SourceRef(url, kind, video_id)


def classify_url(url: str) -> SourceRef:
    """Classify a link as a video, a Short or unsupported."""
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in _HOSTS:
        return SourceRef(url, SourceKind.UNSUPPORTED)

    parts = [p for p in parsed.path.split("/") if p]
    if host.endswith("youtu.be"):
        return _ref(url, SourceKind.VIDEO, parts[0] if parts else None)
    if not parts:
        return SourceRef(url, SourceKind.UNSUPPORTED)

    head = parts[0]
    if head == "watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        return _ref(url, SourceKind.VIDEO, video_id)
    if head == "shorts" and len(parts) > 1:
        return _ref(url, SourceKind.SHORT, parts[1])
    if head in _VIDEO_PREFIXES and len(parts) > 1:
        return _ref(url, SourceKind.VIDEO, parts[1])
    return SourceRef(url, SourceKind.UNSUPPORTED)


def sanitize_filename(title: str, max_len: int = 80) -> str:
    """Turn a video title into a safe file name (without extension)."""
    cleaned = re.sub(r"[^\w\s.-]", "", title, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("._-")[:max_len].rstrip("._-")
    reserved = {"con", "prn", "aux", "nul"}
    if not cleaned or cleaned.lower() in reserved:
        return "video"
    return cleaned
PYEOF

write_file src/yt2wa/domain/formats.py <<'PYEOF'
"""Rules for choosing which streams to download."""

from __future__ import annotations

from yt2wa.domain.errors import UsageError
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    RESOLUTION_RUNGS,
    FormatChoice,
    Target,
)


def parse_resolution(text: str) -> int:
    """Turn '480', '480p' or 'best' into a resolution value."""
    cleaned = text.strip().lower()
    if cleaned == "best":
        return BEST_RESOLUTION
    cleaned = cleaned.removesuffix("p")
    if cleaned.isdigit() and int(cleaned) in RESOLUTION_RUNGS:
        return int(cleaned)
    choices = ", ".join(str(rung) for rung in RESOLUTION_RUNGS)
    raise UsageError(
        f"Unsupported resolution '{text}'.",
        hint=f"Use one of: {choices}, best.",
    )


def short_edge_cap(
    target: Target, requested: int, max_short_edge: int
) -> int | None:
    """Return the largest short edge allowed, or None for no limit.

    Shareable targets are always limited by the profile maximum.
    """
    if target is Target.ORIGINAL:
        return None if requested == BEST_RESOLUTION else requested
    if requested == BEST_RESOLUTION:
        return max_short_edge
    return min(requested, max_short_edge)


def build_format_selector(
    target: Target, requested: int, max_short_edge: int = 1080
) -> FormatChoice:
    """Build the yt-dlp format choice for a target and resolution.

    yt-dlp's ``res`` sort key is the short edge, so portrait Shorts and
    landscape videos are handled the same way. It prefers the largest
    stream at or below the limit, then H.264 video and AAC audio.
    """
    cap = short_edge_cap(target, requested, max_short_edge)
    res_key = "res" if cap is None else f"res:{cap}"
    return FormatChoice(
        selector="bv*+ba/b",
        sort=(res_key, "vcodec:h264", "acodec:aac"),
    )
PYEOF

write_file src/yt2wa/domain/profile.py <<'PYEOF'
"""The WhatsApp compatibility profile.

Profiles are data. The built-in defaults can be overridden by a TOML file
(see ``config/presets.default.toml``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from typing import Any

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target

_MIN_BITRATES = {144: 60, 240: 120, 360: 250, 480: 400, 720: 800, 1080: 1500}
_MAX_BITRATES = {
    144: 200,
    240: 400,
    360: 800,
    480: 1400,
    720: 2800,
    1080: 5500,
}


@dataclass(frozen=True, kw_only=True)
class CompatProfile:
    """The settings a file must match to be shared on WhatsApp."""

    name: str
    max_long_edge: int = 1920
    max_short_edge: int = 1080
    max_fps: float = 30.0
    max_h264_level: int = 40
    allowed_h264_profiles: tuple[str, ...] = (
        "Baseline",
        "Constrained Baseline",
        "Main",
        "High",
    )
    audio_bitrate_k: int = 128
    sample_rates: tuple[int, ...] = (44100, 48000)
    default_sample_rate: int = 48000
    crf: int = 23
    preset: str = "medium"
    size_cap_mb: int = 16
    floor_resolution: int = 360
    advisory_aspect: float | None = None
    advisory_max_duration_s: float | None = None
    min_video_bitrate_k: Mapping[int, int] = field(
        default_factory=lambda: dict(_MIN_BITRATES)
    )
    max_video_bitrate_k: Mapping[int, int] = field(
        default_factory=lambda: dict(_MAX_BITRATES)
    )


DEFAULT_CHAT = CompatProfile(name="chat")

# 9:16 is ideal for Status. The duration is advice only. Verify it.
DEFAULT_STATUS = replace(
    DEFAULT_CHAT,
    name="status",
    advisory_aspect=9 / 16,
    advisory_max_duration_s=60.0,
)

DEFAULT_PROFILES: Mapping[str, CompatProfile] = {
    "chat": DEFAULT_CHAT,
    "status": DEFAULT_STATUS,
}


def profile_for(
    target: Target, profiles: Mapping[str, CompatProfile]
) -> CompatProfile:
    """Return the profile used for a target.

    The original target has no profile of its own. It borrows the chat one
    so its informational report still has something to compare against.
    """
    return profiles["status" if target is Target.STATUS else "chat"]


def profile_from_mapping(
    name: str,
    data: Mapping[str, Any],
    base: CompatProfile = DEFAULT_CHAT,
) -> CompatProfile:
    """Build a profile from parsed TOML, starting from a base profile."""
    allowed = {f.name for f in fields(CompatProfile)} - {"name"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            f"Unknown setting(s) in profile '{name}': {', '.join(unknown)}.",
            hint="Compare with config/presets.default.toml.",
        )
    values = dict(data)
    try:
        for key in ("min_video_bitrate_k", "max_video_bitrate_k"):
            if key in values:
                values[key] = {int(k): int(v) for k, v in values[key].items()}
        for key in ("allowed_h264_profiles", "sample_rates"):
            if key in values:
                values[key] = tuple(values[key])
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid value in profile '{name}'.") from exc
    return replace(base, name=name, **values)
PYEOF

write_file src/yt2wa/domain/compliance.py <<'PYEOF'
"""Check a file against the compatibility profile.

``check_compliance`` is the single source of truth. It decides whether a
download can simply be copied, verifies the finished output and powers the
``verify`` command.
"""

from __future__ import annotations

from yt2wa.domain.models import (
    CheckResult,
    ComplianceReport,
    Severity,
    StreamFacts,
)
from yt2wa.domain.profile import CompatProfile

CONTAINER = "container"
VIDEO_CODEC = "video_codec"
VIDEO_PROFILE = "video_profile"
VIDEO_LEVEL = "video_level"
PIXEL_FORMAT = "pixel_format"
FRAME_RATE = "frame_rate"
RESOLUTION = "resolution"
ASPECT_PRESERVED = "aspect_preserved"
ASPECT_RATIO = "aspect_ratio"
ORIENTATION = "orientation"
AUDIO_PRESENT = "audio_present"
AUDIO_CODEC = "audio_codec"
AUDIO_PROFILE = "audio_profile"
AUDIO_CHANNELS = "audio_channels"
SAMPLE_RATE = "sample_rate"
FASTSTART = "faststart"
FILE_SIZE = "file_size"
DURATION = "duration"

_ASPECT_TOLERANCE = 0.03


def _check(
    name: str,
    expected: object,
    actual: object,
    passed: bool,
    severity: Severity = Severity.ERROR,
) -> CheckResult:
    """Build a check result, turning values into text."""
    return CheckResult(name, str(expected), str(actual), passed, severity)


def _video_checks(
    facts: StreamFacts, profile: CompatProfile, short_cap: int
) -> list[CheckResult]:
    """Check container, video codec and picture size."""
    tokens = {part.strip() for part in facts.container.split(",")}
    width, height = facts.display_size
    level = facts.vlevel
    return [
        _check(CONTAINER, "mp4", facts.container, "mp4" in tokens),
        _check(
            VIDEO_CODEC, "h264", facts.vcodec or "none", facts.vcodec == "h264"
        ),
        _check(
            VIDEO_PROFILE,
            " / ".join(profile.allowed_h264_profiles),
            facts.vprofile or "none",
            facts.vprofile in profile.allowed_h264_profiles,
        ),
        _check(
            VIDEO_LEVEL,
            f"<= {profile.max_h264_level}",
            "unknown" if level is None else level,
            level is None or level <= profile.max_h264_level,
        ),
        _check(
            PIXEL_FORMAT,
            "yuv420p",
            facts.pix_fmt or "none",
            facts.pix_fmt == "yuv420p",
        ),
        _check(
            FRAME_RATE,
            f"<= {profile.max_fps:g} fps",
            f"{facts.fps:.2f} fps",
            facts.fps <= profile.max_fps + 0.05,
        ),
        _check(
            RESOLUTION,
            f"short edge <= {short_cap}, long edge <= "
            f"{profile.max_long_edge}",
            f"{width}x{height}",
            min(width, height) <= short_cap
            and max(width, height) <= profile.max_long_edge,
        ),
        _check(
            ORIENTATION,
            "no rotation metadata",
            f"{facts.rotation} degrees",
            facts.rotation == 0,
        ),
    ]


def _audio_checks(
    facts: StreamFacts, profile: CompatProfile
) -> list[CheckResult]:
    """Check the audio stream, or warn when there is none."""
    if not facts.has_audio:
        return [
            _check(
                AUDIO_PRESENT,
                "an audio stream",
                "none",
                False,
                Severity.WARNING,
            )
        ]
    rates = " or ".join(str(rate) for rate in profile.sample_rates)
    return [
        _check(
            AUDIO_CODEC, "aac", facts.acodec or "none", facts.acodec == "aac"
        ),
        _check(
            AUDIO_PROFILE,
            "LC",
            facts.aprofile or "none",
            facts.aprofile == "LC",
        ),
        _check(
            AUDIO_CHANNELS, "2 (stereo)", facts.channels, facts.channels == 2
        ),
        _check(
            SAMPLE_RATE,
            rates,
            facts.sample_rate,
            facts.sample_rate in profile.sample_rates,
        ),
    ]


def _extra_checks(
    facts: StreamFacts,
    profile: CompatProfile,
    size_cap_bytes: int | None,
    source_aspect: float | None,
) -> list[CheckResult]:
    """Check faststart, size, aspect ratio and duration."""
    results = [
        _check(
            FASTSTART,
            "moov before mdat",
            {True: "yes", False: "no", None: "unknown"}[facts.faststart],
            facts.faststart is True,
        )
    ]
    if size_cap_bytes is not None:
        results.append(
            _check(
                FILE_SIZE,
                f"<= {size_cap_bytes} bytes",
                f"{facts.size_bytes} bytes",
                facts.size_bytes <= size_cap_bytes,
            )
        )
    if source_aspect:
        ratio = facts.aspect / source_aspect
        results.append(
            _check(
                ASPECT_PRESERVED,
                "same as the source",
                f"{facts.aspect:.3f} vs {source_aspect:.3f}",
                abs(ratio - 1) <= _ASPECT_TOLERANCE,
            )
        )
    if profile.advisory_aspect:
        results.append(
            _check(
                ASPECT_RATIO,
                "9:16 (ideal for Status)",
                f"{facts.aspect:.3f}",
                abs(facts.aspect - profile.advisory_aspect) <= 0.02,
                Severity.WARNING,
            )
        )
    limit = profile.advisory_max_duration_s
    if limit:
        results.append(
            _check(
                DURATION,
                f"<= {limit:g} s",
                f"{facts.duration_s:.1f} s",
                facts.duration_s <= limit,
                Severity.WARNING,
            )
        )
    return results


def check_compliance(
    facts: StreamFacts,
    profile: CompatProfile,
    size_cap_bytes: int | None = None,
    short_cap: int | None = None,
    source_aspect: float | None = None,
) -> ComplianceReport:
    """Compare real file facts with the profile.

    Args:
        facts: What ffprobe reported for the file.
        profile: The settings the file should match.
        size_cap_bytes: Maximum file size, or None for no limit.
        short_cap: Lower limit for the short edge (never above the
            profile maximum).
        source_aspect: Aspect ratio of the original, to prove it was kept.
    """
    cap = profile.max_short_edge
    if short_cap is not None:
        cap = min(short_cap, cap)
    results = _video_checks(facts, profile, cap)
    results += _audio_checks(facts, profile)
    results += _extra_checks(facts, profile, size_cap_bytes, source_aspect)
    return ComplianceReport(tuple(results))
PYEOF

write_file src/yt2wa/domain/decision.py <<'PYEOF'
"""Decide how to turn a download into a shareable file."""

from __future__ import annotations

from collections.abc import Sequence

from yt2wa.domain import compliance as c
from yt2wa.domain.models import (
    Candidate,
    ComplianceReport,
    Method,
    PathDecision,
)

# Failing any of these means the streams themselves must be re-encoded.
_REENCODE = frozenset(
    {
        c.VIDEO_CODEC,
        c.VIDEO_PROFILE,
        c.VIDEO_LEVEL,
        c.PIXEL_FORMAT,
        c.FRAME_RATE,
        c.RESOLUTION,
        c.ORIENTATION,
        c.AUDIO_CODEC,
        c.AUDIO_PROFILE,
        c.AUDIO_CHANNELS,
        c.SAMPLE_RATE,
    }
)

# These can be fixed by copying the streams into a new MP4.
_REMUX = frozenset({c.CONTAINER, c.FASTSTART})


def decide_path(report: ComplianceReport) -> PathDecision:
    """Choose between a lossless remux and a full transcode."""
    failed = [result.name for result in report.errors]
    reencode = [name for name in failed if name in _REENCODE]
    if reencode:
        return PathDecision(Method.TRANSCODE, tuple(reencode))
    if c.FILE_SIZE in failed:
        # Copying the streams cannot make the file smaller.
        return PathDecision(Method.TRANSCODE, ("file is over the size cap",))
    if failed:
        return PathDecision(Method.REMUX, tuple(failed))
    return PathDecision(Method.REMUX, ("already compliant",))


def choose_best_candidate(candidates: Sequence[Candidate]) -> Candidate | None:
    """Return the smallest compliant candidate, or None."""
    compliant = [cand for cand in candidates if cand.report.ok]
    if not compliant:
        return None
    return min(compliant, key=lambda cand: cand.size_bytes)
PYEOF

write_file src/yt2wa/domain/size_guard.py <<'PYEOF'
"""Plan the fallback steps used when a file is too big.

Re-encoding does not guarantee a smaller file, so the ladder lists what to
try, in order, until a result fits the size cap.
"""

from __future__ import annotations

from collections.abc import Mapping

from yt2wa.domain.models import RESOLUTION_RUNGS, LadderStep


def rung_for(short_edge: int) -> int:
    """Return the smallest known resolution that fits the short edge."""
    for rung in RESOLUTION_RUNGS:
        if short_edge <= rung:
            return rung
    return RESOLUTION_RUNGS[-1]


def compute_video_bitrate_k(
    cap_bytes: int,
    duration_s: float,
    audio_k: int,
    safety: float = 0.95,
) -> int:
    """Return the video bitrate (kbit/s) that keeps a file under the cap."""
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    total_bits = cap_bytes * 8 * safety
    audio_bits = audio_k * 1000 * duration_s
    video_bps = (total_bits - audio_bits) / duration_s
    return max(0, int(video_bps // 1000))


def plan_size_ladder(
    start: int,
    floor: int,
    duration_s: float,
    cap_bytes: int | None,
    audio_k: int,
    min_bitrates: Mapping[int, int],
) -> tuple[LadderStep, ...]:
    """List the attempts to make, from best quality to smallest.

    Step 1 is a quality based encode. The next steps aim for a bitrate
    that fits the cap, first at the starting resolution and then one
    resolution rung lower at a time, down to the floor. A rung is skipped
    when the bitrate it would get is too low to look acceptable.
    """
    steps = [LadderStep("crf", start)]
    if cap_bytes is None or duration_s <= 0:
        return tuple(steps)

    lower = [r for r in reversed(RESOLUTION_RUNGS) if floor <= r < start]
    added = False
    for resolution in [start, *lower]:
        safety = 0.85 if added else 0.95
        bitrate = compute_video_bitrate_k(
            cap_bytes, duration_s, audio_k, safety
        )
        minimum = min_bitrates.get(rung_for(resolution), 0)
        if bitrate > 0 and bitrate >= minimum:
            steps.append(LadderStep("bitrate", resolution, bitrate))
            added = True
    return tuple(steps)
PYEOF

write_file src/yt2wa/domain/ffmpeg_args.py <<'PYEOF'
"""Build ffmpeg command lines. Pure: nothing is executed here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.models import LadderStep, Method, StreamFacts
from yt2wa.domain.profile import CompatProfile
from yt2wa.domain.size_guard import rung_for


@dataclass(frozen=True)
class FfmpegPlan:
    """Everything needed to build one ffmpeg command."""

    source: Path
    output: Path
    method: Method
    facts: StreamFacts
    profile: CompatProfile
    short_cap: int
    step: LadderStep | None = None
    threads: int = 0
    ffmpeg_bin: str = "ffmpeg"


def select_h264_level(width: int, height: int, fps: float = 30.0) -> str:
    """Pick an H.264 level that fits the picture size at up to 30 fps."""
    pixels = width * height
    if pixels <= 414_720:  # 854x480 and smaller.
        return "3.0"
    if pixels <= 921_600:  # 1280x720 and smaller.
        return "3.1"
    return "4.0"


def _even(value: float) -> int:
    """Round to the nearest even number, at least 2."""
    return max(2, round(value / 2) * 2)


def target_size(
    facts: StreamFacts, short_cap: int, long_cap: int
) -> tuple[int, int]:
    """Return the output size. Only ever scales down, keeps the aspect."""
    width, height = facts.display_size
    scale = min(
        1.0,
        short_cap / min(width, height),
        long_cap / max(width, height),
    )
    return _even(width * scale), _even(height * scale)


def build_video_filter(
    facts: StreamFacts, size: tuple[int, int], max_fps: float
) -> str | None:
    """Return the ``-vf`` value, or None when no filter is needed."""
    parts = []
    if size != facts.display_size:
        parts.append(f"scale={size[0]}:{size[1]}:flags=lanczos")
    if facts.fps > max_fps + 0.05:
        parts.append(f"fps={max_fps:g}")
    return ",".join(parts) or None


def _video_args(plan: FfmpegPlan) -> list[str]:
    """Return the video encoder arguments."""
    profile = plan.profile
    size = target_size(plan.facts, plan.short_cap, profile.max_long_edge)
    fps_out = min(plan.facts.fps, profile.max_fps)
    args: list[str] = []
    video_filter = build_video_filter(plan.facts, size, profile.max_fps)
    if video_filter:
        args += ["-vf", video_filter]
    args += [
        "-c:v", "libx264",
        "-preset", profile.preset,
        "-profile:v", "high",
        "-level:v", select_h264_level(size[0], size[1], fps_out),
        "-pix_fmt", "yuv420p",
    ]  # fmt: skip
    step = plan.step
    if step is not None and step.kind == "bitrate" and step.video_bitrate_k:
        rate = step.video_bitrate_k
        args += ["-b:v", f"{rate}k", "-maxrate", f"{rate}k"]
        args += ["-bufsize", f"{rate * 2}k"]
    else:
        rung = rung_for(min(size))
        peak = profile.max_video_bitrate_k.get(rung, 5500)
        args += ["-crf", str(profile.crf), "-maxrate", f"{peak}k"]
        args += ["-bufsize", f"{peak * 2}k"]
    return args


def _audio_args(plan: FfmpegPlan) -> list[str]:
    """Return the audio encoder arguments."""
    if not plan.facts.has_audio:
        return ["-an"]
    profile = plan.profile
    rate = 44100 if plan.facts.sample_rate == 44100 else (
        profile.default_sample_rate
    )
    return [
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", f"{profile.audio_bitrate_k}k",
        "-ar", str(rate),
        "-ac", "2",
    ]  # fmt: skip


def build_ffmpeg_args(plan: FfmpegPlan) -> list[str]:
    """Return the full ffmpeg argument list for a plan."""
    args = [
        plan.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-i", str(plan.source),
        "-map", "0:v:0", "-map", "0:a:0?",
    ]  # fmt: skip
    if plan.method is Method.REMUX:
        args += ["-c", "copy"]
    else:
        args += _video_args(plan) + _audio_args(plan)
        if plan.threads > 0:
            args += ["-threads", str(plan.threads)]
    args += ["-movflags", "+faststart", str(plan.output)]
    return args
PYEOF

write_file src/yt2wa/domain/mp4_atoms.py <<'PYEOF'
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
PYEOF


# ---------------------------------------------------------------------------
# Application layer: use cases and strategies
# ---------------------------------------------------------------------------
echo "== Application layer"

write_file src/yt2wa/application/__init__.py <<'PYEOF'
"""Application layer: use cases built on the domain and its ports."""
PYEOF

write_file src/yt2wa/application/dto.py <<'PYEOF'
"""Plain data objects passed between the interface and the use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.models import (
    ComplianceReport,
    Method,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    StreamFacts,
    Target,
)
from yt2wa.domain.profile import CompatProfile


@dataclass(frozen=True)
class ConvertRequest:
    """What the user asked for."""

    url: str
    target: Target
    resolution: int
    output_dir: Path
    max_size_mb: int | None = None
    keep_source: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class JobContext:
    """Everything a strategy needs to do its work."""

    request: ConvertRequest
    ref: SourceRef
    metadata: SourceMetadata
    job_dir: Path
    profile: CompatProfile
    size_cap_bytes: int | None
    on_progress: ProgressCallback


@dataclass(frozen=True)
class StrategyOutput:
    """What a strategy hands back before the file is published."""

    path: Path
    method: Method
    facts: StreamFacts
    report: ComplianceReport | None
    warnings: tuple[str, ...] = ()
    source: Path | None = None


@dataclass(frozen=True)
class VerifyRequest:
    """A request to check an existing file."""

    path: Path
    target: Target


@dataclass(frozen=True)
class VerifyResult:
    """The outcome of checking a file."""

    path: Path
    target: Target
    facts: StreamFacts
    report: ComplianceReport
PYEOF

write_file src/yt2wa/application/strategies/__init__.py <<'PYEOF'
"""Conversion strategies, one per kind of output."""
PYEOF

write_file src/yt2wa/application/strategies/base.py <<'PYEOF'
"""The interface every conversion strategy follows."""

from __future__ import annotations

from abc import ABC, abstractmethod

from yt2wa.application.dto import JobContext, StrategyOutput


class ConversionStrategy(ABC):
    """Turns a request into a file inside the job folder."""

    @abstractmethod
    def run(self, ctx: JobContext) -> StrategyOutput:
        """Download and, if needed, convert the video."""
PYEOF

write_file src/yt2wa/application/strategies/original.py <<'PYEOF'
"""The ``original`` target: keep the video as downloaded."""

from __future__ import annotations

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.formats import build_format_selector
from yt2wa.domain.models import Method, Target
from yt2wa.domain.ports import Downloader, MediaProbe


class OriginalStrategy(ConversionStrategy):
    """Download the best phone-friendly streams without re-encoding."""

    def __init__(self, downloader: Downloader, probe: MediaProbe) -> None:
        self._downloader = downloader
        self._probe = probe

    def run(self, ctx: JobContext) -> StrategyOutput:
        """Download the video and describe what we got."""
        choice = build_format_selector(
            Target.ORIGINAL,
            ctx.request.resolution,
            ctx.profile.max_short_edge,
        )
        path = self._downloader.download(
            ctx.ref, choice, ctx.job_dir / "source", ctx.on_progress
        )
        facts = self._probe.inspect(path)

        # The report is informational only. Nothing is enforced here.
        report = check_compliance(facts, ctx.profile)
        warnings = []
        if not report.ok:
            warnings.append(
                f"Saved as {facts.container.split(',')[0]} with "
                f"{facts.vcodec or 'no'} video. It may not play in every "
                "app and WhatsApp may reject it. Use --target chat to share."
            )
        return StrategyOutput(
            path=path,
            method=Method.DOWNLOAD,
            facts=facts,
            report=report,
            warnings=tuple(warnings),
        )
PYEOF

write_file src/yt2wa/application/strategies/share.py <<'PYEOF'
"""The ``chat`` and ``status`` targets: make a WhatsApp friendly file."""

from __future__ import annotations

from pathlib import Path

from yt2wa.application.dto import JobContext, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain import compliance as c
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.decision import choose_best_candidate, decide_path
from yt2wa.domain.errors import NonCompliantOutputError, SizeCapError
from yt2wa.domain.ffmpeg_args import FfmpegPlan, build_ffmpeg_args
from yt2wa.domain.formats import build_format_selector, short_edge_cap
from yt2wa.domain.models import Candidate, LadderStep, Method, StreamFacts
from yt2wa.domain.ports import Downloader, MediaProbe, Transcoder
from yt2wa.domain.size_guard import plan_size_ladder


class ShareStrategy(ConversionStrategy):
    """Download, then remux or re-encode until the file passes."""

    def __init__(
        self,
        downloader: Downloader,
        probe: MediaProbe,
        transcoder: Transcoder,
        ffmpeg_bin: str = "ffmpeg",
        threads: int = 0,
    ) -> None:
        self._downloader = downloader
        self._probe = probe
        self._transcoder = transcoder
        self._ffmpeg_bin = ffmpeg_bin
        self._threads = threads
        self._attempts = 0

    def run(self, ctx: JobContext) -> StrategyOutput:
        """Produce the smallest compliant file, or raise."""
        request, profile = ctx.request, ctx.profile
        cap = short_edge_cap(
            request.target, request.resolution, profile.max_short_edge
        )
        assert cap is not None  # Shareable targets always have a cap.

        choice = build_format_selector(
            request.target, request.resolution, profile.max_short_edge
        )
        source = self._downloader.download(
            ctx.ref, choice, ctx.job_dir / "source", ctx.on_progress
        )
        facts = self._probe.inspect(source)
        report = check_compliance(
            facts, profile, ctx.size_cap_bytes, short_cap=cap
        )
        decision = decide_path(report)

        out_dir = ctx.job_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[Candidate] = []

        if decision.method is Method.REMUX:
            remux = self._attempt(
                ctx, source, facts, cap, out_dir, Method.REMUX, None
            )
            candidates.append(remux)

        if not any(cand.report.ok for cand in candidates):
            duration = facts.duration_s or ctx.metadata.duration_s
            ladder = plan_size_ladder(
                start=min(cap, facts.short_edge),
                floor=profile.floor_resolution,
                duration_s=duration,
                cap_bytes=ctx.size_cap_bytes,
                audio_k=profile.audio_bitrate_k,
                min_bitrates=profile.min_video_bitrate_k,
            )
            for step in ladder:
                cand = self._attempt(
                    ctx, source, facts, cap, out_dir, Method.TRANSCODE, step
                )
                self._reject_non_size_errors(cand)
                candidates.append(cand)
                if cand.report.ok:
                    break

        best = choose_best_candidate(candidates)
        if best is None:
            raise SizeCapError(
                "Could not fit the video under the size limit.",
                hint=(
                    "Try a lower --resolution, raise --max-size, or send "
                    "the file as a Document."
                ),
            )
        return StrategyOutput(
            path=best.path,
            method=best.method,
            facts=self._probe.inspect(best.path),
            report=best.report,
            warnings=tuple(self._warnings(best, facts, cap)),
            source=source,
        )

    def _attempt(
        self,
        ctx: JobContext,
        source: Path,
        facts: StreamFacts,
        cap: int,
        out_dir: Path,
        method: Method,
        step: LadderStep | None,
    ) -> Candidate:
        """Run ffmpeg once and check the file it produced."""
        self._attempts += 1
        output = out_dir / f"candidate_{self._attempts}.mp4"
        plan = FfmpegPlan(
            source=source,
            output=output,
            method=method,
            facts=facts,
            profile=ctx.profile,
            short_cap=step.resolution if step else cap,
            step=step,
            threads=self._threads,
            ffmpeg_bin=self._ffmpeg_bin,
        )
        self._transcoder.run(
            build_ffmpeg_args(plan),
            facts.duration_s or ctx.metadata.duration_s,
            ctx.on_progress,
        )
        out_facts = self._probe.inspect(output)
        report = check_compliance(
            out_facts,
            ctx.profile,
            ctx.size_cap_bytes,
            short_cap=cap,
            source_aspect=facts.aspect,
        )
        return Candidate(output, report, out_facts.size_bytes, method)

    @staticmethod
    def _reject_non_size_errors(candidate: Candidate) -> None:
        """Stop when a re-encode failed for a reason other than size."""
        problems = [
            f"{r.name} (expected {r.expected}, got {r.actual})"
            for r in candidate.report.errors
            if r.name != c.FILE_SIZE
        ]
        if problems:
            raise NonCompliantOutputError(
                "The converted file fails checks: " + "; ".join(problems),
                hint="Run with -vv and report the ffmpeg command.",
            )

    @staticmethod
    def _warnings(
        best: Candidate, source: StreamFacts, cap: int
    ) -> list[str]:
        """Collect advice and notes about the chosen file."""
        notes = [
            f"{r.name}: expected {r.expected}, got {r.actual}"
            for r in best.report.warnings
        ]
        if source.short_edge < cap:
            notes.append(
                f"The source is only {source.short_edge}p, so it was not "
                "upscaled."
            )
        return notes
PYEOF

write_file src/yt2wa/application/convert.py <<'PYEOF'
"""The main use case: turn a YouTube link into a file."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from yt2wa.application.dto import (
    ConvertRequest,
    JobContext,
    StrategyOutput,
)
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.errors import UnsupportedSourceError
from yt2wa.domain.formats import build_format_selector, short_edge_cap
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    ConversionResult,
    DryRunPlan,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.ports import Downloader, Workspace
from yt2wa.domain.profile import CompatProfile, profile_for
from yt2wa.domain.size_guard import plan_size_ladder
from yt2wa.domain.url_rules import classify_url, sanitize_filename

log = logging.getLogger(__name__)

_MB = 1024 * 1024


class ConvertUseCase:
    """Validate a request, run the right strategy and publish the file."""

    def __init__(
        self,
        downloader: Downloader,
        workspace: Workspace,
        strategies: Mapping[Target, ConversionStrategy],
        profiles: Mapping[str, CompatProfile],
    ) -> None:
        self._downloader = downloader
        self._workspace = workspace
        self._strategies = strategies
        self._profiles = profiles

    def execute(
        self,
        request: ConvertRequest,
        on_progress: ProgressCallback = ignore_progress,
    ) -> ConversionResult | DryRunPlan:
        """Run one conversion and return the published result."""
        ref = classify_url(request.url)
        if ref.kind.value == "unsupported":
            raise UnsupportedSourceError(
                "This link is not a YouTube video or Short.",
                hint="Playlists and community posts are not supported yet.",
            )
        metadata = self._downloader.probe(ref)
        profile = profile_for(request.target, self._profiles)
        cap = self._size_cap(request, profile)
        if request.dry_run:
            return self._dry_run(request, ref, metadata, profile, cap)

        job_dir = self._workspace.new_job_dir()
        log.debug("job folder: %s", job_dir)
        try:
            ctx = JobContext(
                request, ref, metadata, job_dir, profile, cap, on_progress
            )
            output = self._strategies[request.target].run(ctx)
            return self._publish(request, metadata, output)
        finally:
            self._workspace.cleanup(job_dir)

    @staticmethod
    def _size_cap(
        request: ConvertRequest, profile: CompatProfile
    ) -> int | None:
        """Return the size cap in bytes, or None when there is none."""
        if not request.target.is_shareable:
            return None
        megabytes = (
            profile.size_cap_mb
            if request.max_size_mb is None
            else request.max_size_mb
        )
        return megabytes * _MB if megabytes > 0 else None

    def _publish(
        self,
        request: ConvertRequest,
        metadata: SourceMetadata,
        output: StrategyOutput,
    ) -> ConversionResult:
        """Move the finished file into the output folder."""
        edge = output.facts.short_edge
        name = (
            f"{sanitize_filename(metadata.title)}_{edge}p"
            f"{output.path.suffix}"
        )
        final = self._workspace.publish(output.path, request.output_dir, name)

        kept = None
        if request.keep_source and output.source is not None:
            kept = self._workspace.publish(
                output.source,
                request.output_dir,
                f"{final.stem}_source{output.source.suffix}",
            )

        warnings = list(output.warnings)
        wanted = request.resolution
        if wanted != BEST_RESOLUTION and edge < wanted:
            warnings.append(
                f"Output is {edge}p (requested {wanted}p). The source was "
                "smaller or the size cap needed a lower resolution."
            )
        return ConversionResult(
            output=final,
            target=request.target,
            method=output.method,
            title=metadata.title,
            requested_resolution=wanted,
            effective_resolution=edge,
            size_bytes=final.stat().st_size,
            report=output.report,
            warnings=tuple(warnings),
            source_kept=kept,
        )

    @staticmethod
    def _dry_run(
        request: ConvertRequest,
        ref: SourceRef,
        metadata: SourceMetadata,
        profile: CompatProfile,
        cap: int | None,
    ) -> DryRunPlan:
        """Describe the plan without downloading anything."""
        choice = build_format_selector(
            request.target, request.resolution, profile.max_short_edge
        )
        lines = [
            f"Title:       {metadata.title}",
            f"Duration:    {metadata.duration_s:.0f} s",
            f"Source kind: {ref.kind.value}",
            f"Target:      {request.target.value}",
            f"yt-dlp sort: {', '.join(choice.sort)}",
        ]
        if not request.target.is_shareable:
            lines.append("Method:      download as is (no re-encode)")
            return DryRunPlan(tuple(lines))

        edge = short_edge_cap(
            request.target, request.resolution, profile.max_short_edge
        )
        lines.append(
            "Method:      decided after download (remux if the file "
            "already complies, otherwise transcode)"
        )
        lines.append(
            "Size cap:    "
            + ("none" if cap is None else f"{cap / _MB:.0f} MB")
        )
        if edge is not None and metadata.duration_s > 0:
            ladder = plan_size_ladder(
                start=edge,
                floor=profile.floor_resolution,
                duration_s=metadata.duration_s,
                cap_bytes=cap,
                audio_k=profile.audio_bitrate_k,
                min_bitrates=profile.min_video_bitrate_k,
            )
            lines.append("Size ladder (used only if a file is too big):")
            for step in ladder:
                rate = (
                    f"{step.video_bitrate_k} kbit/s"
                    if step.video_bitrate_k
                    else f"crf {profile.crf}"
                )
                lines.append(f"  - {step.resolution}p, {rate}")
        return DryRunPlan(tuple(lines))
PYEOF

write_file src/yt2wa/application/verify.py <<'PYEOF'
"""Check an existing file against the WhatsApp profile."""

from __future__ import annotations

from collections.abc import Mapping

from yt2wa.application.dto import VerifyRequest, VerifyResult
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.ports import MediaProbe
from yt2wa.domain.profile import CompatProfile, profile_for

_MB = 1024 * 1024


class VerifyUseCase:
    """Run the compliance checker on any file."""

    def __init__(
        self, probe: MediaProbe, profiles: Mapping[str, CompatProfile]
    ) -> None:
        self._probe = probe
        self._profiles = profiles

    def execute(self, request: VerifyRequest) -> VerifyResult:
        """Inspect a file and report how well it matches."""
        profile = profile_for(request.target, self._profiles)
        facts = self._probe.inspect(request.path)
        report = check_compliance(
            facts, profile, profile.size_cap_mb * _MB or None
        )
        return VerifyResult(request.path, request.target, facts, report)
PYEOF


# ---------------------------------------------------------------------------
# Infrastructure layer: adapters for yt-dlp, ffmpeg and the file system
# ---------------------------------------------------------------------------
echo "== Infrastructure layer"

write_file src/yt2wa/infrastructure/__init__.py <<'PYEOF'
"""Infrastructure layer: adapters that talk to the outside world."""
PYEOF

write_file src/yt2wa/infrastructure/process.py <<'PYEOF'
"""Small helpers for running external programs safely."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence

from yt2wa.domain.errors import MissingBinaryError


def resolve_binary(name: str) -> str:
    """Return the full path of a program, or raise if it is missing."""
    found = shutil.which(name)
    if found is None:
        raise MissingBinaryError(
            f"'{name}' was not found.",
            hint=(
                "Install ffmpeg (https://ffmpeg.org) or set "
                "YT2WA_FFMPEG_BIN / YT2WA_FFPROBE_BIN."
            ),
        )
    return found


def run_capture(
    args: Sequence[str], timeout: float | None = 60
) -> subprocess.CompletedProcess[str]:
    """Run a program and capture its text output.

    The command is always an argument list, never a shell string.
    """
    try:
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MissingBinaryError(f"'{args[0]}' was not found.") from exc
PYEOF

write_file src/yt2wa/infrastructure/local_workspace.py <<'PYEOF'
"""Scratch folders and safe publishing on the local disk."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path


class LocalWorkspace:
    """Creates job folders and publishes finished files."""

    def __init__(self, work_dir: Path | None = None) -> None:
        self._base = work_dir or Path(tempfile.gettempdir()) / "yt2wa"

    def new_job_dir(self) -> Path:
        """Create a private folder for one run."""
        self._base.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="job-", dir=self._base))

    def publish(self, src: Path, dest_dir: Path, final_name: str) -> Path:
        """Move a file into place. Readers never see a partial file."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique(dest_dir / final_name)
        try:
            os.replace(src, target)
        except OSError:
            # Different drives cannot be renamed. Copy, then rename.
            partial = target.with_name(f".{target.name}.part")
            shutil.copyfile(src, partial)
            os.replace(partial, target)
            src.unlink(missing_ok=True)
        return target

    def cleanup(self, job_dir: Path) -> None:
        """Delete a job folder and everything in it."""
        shutil.rmtree(job_dir, ignore_errors=True)

    def stale_jobs(self, max_age_s: float) -> list[Path]:
        """List job folders older than max_age_s seconds."""
        if not self._base.is_dir():
            return []
        cutoff = time.time() - max_age_s
        return [
            path
            for path in self._base.glob("job-*")
            if path.is_dir() and path.stat().st_mtime < cutoff
        ]

    @staticmethod
    def _unique(path: Path) -> Path:
        """Return a path that does not exist yet (adds -1, -2, ...)."""
        if not path.exists():
            return path
        number = 1
        while True:
            candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
            if not candidate.exists():
                return candidate
            number += 1
PYEOF

write_file src/yt2wa/infrastructure/ffprobe_probe.py <<'PYEOF'
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
PYEOF

write_file src/yt2wa/infrastructure/ffmpeg_transcoder.py <<'PYEOF'
"""Run ffmpeg and report its progress."""

from __future__ import annotations

import re
import subprocess
from collections import deque
from collections.abc import Sequence

from yt2wa.domain.errors import MissingBinaryError, TranscodeError
from yt2wa.domain.models import Progress, ProgressCallback

# Lines ffmpeg prints with "-progress". Anything else is an error message.
_PROGRESS_LINE = re.compile(
    r"^(frame|fps|stream_\d+_\d+_q|bitrate|total_size|out_time_us|"
    r"out_time_ms|out_time|dup_frames|drop_frames|speed|progress)="
)


class FfmpegTranscoder:
    """Transcoder implemented with the ffmpeg program."""

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        """Run ffmpeg. Raises TranscodeError if it fails."""
        try:
            proc = subprocess.Popen(
                list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise MissingBinaryError(f"'{args[0]}' was not found.") from exc

        errors: deque[str] = deque(maxlen=15)
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                if not _PROGRESS_LINE.match(line):
                    errors.append(line)
                elif line.startswith("out_time_us=") and duration_s > 0:
                    self._report(line, duration_s, on_progress)
            code = proc.wait()
        finally:
            # Also runs on Ctrl+C, so ffmpeg never keeps running behind us.
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if code != 0:
            raise TranscodeError(
                f"ffmpeg failed with exit code {code}.",
                hint="\n".join(errors) or None,
            )
        on_progress(Progress("convert", 1.0))

    @staticmethod
    def _report(
        line: str, duration_s: float, on_progress: ProgressCallback
    ) -> None:
        """Turn an out_time_us line into a progress update."""
        try:
            seconds = int(line.split("=", 1)[1]) / 1_000_000
        except ValueError:
            return
        fraction = max(0.0, min(1.0, seconds / duration_s))
        on_progress(Progress("convert", fraction))
PYEOF

write_file src/yt2wa/infrastructure/ytdlp_downloader.py <<'PYEOF'
"""Download videos with the yt-dlp library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yt2wa.domain.errors import (
    AgeRestrictedError,
    DomainError,
    GeoBlockedError,
    MissingBinaryError,
    NetworkError,
    PrivateVideoError,
    RemovedVideoError,
    SourceUnavailableError,
)
from yt2wa.domain.models import (
    FormatChoice,
    Progress,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
)

_COOKIE_HINT = "Provide a cookies file with YT2WA_COOKIES_FILE."


def classify_download_error(message: str) -> DomainError:
    """Turn a yt-dlp error message into one of our own errors."""
    text = message.lower()
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    if "private video" in text:
        return PrivateVideoError("This video is private.")
    if "confirm your age" in text or "age-restricted" in text:
        return AgeRestrictedError(
            "This video is age restricted.", hint=_COOKIE_HINT
        )
    if "country" in text and ("not available" in text or "blocked" in text):
        return GeoBlockedError("This video is blocked in your country.")
    if any(
        phrase in text
        for phrase in (
            "video unavailable",
            "has been removed",
            "no longer available",
            "has been terminated",
        )
    ):
        return RemovedVideoError("This video is unavailable or was removed.")
    if "sign in to confirm" in text:
        return SourceUnavailableError(
            "YouTube asked for a sign-in check.", hint=_COOKIE_HINT
        )
    if any(
        phrase in text
        for phrase in (
            "http error 429",
            "timed out",
            "temporary failure",
            "name or service not known",
            "getaddrinfo",
            "connection",
            "urlopen error",
            "unable to download",
        )
    ):
        return NetworkError(
            "The download failed because of a network problem.",
            hint="Check your connection and try again.",
        )
    return SourceUnavailableError(first_line or "The video is unavailable.")


def _load_yt_dlp() -> Any:
    """Import yt-dlp when it is first needed."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise MissingBinaryError(
            "yt-dlp is not installed.", hint="Run: pip install yt-dlp"
        ) from exc
    return yt_dlp


class YtDlpDownloader:
    """Downloader implemented with the yt-dlp Python API."""

    def __init__(
        self, retries: int = 3, cookies_file: Path | None = None
    ) -> None:
        self._retries = retries
        self._cookies_file = cookies_file

    def probe(self, ref: SourceRef) -> SourceMetadata:
        """Fetch metadata without downloading the video."""
        yt_dlp = _load_yt_dlp()
        options = self._base_options() | {"skip_download": True}
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(ref.url, download=False)
        except (yt_dlp.utils.YoutubeDLError, OSError) as exc:
            raise classify_download_error(str(exc)) from exc
        return SourceMetadata(
            video_id=str(info.get("id", ref.video_id or "")),
            title=str(info.get("title") or info.get("id") or "video"),
            duration_s=float(info.get("duration") or 0),
            uploader=info.get("uploader"),
        )

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        """Download the chosen streams and return the file path."""
        yt_dlp = _load_yt_dlp()
        dest_dir.mkdir(parents=True, exist_ok=True)

        def hook(data: dict[str, Any]) -> None:
            if data.get("status") != "downloading":
                return
            total = data.get("total_bytes") or data.get(
                "total_bytes_estimate"
            )
            done = data.get("downloaded_bytes") or 0
            if total:
                on_progress(Progress("download", min(1.0, done / total)))

        options = self._base_options() | {
            "format": choice.selector,
            "format_sort": list(choice.sort),
            "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "progress_hooks": [hook],
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(ref.url, download=True)
                downloads = info.get("requested_downloads") or []
                if downloads and downloads[0].get("filepath"):
                    path = Path(downloads[0]["filepath"])
                else:
                    path = Path(ydl.prepare_filename(info))
        except (yt_dlp.utils.YoutubeDLError, OSError) as exc:
            raise classify_download_error(str(exc)) from exc
        if not path.exists():
            raise SourceUnavailableError("The download finished but no file.")
        on_progress(Progress("download", 1.0))
        return path

    def _base_options(self) -> dict[str, Any]:
        """Return the yt-dlp options shared by every call."""
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": self._retries,
            "fragment_retries": self._retries,
            "socket_timeout": 30,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)
        return options
PYEOF


# ---------------------------------------------------------------------------
# Bootstrap: settings, logging and the composition root
# ---------------------------------------------------------------------------
echo "== Bootstrap"

write_file src/yt2wa/bootstrap/__init__.py <<'PYEOF'
"""Bootstrap: configuration and wiring of the whole application."""
PYEOF

write_file src/yt2wa/bootstrap/settings.py <<'PYEOF'
"""Settings read from environment variables (12-factor config)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.formats import parse_resolution
from yt2wa.domain.models import Target

PREFIX = "YT2WA_"


def load_dotenv(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file (development only)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    """Read an integer setting."""
    raw = env.get(PREFIX + key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{PREFIX}{key} must be a number.") from exc


def _path(env: Mapping[str, str], key: str) -> Path | None:
    """Read an optional path setting."""
    raw = env.get(PREFIX + key)
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class Settings:
    """Every configurable value, with its default."""

    default_target: Target = Target.CHAT
    default_resolution: int = 480
    max_size_mb: int | None = None
    floor_resolution: int | None = None
    profile_file: Path | None = None
    work_dir: Path | None = None
    output_dir: Path = Path("out")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    ffmpeg_threads: int = 0
    net_retries: int = 3
    cookies_file: Path | None = None
    log_level: str = "INFO"
    log_format: str = "text"

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        dotenv: Path | None = None,
    ) -> Settings:
        """Build settings. Real environment variables beat .env."""
        env: dict[str, str] = {}
        env.update(load_dotenv(dotenv or Path(".env")))
        env.update(environ if environ is not None else os.environ)

        try:
            target = Target(env.get(PREFIX + "DEFAULT_TARGET", "chat"))
        except ValueError as exc:
            raise ConfigError(
                f"{PREFIX}DEFAULT_TARGET must be original, chat or status."
            ) from exc
        resolution = parse_resolution(
            env.get(PREFIX + "DEFAULT_RESOLUTION", "480")
        )
        log_format = env.get(PREFIX + "LOG_FORMAT", "text")
        if log_format not in ("text", "json"):
            raise ConfigError(f"{PREFIX}LOG_FORMAT must be text or json.")

        size = env.get(PREFIX + "MAX_SIZE_MB")
        floor = env.get(PREFIX + "MIN_RESOLUTION_FLOOR")
        return cls(
            default_target=target,
            default_resolution=resolution,
            max_size_mb=_int(env, "MAX_SIZE_MB", 0) if size else None,
            floor_resolution=(
                _int(env, "MIN_RESOLUTION_FLOOR", 0) if floor else None
            ),
            profile_file=_path(env, "PROFILE_FILE"),
            work_dir=_path(env, "WORK_DIR"),
            output_dir=_path(env, "OUTPUT_DIR") or Path("out"),
            ffmpeg_bin=env.get(PREFIX + "FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=env.get(PREFIX + "FFPROBE_BIN", "ffprobe"),
            ffmpeg_threads=_int(env, "FFMPEG_THREADS", 0),
            net_retries=_int(env, "NET_RETRIES", 3),
            cookies_file=_path(env, "COOKIES_FILE"),
            log_level=env.get(PREFIX + "LOG_LEVEL", "INFO").upper(),
            log_format=log_format,
        )
PYEOF

write_file src/yt2wa/bootstrap/profiles.py <<'PYEOF'
"""Load compatibility profiles and apply environment overrides."""

from __future__ import annotations

import tomllib
from dataclasses import replace
from typing import Any

from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import ConfigError
from yt2wa.domain.profile import (
    DEFAULT_PROFILES,
    CompatProfile,
    profile_from_mapping,
)


def load_profiles(settings: Settings) -> dict[str, CompatProfile]:
    """Return the chat and status profiles."""
    profiles = dict(DEFAULT_PROFILES)
    if settings.profile_file is not None:
        try:
            with settings.profile_file.open("rb") as handle:
                data = tomllib.load(handle)
        except OSError as exc:
            raise ConfigError(
                f"Cannot read profile file {settings.profile_file}."
            ) from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in profile file: {exc}") from exc
        unknown = sorted(set(data) - {"chat", "status"})
        if unknown:
            raise ConfigError(f"Unknown profile(s): {', '.join(unknown)}.")
        # Status starts from chat, so chat changes carry over.
        chat = profile_from_mapping("chat", data.get("chat", {}))
        profiles["chat"] = chat
        profiles["status"] = profile_from_mapping(
            "status",
            {**_status_defaults(), **data.get("status", {})},
            base=chat,
        )

    overrides: dict[str, Any] = {}
    if settings.max_size_mb is not None:
        overrides["size_cap_mb"] = settings.max_size_mb
    if settings.floor_resolution is not None:
        overrides["floor_resolution"] = settings.floor_resolution
    if overrides:
        profiles = {
            name: replace(profile, **overrides)
            for name, profile in profiles.items()
        }
    return profiles


def _status_defaults() -> dict[str, float]:
    """Return the advisory settings every status profile starts with."""
    status = DEFAULT_PROFILES["status"]
    return {
        "advisory_aspect": status.advisory_aspect or 0.0,
        "advisory_max_duration_s": status.advisory_max_duration_s or 0.0,
    }
PYEOF

write_file src/yt2wa/bootstrap/logging_setup.py <<'PYEOF'
"""Logging goes to stderr as an event stream."""

from __future__ import annotations

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a JSON string."""
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging(level: str, log_format: str) -> None:
    """Send logs to stderr in text or JSON form."""
    handler = logging.StreamHandler(sys.stderr)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level, logging.INFO))
PYEOF

write_file src/yt2wa/bootstrap/container.py <<'PYEOF'
"""The composition root: the one place that creates and wires objects."""

from __future__ import annotations

from dataclasses import dataclass

from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.application.verify import VerifyUseCase
from yt2wa.bootstrap.profiles import load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.models import Target
from yt2wa.domain.profile import CompatProfile
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe
from yt2wa.infrastructure.local_workspace import LocalWorkspace
from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader


@dataclass(frozen=True)
class Container:
    """The wired application."""

    settings: Settings
    profiles: dict[str, CompatProfile]
    workspace: LocalWorkspace
    convert: ConvertUseCase
    verify: VerifyUseCase


def build_container(settings: Settings) -> Container:
    """Create every adapter and use case from the settings."""
    profiles = load_profiles(settings)
    downloader = YtDlpDownloader(
        retries=settings.net_retries, cookies_file=settings.cookies_file
    )
    probe = FfprobeMediaProbe(settings.ffprobe_bin)
    transcoder = FfmpegTranscoder()
    workspace = LocalWorkspace(settings.work_dir)

    share = ShareStrategy(
        downloader,
        probe,
        transcoder,
        ffmpeg_bin=settings.ffmpeg_bin,
        threads=settings.ffmpeg_threads,
    )
    strategies = {
        Target.ORIGINAL: OriginalStrategy(downloader, probe),
        Target.CHAT: share,
        Target.STATUS: share,
    }
    return Container(
        settings=settings,
        profiles=profiles,
        workspace=workspace,
        convert=ConvertUseCase(downloader, workspace, strategies, profiles),
        verify=VerifyUseCase(probe, profiles),
    )
PYEOF

write_file src/yt2wa/bootstrap/doctor.py <<'PYEOF'
"""Environment checks for the ``doctor`` command."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date

from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import MissingBinaryError
from yt2wa.infrastructure.process import resolve_binary, run_capture

MIN_FFMPEG_MAJOR = 4
MAX_YTDLP_AGE_DAYS = 180


@dataclass(frozen=True)
class DoctorCheck:
    """The result of one environment check."""

    name: str
    ok: bool
    detail: str


def _check_python() -> DoctorCheck:
    """Check the Python version."""
    version = ".".join(str(part) for part in sys.version_info[:3])
    return DoctorCheck("python", sys.version_info >= (3, 11), version)


def _check_binary(label: str, name: str) -> DoctorCheck:
    """Check that ffmpeg or ffprobe exists and is recent enough."""
    try:
        path = resolve_binary(name)
        output = run_capture([path, "-version"], timeout=15).stdout
    except MissingBinaryError as exc:
        return DoctorCheck(label, False, exc.message)
    first = output.splitlines()[0] if output else "unknown version"
    match = re.search(r"version n?(\d+)", first)
    if match and int(match.group(1)) < MIN_FFMPEG_MAJOR:
        return DoctorCheck(label, False, f"{first} (need >= 4)")
    return DoctorCheck(label, True, first)


def _check_encoders(ffmpeg_bin: str) -> DoctorCheck:
    """Check that ffmpeg can encode H.264 and AAC."""
    try:
        output = run_capture(
            [resolve_binary(ffmpeg_bin), "-hide_banner", "-encoders"],
            timeout=15,
        ).stdout
    except MissingBinaryError as exc:
        return DoctorCheck("encoders", False, exc.message)
    missing = [
        name for name in ("libx264", " aac ") if name not in output
    ]
    if missing:
        return DoctorCheck(
            "encoders", False, f"missing: {', '.join(missing).strip()}"
        )
    return DoctorCheck("encoders", True, "libx264 and aac available")


def _check_ytdlp() -> DoctorCheck:
    """Check that yt-dlp is installed and not too old."""
    try:
        from yt_dlp.version import __version__
    except ImportError:
        return DoctorCheck("yt-dlp", False, "not installed")
    try:
        year, month, day = (int(p) for p in __version__.split(".")[:3])
        age = (date.today() - date(year, month, day)).days
    except ValueError:
        return DoctorCheck("yt-dlp", True, __version__)
    note = " (old, consider upgrading)" if age > MAX_YTDLP_AGE_DAYS else ""
    return DoctorCheck("yt-dlp", True, f"{__version__}, {age} days old{note}")


def run_doctor(settings: Settings) -> list[DoctorCheck]:
    """Run every environment check."""
    return [
        _check_python(),
        _check_binary("ffmpeg", settings.ffmpeg_bin),
        _check_binary("ffprobe", settings.ffprobe_bin),
        _check_encoders(settings.ffmpeg_bin),
        _check_ytdlp(),
    ]
PYEOF

# ---------------------------------------------------------------------------
# Interface: the command line and its presenters (procedural shell)
# ---------------------------------------------------------------------------
echo "== Interface layer"

write_file src/yt2wa/interface/__init__.py <<'PYEOF'
"""Interface layer: the command line and how results are shown."""
PYEOF

write_file src/yt2wa/interface/exit_codes.py <<'PYEOF'
"""Exit codes and the mapping from errors to codes."""

from __future__ import annotations

from enum import IntEnum

from yt2wa.domain.errors import (
    ConstraintError,
    DependencyError,
    DomainError,
    NetworkError,
    SourceUnavailableError,
    TranscodeError,
    UnsupportedSourceError,
    UsageError,
)


class ExitCode(IntEnum):
    """Process exit codes."""

    OK = 0
    GENERAL = 1
    USAGE = 2
    UNSUPPORTED = 3
    UNAVAILABLE = 4
    NETWORK = 5
    DEPENDENCY = 6
    TRANSCODE = 7
    CONSTRAINT = 8
    INTERRUPTED = 130


_CODES: tuple[tuple[type[DomainError], ExitCode], ...] = (
    (UsageError, ExitCode.USAGE),
    (UnsupportedSourceError, ExitCode.UNSUPPORTED),
    (SourceUnavailableError, ExitCode.UNAVAILABLE),
    (NetworkError, ExitCode.NETWORK),
    (DependencyError, ExitCode.DEPENDENCY),
    (TranscodeError, ExitCode.TRANSCODE),
    (ConstraintError, ExitCode.CONSTRAINT),
)


def map_exception_to_exit_code(exc: Exception) -> ExitCode:
    """Return the exit code for an error."""
    for error_type, code in _CODES:
        if isinstance(exc, error_type):
            return code
    return ExitCode.GENERAL
PYEOF

write_file src/yt2wa/interface/progress.py <<'PYEOF'
"""Show progress on the terminal (stderr)."""

from __future__ import annotations

import sys
from typing import TextIO

from yt2wa.domain.models import Progress


class ConsoleProgress:
    """A progress callback that draws a simple line on stderr."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stderr
        self._tty = self._stream.isatty()
        self._stage: str | None = None
        self._dirty = False

    def __call__(self, progress: Progress) -> None:
        """Handle one progress update."""
        if progress.stage != self._stage:
            self.finish()
            if not self._tty:
                self._stream.write(f"  {progress.stage}...\n")
            self._stage = progress.stage
        if self._tty and progress.fraction is not None:
            percent = progress.fraction * 100
            self._stream.write(f"\r  {progress.stage:<9} {percent:5.1f}%")
            self._stream.flush()
            self._dirty = True

    def finish(self) -> None:
        """End the current line, if we were drawing on it."""
        if self._dirty:
            self._stream.write("\n")
            self._stream.flush()
            self._dirty = False
PYEOF

write_file src/yt2wa/interface/presenters.py <<'PYEOF'
"""Turn results and errors into text for people or machines."""

from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from yt2wa.application.dto import VerifyResult
from yt2wa.bootstrap.doctor import DoctorCheck
from yt2wa.domain.errors import DomainError
from yt2wa.domain.models import (
    ComplianceReport,
    ConversionResult,
    DryRunPlan,
    Method,
    Severity,
    Target,
)

_METHOD_TEXT = {
    Method.DOWNLOAD: "downloaded as is, no re-encode",
    Method.REMUX: "remuxed, no re-encode",
    Method.TRANSCODE: "re-encoded",
}


def format_size(size_bytes: int) -> str:
    """Return a size such as '7.9 MB'."""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def to_jsonable(value: Any) -> Any:
    """Convert results into plain data that json can write."""
    if isinstance(value, ComplianceReport):
        return {
            "ok": value.ok,
            "checks": [to_jsonable(r) for r in value.results],
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_jsonable(getattr(value, f.name)) for f in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


class ConsolePresenter:
    """Print for people. The result path goes to stdout, the rest to stderr."""

    def __init__(
        self,
        quiet: bool = False,
        out: TextIO | None = None,
        err: TextIO | None = None,
    ) -> None:
        self._quiet = quiet
        self._out = out or sys.stdout
        self._err = err or sys.stderr

    def _say(self, tag: str, text: str) -> None:
        print(f"[{tag}] {text}", file=self._err)

    def result(self, result: ConversionResult, show_report: bool) -> None:
        """Show a finished conversion."""
        print(result.output, file=self._out)
        if self._quiet:
            return
        self._say(
            "ok",
            f"Saved {result.output} ({format_size(result.size_bytes)}, "
            f"{_METHOD_TEXT[result.method]})",
        )
        if result.report is not None and result.target.is_shareable:
            total = len(result.report.results)
            passed = sum(1 for r in result.report.results if r.passed)
            self._say("ok", f"Compliance: {passed}/{total} checks passed")
        for warning in result.warnings:
            self._say("warn", warning)
        if result.target.is_shareable:
            self._say(
                "info",
                "WhatsApp may still re-compress media. Send the file as a "
                "Document to keep its quality.",
            )
        if result.source_kept:
            self._say("info", f"Source kept at {result.source_kept}")
        if show_report and result.report is not None:
            self._report(result.report)

    def dry_run(self, plan: DryRunPlan) -> None:
        """Show what a run would do."""
        for line in plan.lines:
            print(line, file=self._out)

    def verify(self, result: VerifyResult) -> None:
        """Show the result of checking a file."""
        self._report(result.report)
        verdict = "matches" if result.report.ok else "does NOT match"
        self._say(
            "ok" if result.report.ok else "fail",
            f"{result.path.name} {verdict} the {result.target.value} "
            "profile.",
        )

    def doctor(self, checks: list[DoctorCheck]) -> None:
        """Show the environment checks."""
        for check in checks:
            tag = "ok" if check.ok else "fail"
            print(f"[{tag}] {check.name}: {check.detail}", file=self._err)

    def cleaned(self, paths: list[Path]) -> None:
        """Show which folders were removed."""
        self._say("ok", f"Removed {len(paths)} old job folder(s).")

    def error(self, exc: DomainError) -> None:
        """Show an error and its hint."""
        self._say("error", exc.message)
        if exc.hint:
            self._say("hint", exc.hint)

    def interrupted(self) -> None:
        """Show that the user stopped the run."""
        self._say("error", "Interrupted.")

    def _report(self, report: ComplianceReport) -> None:
        """Print every check on its own line."""
        for r in report.results:
            if r.passed:
                label = "PASS"
            elif r.severity is Severity.WARNING:
                label = "WARN"
            else:
                label = "FAIL"
            detail = r.actual if r.passed else (
                f"{r.actual} (expected {r.expected})"
            )
            print(f"  {label}  {r.name}: {detail}", file=self._err)


class JsonPresenter:
    """Print machine readable JSON on stdout."""

    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out or sys.stdout

    def _dump(self, payload: Any) -> None:
        print(json.dumps(to_jsonable(payload), indent=2), file=self._out)

    def result(self, result: ConversionResult, show_report: bool) -> None:
        """Write a finished conversion."""
        self._dump(result)

    def dry_run(self, plan: DryRunPlan) -> None:
        """Write the dry run plan."""
        self._dump({"plan": plan.lines})

    def verify(self, result: VerifyResult) -> None:
        """Write the result of checking a file."""
        self._dump(result)

    def doctor(self, checks: list[DoctorCheck]) -> None:
        """Write the environment checks."""
        self._dump({"checks": checks})

    def cleaned(self, paths: list[Path]) -> None:
        """Write which folders were removed."""
        self._dump({"removed": paths})

    def error(self, exc: DomainError) -> None:
        """Write an error."""
        self._dump({"error": exc.message, "hint": exc.hint})

    def interrupted(self) -> None:
        """Write that the run was interrupted."""
        self._dump({"error": "interrupted"})


Presenter = ConsolePresenter | JsonPresenter

__all__ = [
    "ConsolePresenter",
    "JsonPresenter",
    "Presenter",
    "Target",
    "format_size",
    "to_jsonable",
]
PYEOF

write_file src/yt2wa/interface/cli.py <<'PYEOF'
"""The command line: parse arguments, wire the app, run, map exit codes."""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from yt2wa import __version__
from yt2wa.application.dto import ConvertRequest, VerifyRequest
from yt2wa.bootstrap.container import Container, build_container
from yt2wa.bootstrap.doctor import run_doctor
from yt2wa.bootstrap.logging_setup import configure_logging
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import DomainError, UsageError
from yt2wa.domain.formats import parse_resolution
from yt2wa.domain.models import DryRunPlan, Target, ignore_progress
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code
from yt2wa.interface.presenters import (
    ConsolePresenter,
    JsonPresenter,
    Presenter,
)
from yt2wa.interface.progress import ConsoleProgress

COMMANDS = ("convert", "verify", "doctor", "clean")

NOTICE = (
    "Legal note: downloading may break YouTube's Terms of Service or "
    "copyright law. Use this tool only for content you own, have permission "
    "to use, or that is licensed for reuse."
)


def _resolution_type(text: str) -> int:
    """Argparse type for --resolution."""
    try:
        return parse_resolution(text)
    except UsageError as exc:
        raise argparse.ArgumentTypeError(exc.message) from exc


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("-v", "--verbose", action="count", default=0)
    common.add_argument("-q", "--quiet", action="store_true")

    parser = argparse.ArgumentParser(
        prog="yt2wa",
        description="Download YouTube videos and make them WhatsApp ready.",
        epilog=NOTICE,
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser(
        "convert", parents=[common], help="download and convert a video"
    )
    convert.add_argument("url", help="YouTube video or Short link")
    convert.add_argument(
        "-t",
        "--target",
        choices=[t.value for t in Target],
        help="output intent (default: chat)",
    )
    convert.add_argument(
        "--keep-original",
        dest="target",
        action="store_const",
        const=Target.ORIGINAL.value,
        help="same as --target original",
    )
    convert.add_argument(
        "-r",
        "--resolution",
        type=_resolution_type,
        metavar="{144,240,360,480,720,1080,best}",
        help="short edge size (default: 480)",
    )
    convert.add_argument("-o", "--output-dir", type=Path)
    convert.add_argument(
        "--max-size",
        type=int,
        metavar="MB",
        help="size cap for chat/status (0 means no cap)",
    )
    convert.add_argument("--report", action="store_true")
    convert.add_argument("--keep-source", action="store_true")
    convert.add_argument("--dry-run", action="store_true")

    verify = sub.add_parser(
        "verify", parents=[common], help="check a file against the profile"
    )
    verify.add_argument("file", type=Path)
    verify.add_argument(
        "-t",
        "--target",
        choices=[Target.CHAT.value, Target.STATUS.value],
        default=Target.CHAT.value,
    )

    sub.add_parser(
        "doctor", parents=[common], help="check ffmpeg, ffprobe and yt-dlp"
    )

    clean = sub.add_parser(
        "clean", parents=[common], help="remove old scratch folders"
    )
    clean.add_argument("--hours", type=float, default=24.0)
    return parser


def with_default_command(argv: Sequence[str]) -> list[str]:
    """Insert 'convert' when the user typed only a link and options."""
    args = list(argv)
    if args and args[0] not in COMMANDS and args[0] not in (
        "-h",
        "--help",
        "--version",
    ):
        return ["convert", *args]
    return args


def _convert(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the convert command."""
    settings = container.settings
    request = ConvertRequest(
        url=args.url,
        target=Target(args.target or settings.default_target),
        resolution=(
            settings.default_resolution
            if args.resolution is None
            else args.resolution
        ),
        output_dir=args.output_dir or settings.output_dir,
        max_size_mb=args.max_size,
        keep_source=args.keep_source,
        dry_run=args.dry_run,
    )
    quiet = args.json or args.quiet
    progress = ignore_progress if quiet else ConsoleProgress()
    try:
        outcome = container.convert.execute(request, progress)
    finally:
        if isinstance(progress, ConsoleProgress):
            progress.finish()
    if isinstance(outcome, DryRunPlan):
        presenter.dry_run(outcome)
    else:
        presenter.result(outcome, args.report)
    return ExitCode.OK


def _verify(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the verify command."""
    result = container.verify.execute(
        VerifyRequest(args.file, Target(args.target))
    )
    presenter.verify(result)
    return ExitCode.OK if result.report.ok else ExitCode.CONSTRAINT


def _doctor(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the doctor command."""
    checks = run_doctor(container.settings)
    presenter.doctor(checks)
    return ExitCode.OK if all(c.ok for c in checks) else ExitCode.DEPENDENCY


def _clean(
    args: argparse.Namespace, container: Container, presenter: Presenter
) -> ExitCode:
    """Handle the clean command."""
    old = container.workspace.stale_jobs(args.hours * 3600)
    for path in old:
        container.workspace.cleanup(path)
    presenter.cleaned(old)
    return ExitCode.OK


_HANDLERS = {
    "convert": _convert,
    "verify": _verify,
    "doctor": _doctor,
    "clean": _clean,
}


def _raise_interrupt(signum: int, frame: FrameType | None) -> None:
    """Turn SIGTERM into Ctrl+C so cleanup code runs."""
    raise KeyboardInterrupt


def _log_level(args: argparse.Namespace, settings: Settings) -> str:
    """Pick the log level from flags and settings."""
    if args.quiet:
        return "ERROR"
    if args.verbose:
        return "DEBUG"
    return settings.log_level


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return the exit code."""
    raw = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(with_default_command(raw))
    presenter: Presenter = (
        JsonPresenter() if args.json else ConsolePresenter(quiet=args.quiet)
    )
    try:
        settings = Settings.from_env()
        configure_logging(_log_level(args, settings), settings.log_format)
        container = build_container(settings)
        signal.signal(signal.SIGTERM, _raise_interrupt)
        code = _HANDLERS[args.command](args, container, presenter)
    except DomainError as exc:
        presenter.error(exc)
        return int(map_exception_to_exit_code(exc))
    except KeyboardInterrupt:
        presenter.interrupted()
        return int(ExitCode.INTERRUPTED)
    return int(code)
PYEOF


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
echo "== Tests"

write_file tests/__init__.py </dev/null
write_file tests/unit/__init__.py </dev/null
write_file tests/unit/domain/__init__.py </dev/null
write_file tests/unit/application/__init__.py </dev/null
write_file tests/integration/__init__.py </dev/null
write_file tests/contract/__init__.py </dev/null
write_file tests/e2e/__init__.py </dev/null
write_file tests/fakes/__init__.py </dev/null

write_file tests/fakes/factories.py <<'PYEOF'
"""Helpers that build test data."""

from __future__ import annotations

from dataclasses import replace

from yt2wa.domain.models import StreamFacts

MP4 = "mov,mp4,m4a,3gp,3g2,mj2"


def make_facts(**overrides: object) -> StreamFacts:
    """Return facts for a file that already matches the profile."""
    base = StreamFacts(
        container=MP4,
        vcodec="h264",
        vprofile="High",
        vlevel=31,
        pix_fmt="yuv420p",
        width=854,
        height=480,
        fps=30.0,
        rotation=0,
        acodec="aac",
        aprofile="LC",
        channels=2,
        sample_rate=48000,
        size_bytes=5 * 1024 * 1024,
        duration_s=60.0,
        faststart=True,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]
PYEOF

write_file tests/fakes/fakes.py <<'PYEOF'
"""Fake adapters used by the application tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fakes.factories import make_facts
from yt2wa.domain.models import (
    FormatChoice,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    StreamFacts,
)


class FakeDownloader:
    """Pretends to download a video."""

    def __init__(self, duration_s: float = 60.0) -> None:
        self._duration = duration_s
        self.choices: list[FormatChoice] = []

    def probe(self, ref: SourceRef) -> SourceMetadata:
        return SourceMetadata("abcdefghijk", "My Clip", self._duration)

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        self.choices.append(choice)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / "source.mkv"
        path.write_bytes(b"source")
        return path


class FakeProbe:
    """Returns the source facts, or sane facts for candidate files."""

    def __init__(self, source: StreamFacts) -> None:
        self._source = source

    def inspect(self, path: Path) -> StreamFacts:
        if path.name.startswith("candidate"):
            return make_facts(size_bytes=path.stat().st_size)
        return self._source


class FakeTranscoder:
    """Writes output files of the sizes it was given, in order."""

    def __init__(self, sizes: Sequence[int]) -> None:
        self._sizes = list(sizes)
        self.calls: list[list[str]] = []

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        self.calls.append(list(args))
        Path(args[-1]).write_bytes(b"0" * self._sizes.pop(0))
PYEOF

write_file tests/unit/domain/test_url_rules.py <<'PYEOF'
import pytest

from yt2wa.domain.models import SourceKind
from yt2wa.domain.url_rules import classify_url, sanitize_filename


@pytest.mark.parametrize(
    ("url", "kind", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", SourceKind.VIDEO,
         "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", SourceKind.VIDEO, "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abcdefghijk", SourceKind.SHORT,
         "abcdefghijk"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1",
         SourceKind.VIDEO, "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", SourceKind.VIDEO,
         "dQw4w9WgXcQ"),
    ],
)
def test_supported_links(url, kind, video_id):
    ref = classify_url(url)
    assert ref.kind is kind
    assert ref.video_id == video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/post/UgkxABC",
        "https://www.youtube.com/@channel/community",
        "https://www.youtube.com/watch",
        "https://vimeo.com/12345",
        "not a url",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_unsupported_links(url):
    assert classify_url(url).kind is SourceKind.UNSUPPORTED


def test_sanitize_filename_removes_unsafe_characters():
    assert sanitize_filename('a/b:c*"d?  e') == "abcd_e"


def test_sanitize_filename_falls_back_for_empty_names():
    assert sanitize_filename("///") == "video"
    assert sanitize_filename("CON") == "video"


def test_sanitize_filename_limits_length():
    assert len(sanitize_filename("x" * 500)) <= 80
PYEOF

write_file tests/unit/domain/test_formats.py <<'PYEOF'
import pytest

from yt2wa.domain.errors import UsageError
from yt2wa.domain.formats import (
    build_format_selector,
    parse_resolution,
    short_edge_cap,
)
from yt2wa.domain.models import BEST_RESOLUTION, Target


@pytest.mark.parametrize(
    ("text", "expected"),
    [("480", 480), ("720p", 720), (" BEST ", BEST_RESOLUTION)],
)
def test_parse_resolution(text, expected):
    assert parse_resolution(text) == expected


@pytest.mark.parametrize("text", ["420", "760", "abc", "", "4k"])
def test_parse_resolution_rejects_unknown_values(text):
    with pytest.raises(UsageError):
        parse_resolution(text)


def test_original_best_has_no_cap():
    assert short_edge_cap(Target.ORIGINAL, BEST_RESOLUTION, 1080) is None


def test_shareable_best_is_clamped_to_profile_maximum():
    assert short_edge_cap(Target.CHAT, BEST_RESOLUTION, 1080) == 1080


def test_cap_never_exceeds_profile_maximum():
    assert short_edge_cap(Target.STATUS, 1080, 720) == 720


def test_selector_prefers_h264_and_aac_within_the_cap():
    choice = build_format_selector(Target.CHAT, 480)
    assert choice.sort == ("res:480", "vcodec:h264", "acodec:aac")
    assert choice.selector == "bv*+ba/b"


def test_original_best_selector_has_no_limit():
    choice = build_format_selector(Target.ORIGINAL, BEST_RESOLUTION)
    assert choice.sort[0] == "res"
PYEOF

write_file tests/unit/domain/test_compliance.py <<'PYEOF'
import pytest

from fakes.factories import make_facts
from yt2wa.domain import compliance as c
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.profile import DEFAULT_CHAT, DEFAULT_STATUS

MB = 1024 * 1024


def failed_names(report):
    return {r.name for r in report.errors}


def test_compliant_file_passes_every_check():
    report = check_compliance(make_facts(), DEFAULT_CHAT, 16 * MB)
    assert report.ok
    assert not report.failed


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"vcodec": "vp9"}, c.VIDEO_CODEC),
        ({"pix_fmt": "yuv444p"}, c.PIXEL_FORMAT),
        ({"fps": 60.0}, c.FRAME_RATE),
        ({"acodec": "opus"}, c.AUDIO_CODEC),
        ({"aprofile": "HE-AAC"}, c.AUDIO_PROFILE),
        ({"channels": 1}, c.AUDIO_CHANNELS),
        ({"sample_rate": 22050}, c.SAMPLE_RATE),
        ({"faststart": False}, c.FASTSTART),
        ({"faststart": None}, c.FASTSTART),
        ({"rotation": 90}, c.ORIENTATION),
        ({"container": "matroska,webm"}, c.CONTAINER),
        ({"width": 3840, "height": 2160}, c.RESOLUTION),
        ({"vprofile": "High 4:4:4 Predictive"}, c.VIDEO_PROFILE),
        ({"vlevel": 52}, c.VIDEO_LEVEL),
    ],
)
def test_each_rule_is_detected(overrides, expected):
    report = check_compliance(make_facts(**overrides), DEFAULT_CHAT)
    assert expected in failed_names(report)


def test_44100_hz_audio_is_accepted():
    report = check_compliance(
        make_facts(sample_rate=44100), DEFAULT_CHAT
    )
    assert report.ok


def test_size_cap_is_enforced():
    facts = make_facts(size_bytes=20 * MB)
    report = check_compliance(facts, DEFAULT_CHAT, 16 * MB)
    assert failed_names(report) == {c.FILE_SIZE}


def test_missing_audio_is_only_a_warning():
    report = check_compliance(
        make_facts(acodec=None, aprofile=None, channels=None,
                   sample_rate=None),
        DEFAULT_CHAT,
    )
    assert report.ok
    assert [r.name for r in report.warnings] == [c.AUDIO_PRESENT]


def test_landscape_status_gets_an_aspect_warning_not_an_error():
    report = check_compliance(make_facts(), DEFAULT_STATUS)
    assert report.ok
    assert c.ASPECT_RATIO in {r.name for r in report.warnings}


def test_portrait_status_has_no_aspect_warning():
    facts = make_facts(width=480, height=854)
    report = check_compliance(facts, DEFAULT_STATUS)
    assert c.ASPECT_RATIO not in {r.name for r in report.warnings}


def test_short_cap_lowers_the_allowed_resolution():
    facts = make_facts(width=1280, height=720)
    report = check_compliance(facts, DEFAULT_CHAT, short_cap=480)
    assert c.RESOLUTION in failed_names(report)


def test_changed_aspect_ratio_is_detected():
    facts = make_facts(width=640, height=480)
    report = check_compliance(facts, DEFAULT_CHAT, source_aspect=16 / 9)
    assert c.ASPECT_PRESERVED in failed_names(report)
PYEOF

write_file tests/unit/domain/test_decision.py <<'PYEOF'
from fakes.factories import make_facts
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.decision import choose_best_candidate, decide_path
from yt2wa.domain.models import Candidate, Method
from yt2wa.domain.profile import DEFAULT_CHAT

MB = 1024 * 1024


def decide(**overrides):
    facts = make_facts(**overrides)
    return decide_path(check_compliance(facts, DEFAULT_CHAT, 16 * MB))


def test_compliant_source_is_remuxed():
    decision = decide()
    assert decision.method is Method.REMUX
    assert decision.reasons == ("already compliant",)


def test_wrong_container_only_needs_a_remux():
    assert decide(container="matroska,webm").method is Method.REMUX


def test_missing_faststart_only_needs_a_remux():
    assert decide(faststart=False).method is Method.REMUX


def test_wrong_codec_needs_a_transcode():
    assert decide(vcodec="vp9").method is Method.TRANSCODE


def test_rotation_forces_a_transcode():
    assert decide(rotation=90).method is Method.TRANSCODE


def test_oversize_file_needs_a_transcode():
    assert decide(size_bytes=30 * MB).method is Method.TRANSCODE


def _candidate(name, size, **overrides):
    report = check_compliance(
        make_facts(size_bytes=size, **overrides), DEFAULT_CHAT, 16 * MB
    )
    return Candidate(name, report, size, Method.TRANSCODE)


def test_smallest_compliant_candidate_wins():
    big = _candidate("big", 10 * MB)
    small = _candidate("small", 4 * MB)
    assert choose_best_candidate([big, small]) is small


def test_non_compliant_candidates_are_never_chosen():
    bad = _candidate("bad", 1 * MB, vcodec="vp9")
    assert choose_best_candidate([bad]) is None
PYEOF

write_file tests/unit/domain/test_size_guard.py <<'PYEOF'
import pytest
from hypothesis import given
from hypothesis import strategies as st

from yt2wa.domain.models import RESOLUTION_RUNGS
from yt2wa.domain.profile import DEFAULT_CHAT
from yt2wa.domain.size_guard import (
    compute_video_bitrate_k,
    plan_size_ladder,
    rung_for,
)

MB = 1024 * 1024
MIN = DEFAULT_CHAT.min_video_bitrate_k


def test_bitrate_fits_inside_the_cap():
    rate = compute_video_bitrate_k(16 * MB, 60, 128)
    total_bytes = (rate + 128) * 1000 * 60 / 8
    assert total_bytes <= 16 * MB


def test_bitrate_rejects_zero_duration():
    with pytest.raises(ValueError):
        compute_video_bitrate_k(16 * MB, 0, 128)


def test_rung_for_rounds_up():
    assert rung_for(404) == 480
    assert rung_for(480) == 480
    assert rung_for(5000) == 1080


def test_ladder_starts_with_a_quality_encode():
    steps = plan_size_ladder(480, 360, 60, 16 * MB, 128, MIN)
    assert steps[0].kind == "crf"
    assert [s.kind for s in steps[1:]] == ["bitrate", "bitrate"]
    assert [s.resolution for s in steps] == [480, 480, 360]


def test_ladder_without_a_cap_is_a_single_step():
    assert len(plan_size_ladder(480, 360, 60, None, 128, MIN)) == 1


def test_ladder_skips_rungs_with_too_little_bitrate():
    # A 2 hour video at 16 MB leaves only ~15 kbit/s, so nothing is viable.
    steps = plan_size_ladder(720, 360, 7200, 16 * MB, 128, MIN)
    assert [s.kind for s in steps] == ["crf"]


@given(
    start=st.sampled_from(RESOLUTION_RUNGS),
    duration=st.floats(min_value=1, max_value=7200),
    cap_mb=st.integers(min_value=1, max_value=200),
)
def test_ladder_always_ends_and_never_goes_up(start, duration, cap_mb):
    steps = plan_size_ladder(start, 360, duration, cap_mb * MB, 128, MIN)
    resolutions = [s.resolution for s in steps]
    assert resolutions == sorted(resolutions, reverse=True)
    assert len(steps) <= len(RESOLUTION_RUNGS) + 1
    for step in steps:
        if step.kind == "bitrate":
            assert step.video_bitrate_k >= MIN[rung_for(step.resolution)]
PYEOF

write_file tests/unit/domain/test_ffmpeg_args.py <<'PYEOF'
from pathlib import Path

from fakes.factories import make_facts
from yt2wa.domain.ffmpeg_args import (
    FfmpegPlan,
    build_ffmpeg_args,
    build_video_filter,
    select_h264_level,
    target_size,
)
from yt2wa.domain.models import LadderStep, Method
from yt2wa.domain.profile import DEFAULT_CHAT


def plan(method=Method.TRANSCODE, cap=480, step=None, **facts):
    return FfmpegPlan(
        source=Path("in.mkv"),
        output=Path("out.mp4"),
        method=method,
        facts=make_facts(**facts),
        profile=DEFAULT_CHAT,
        short_cap=cap,
        step=step,
    )


def pairs(args, flag):
    return [args[i + 1] for i, a in enumerate(args) if a == flag]


def test_levels_follow_picture_size():
    assert select_h264_level(854, 480) == "3.0"
    assert select_h264_level(1280, 720) == "3.1"
    assert select_h264_level(1920, 1080) == "4.0"


def test_target_size_never_upscales():
    facts = make_facts(width=640, height=360)
    assert target_size(facts, 480, 1920) == (640, 360)


def test_target_size_scales_landscape_by_short_edge():
    facts = make_facts(width=1920, height=1080)
    assert target_size(facts, 480, 1920) == (854, 480)


def test_target_size_scales_portrait_by_short_edge():
    facts = make_facts(width=1080, height=1920)
    assert target_size(facts, 480, 1920) == (480, 854)


def test_target_size_uses_even_numbers_and_swaps_for_rotation():
    facts = make_facts(width=853, height=481, rotation=90)
    width, height = target_size(facts, 1080, 1920)
    assert width % 2 == 0 and height % 2 == 0
    assert (width, height) == (480, 852)


def test_no_filter_when_nothing_changes():
    facts = make_facts()
    assert build_video_filter(facts, facts.display_size, 30) is None


def test_fps_filter_only_above_the_limit():
    facts = make_facts(fps=60.0)
    assert build_video_filter(facts, facts.display_size, 30) == "fps=30"


def test_transcode_args_follow_the_profile():
    args = build_ffmpeg_args(plan(width=1280, height=720))
    assert pairs(args, "-c:v") == ["libx264"]
    assert pairs(args, "-pix_fmt") == ["yuv420p"]
    assert pairs(args, "-c:a") == ["aac"]
    assert pairs(args, "-profile:a") == ["aac_low"]
    assert pairs(args, "-ac") == ["2"]
    assert pairs(args, "-ar") == ["48000"]
    assert pairs(args, "-movflags") == ["+faststart"]
    assert pairs(args, "-vf") == ["scale=854:480:flags=lanczos"]
    assert pairs(args, "-crf") == ["23"]
    assert args[-1] == "out.mp4"


def test_bitrate_step_sets_the_target_bitrate():
    step = LadderStep("bitrate", 480, 900)
    args = build_ffmpeg_args(plan(step=step))
    assert pairs(args, "-b:v") == ["900k"]
    assert "-crf" not in args


def test_44100_hz_audio_is_kept():
    args = build_ffmpeg_args(plan(sample_rate=44100))
    assert pairs(args, "-ar") == ["44100"]


def test_silent_source_gets_no_audio_track():
    args = build_ffmpeg_args(plan(acodec=None, aprofile=None))
    assert "-an" in args
    assert "-c:a" not in args


def test_remux_copies_streams_and_enables_faststart():
    args = build_ffmpeg_args(plan(method=Method.REMUX))
    assert pairs(args, "-c") == ["copy"]
    assert "libx264" not in args
    assert pairs(args, "-movflags") == ["+faststart"]


def test_command_is_a_list_of_plain_strings():
    args = build_ffmpeg_args(plan())
    assert all(isinstance(a, str) for a in args)
    assert args[0] == "ffmpeg"
PYEOF

write_file tests/unit/domain/test_mp4_atoms.py <<'PYEOF'
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
PYEOF

write_file tests/unit/domain/test_profile.py <<'PYEOF'
import pytest

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target
from yt2wa.domain.profile import (
    DEFAULT_PROFILES,
    profile_for,
    profile_from_mapping,
)


def test_original_target_borrows_the_chat_profile():
    assert profile_for(Target.ORIGINAL, DEFAULT_PROFILES).name == "chat"


def test_override_keeps_other_defaults():
    profile = profile_from_mapping("chat", {"crf": 28})
    assert profile.crf == 28
    assert profile.max_short_edge == 1080


def test_bitrate_tables_are_converted_to_int_keys():
    profile = profile_from_mapping(
        "chat", {"min_video_bitrate_k": {"480": 300}}
    )
    assert profile.min_video_bitrate_k == {480: 300}


def test_unknown_setting_is_rejected():
    with pytest.raises(ConfigError):
        profile_from_mapping("chat", {"colour": "red"})
PYEOF

write_file tests/unit/application/test_share_strategy.py <<'PYEOF'
from pathlib import Path

import pytest

from fakes.factories import make_facts
from fakes.fakes import FakeDownloader, FakeProbe, FakeTranscoder
from yt2wa.application.dto import ConvertRequest, JobContext
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.domain.errors import SizeCapError
from yt2wa.domain.models import (
    Method,
    SourceKind,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.profile import DEFAULT_CHAT

MB = 1024 * 1024


def run_strategy(tmp_path: Path, source_facts, sizes):
    downloader = FakeDownloader()
    transcoder = FakeTranscoder(sizes)
    strategy = ShareStrategy(
        downloader, FakeProbe(source_facts), transcoder
    )
    request = ConvertRequest(
        url="https://youtu.be/abcdefghijk",
        target=Target.CHAT,
        resolution=480,
        output_dir=tmp_path / "out",
    )
    ctx = JobContext(
        request=request,
        ref=SourceRef(request.url, SourceKind.VIDEO, "abcdefghijk"),
        metadata=SourceMetadata("abcdefghijk", "My Clip", 60.0),
        job_dir=tmp_path / "job",
        profile=DEFAULT_CHAT,
        size_cap_bytes=16 * MB,
        on_progress=ignore_progress,
    )
    return strategy.run(ctx), transcoder, downloader


def test_compliant_source_is_remuxed_without_re_encoding(tmp_path):
    source = make_facts(container="matroska,webm", faststart=None)
    output, transcoder, _ = run_strategy(tmp_path, source, [5 * MB])
    assert output.method is Method.REMUX
    assert len(transcoder.calls) == 1
    assert "copy" in transcoder.calls[0]


def test_non_compliant_source_is_transcoded(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    output, transcoder, _ = run_strategy(tmp_path, source, [6 * MB])
    assert output.method is Method.TRANSCODE
    assert "libx264" in transcoder.calls[0]


def test_ladder_steps_down_until_the_file_fits(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    output, transcoder, _ = run_strategy(
        tmp_path, source, [20 * MB, 10 * MB]
    )
    assert len(transcoder.calls) == 2
    assert "-crf" in transcoder.calls[0]
    assert "-b:v" in transcoder.calls[1]
    assert output.facts.size_bytes == 10 * MB


def test_oversize_compliant_source_falls_back_to_the_ladder(tmp_path):
    source = make_facts(size_bytes=30 * MB)
    output, transcoder, _ = run_strategy(
        tmp_path, source, [30 * MB, 9 * MB]
    )
    assert output.method is Method.TRANSCODE
    assert len(transcoder.calls) == 2


def test_fails_when_nothing_fits(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    with pytest.raises(SizeCapError):
        run_strategy(tmp_path, source, [30 * MB] * 10)


def test_download_is_limited_to_the_requested_resolution(tmp_path):
    source = make_facts()
    _, _, downloader = run_strategy(tmp_path, source, [5 * MB])
    assert downloader.choices[0].sort[0] == "res:480"
PYEOF

write_file tests/unit/application/test_original_strategy.py <<'PYEOF'
from fakes.factories import make_facts
from fakes.fakes import FakeDownloader, FakeProbe
from yt2wa.application.dto import ConvertRequest, JobContext
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.domain.models import (
    Method,
    SourceKind,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.profile import DEFAULT_CHAT


def run(tmp_path, facts):
    strategy = OriginalStrategy(FakeDownloader(), FakeProbe(facts))
    request = ConvertRequest(
        url="https://youtu.be/abcdefghijk",
        target=Target.ORIGINAL,
        resolution=480,
        output_dir=tmp_path,
    )
    ctx = JobContext(
        request=request,
        ref=SourceRef(request.url, SourceKind.VIDEO, "abcdefghijk"),
        metadata=SourceMetadata("abcdefghijk", "My Clip", 60.0),
        job_dir=tmp_path / "job",
        profile=DEFAULT_CHAT,
        size_cap_bytes=None,
        on_progress=ignore_progress,
    )
    return strategy.run(ctx)


def test_original_is_never_converted(tmp_path):
    output = run(tmp_path, make_facts())
    assert output.method is Method.DOWNLOAD
    assert output.path.name == "source.mkv"
    assert output.warnings == ()


def test_unshareable_original_gets_a_warning(tmp_path):
    output = run(tmp_path, make_facts(vcodec="vp9", acodec="opus"))
    assert len(output.warnings) == 1
    assert "--target chat" in output.warnings[0]
PYEOF

write_file tests/contract/test_workspace.py <<'PYEOF'
from yt2wa.infrastructure.local_workspace import LocalWorkspace


def test_job_dirs_are_unique_and_cleaned_up(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    first, second = workspace.new_job_dir(), workspace.new_job_dir()
    assert first != second
    workspace.cleanup(first)
    assert not first.exists()
    assert second.exists()


def test_publish_never_overwrites_an_existing_file(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    out = tmp_path / "out"
    for text in ("one", "two"):
        src = tmp_path / "src.mp4"
        src.write_text(text)
        workspace.publish(src, out, "clip.mp4")
    assert (out / "clip.mp4").read_text() == "one"
    assert (out / "clip-1.mp4").read_text() == "two"


def test_stale_jobs_only_lists_old_folders(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    job = workspace.new_job_dir()
    assert workspace.stale_jobs(3600) == []
    assert workspace.stale_jobs(-1) == [job]
PYEOF

write_file tests/unit/test_adapters.py <<'PYEOF'
from yt2wa.domain.errors import (
    AgeRestrictedError,
    GeoBlockedError,
    NetworkError,
    PrivateVideoError,
    RemovedVideoError,
    SourceUnavailableError,
)
from yt2wa.infrastructure.ffprobe_probe import parse_ffprobe_json
from yt2wa.infrastructure.ytdlp_downloader import classify_download_error


def test_download_errors_are_translated():
    cases = {
        "ERROR: Private video. Sign in": PrivateVideoError,
        "Sign in to confirm your age": AgeRestrictedError,
        "not available in your country": GeoBlockedError,
        "Video unavailable": RemovedVideoError,
        "Sign in to confirm you're not a bot": SourceUnavailableError,
        "HTTP Error 429: Too Many Requests": NetworkError,
        "something odd": SourceUnavailableError,
    }
    for message, expected in cases.items():
        assert isinstance(classify_download_error(message), expected)


def test_ffprobe_json_is_parsed():
    data = {
        "format": {"format_name": "mov,mp4", "duration": "12.5"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "profile": "High",
                "level": 31,
                "pix_fmt": "yuv420p",
                "width": 1080,
                "height": 1920,
                "avg_frame_rate": "30000/1001",
                "side_data_list": [{"rotation": -90}],
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "profile": "LC",
                "channels": 2,
                "sample_rate": "48000",
            },
        ],
    }
    facts = parse_ffprobe_json(data, 1234, True)
    assert facts.vcodec == "h264"
    assert round(facts.fps, 2) == 29.97
    assert facts.rotation == 90
    assert facts.display_size == (1920, 1080)
    assert facts.sample_rate == 48000
    assert facts.faststart is True
    assert facts.duration_s == 12.5
PYEOF

write_file tests/unit/test_settings.py <<'PYEOF'
from pathlib import Path

import pytest

from yt2wa.bootstrap.profiles import load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target


def settings(env):
    return Settings.from_env(env, dotenv=Path("does-not-exist"))


def test_defaults():
    result = settings({})
    assert result.default_target is Target.CHAT
    assert result.default_resolution == 480
    assert result.max_size_mb is None


def test_environment_overrides():
    result = settings(
        {
            "YT2WA_DEFAULT_TARGET": "status",
            "YT2WA_DEFAULT_RESOLUTION": "720",
            "YT2WA_MAX_SIZE_MB": "8",
        }
    )
    assert result.default_target is Target.STATUS
    assert result.default_resolution == 720
    assert load_profiles(result)["chat"].size_cap_mb == 8


def test_bad_values_raise_config_errors():
    with pytest.raises(ConfigError):
        settings({"YT2WA_DEFAULT_TARGET": "tv"})
    with pytest.raises(ConfigError):
        settings({"YT2WA_NET_RETRIES": "many"})


def test_profile_file_can_override_values(tmp_path):
    profile_file = tmp_path / "profiles.toml"
    profile_file.write_text("[chat]\ncrf = 30\n")
    result = settings({"YT2WA_PROFILE_FILE": str(profile_file)})
    profiles = load_profiles(result)
    assert profiles["chat"].crf == 30
    assert profiles["status"].crf == 30
    assert profiles["status"].advisory_aspect is not None
PYEOF

write_file tests/unit/test_cli.py <<'PYEOF'
from yt2wa.domain.errors import SizeCapError, UsageError
from yt2wa.interface.cli import build_parser, with_default_command
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code


def test_bare_link_runs_convert():
    assert with_default_command(["https://youtu.be/x"])[0] == "convert"


def test_known_command_is_kept():
    assert with_default_command(["doctor"]) == ["doctor"]


def test_keep_original_sets_the_target():
    args = build_parser().parse_args(
        ["convert", "u", "--keep-original", "-r", "best"]
    )
    assert args.target == "original"
    assert args.resolution == 0


def test_exit_codes():
    assert map_exception_to_exit_code(UsageError("x")) == ExitCode.USAGE
    assert (
        map_exception_to_exit_code(SizeCapError("x")) == ExitCode.CONSTRAINT
    )
    assert map_exception_to_exit_code(ValueError("x")) == ExitCode.GENERAL
PYEOF

write_file tests/integration/test_ffmpeg_roundtrip.py <<'PYEOF'
"""Run the real ffmpeg on a tiny video and check the result."""

import shutil
import subprocess

import pytest

from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.ffmpeg_args import FfmpegPlan, build_ffmpeg_args
from yt2wa.domain.models import Method, ignore_progress
from yt2wa.domain.profile import DEFAULT_CHAT
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe

pytestmark = pytest.mark.ffmpeg


def has_encoders() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "libx264" in out and "mpeg4" in out


pytestmark = [
    pytest.mark.ffmpeg,
    pytest.mark.skipif(not has_encoders(), reason="ffmpeg not available"),
]


@pytest.fixture
def source(tmp_path):
    """A 1280x720, 60 fps MPEG-4 + MP3 clip that is NOT compliant."""
    path = tmp_path / "source.mkv"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=60",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "mpeg4", "-c:a", "libmp3lame", "-ac", "1",
            str(path),
        ],  # fmt: skip
        check=True,
    )
    return path


def test_transcode_output_passes_the_compliance_checker(source, tmp_path):
    probe = FfprobeMediaProbe()
    facts = probe.inspect(source)
    output = tmp_path / "out.mp4"
    plan = FfmpegPlan(
        source=source,
        output=output,
        method=Method.TRANSCODE,
        facts=facts,
        profile=DEFAULT_CHAT,
        short_cap=480,
    )
    FfmpegTranscoder().run(
        build_ffmpeg_args(plan), facts.duration_s, ignore_progress
    )

    result = probe.inspect(output)
    report = check_compliance(
        result, DEFAULT_CHAT, 16 * 1024 * 1024, short_cap=480,
        source_aspect=facts.aspect,
    )
    assert report.ok, [
        (r.name, r.expected, r.actual) for r in report.errors
    ]
    assert result.display_size == (854, 480)
    assert result.fps <= 30.05
    assert result.faststart is True
PYEOF

write_file tests/e2e/test_real_download.py <<'PYEOF'
"""Opt-in test that touches the real internet.

Run with:  pytest -m network --url <link to a video you may download>
"""

import os

import pytest

from yt2wa.domain.url_rules import classify_url

pytestmark = pytest.mark.network

URL = os.environ.get("YT2WA_E2E_URL", "")


@pytest.mark.skipif(not URL, reason="set YT2WA_E2E_URL to a video you may use")
def test_probe_real_video():
    from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader

    metadata = YtDlpDownloader().probe(classify_url(URL))
    assert metadata.duration_s > 0
PYEOF

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
echo "Done. Next steps:"
echo "  1. Activate your virtual environment:  source .venv/bin/activate"
echo "  2. Install the project:                pip install -e \".[dev]\""
echo "  3. Check your setup:                   yt2wa doctor"
echo "  4. Run the checks:                     make check"
echo "  5. Try it:                             yt2wa <youtube-url> --dry-run"
