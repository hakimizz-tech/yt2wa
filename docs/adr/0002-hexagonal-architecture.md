# 0002: Hexagonal architecture

**Status:** accepted

Dependencies point inward: interface -> application -> domain <-
infrastructure. yt-dlp and ffmpeg sit behind ports so they can be faked in
tests or replaced. `import-linter` enforces the rule in CI.
