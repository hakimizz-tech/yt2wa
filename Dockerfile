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
RUN pip install ".[music]"

RUN useradd --create-home app && mkdir /out && chown app /out
USER app
ENV YT2WA_OUTPUT_DIR=/out

ENTRYPOINT ["yt2wa"]
CMD ["--help"]
