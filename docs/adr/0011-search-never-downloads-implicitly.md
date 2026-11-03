# 0011: Search never downloads implicitly

**Status:** accepted

Downloading needs `--download`, enough confidence and an unambiguous
result, or an explicit `--pick N`. There are no interactive prompts, so
scripts stay predictable. Failing these checks exits with code 9.
