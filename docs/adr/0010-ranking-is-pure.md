# 0010: "Most likely" is a pure, deterministic ranking

**Status:** accepted

`rank_candidates` uses no network and no randomness. Weights and penalties
are named constants, and golden cases in `tests/fixtures/search` show the
effect of any change.
