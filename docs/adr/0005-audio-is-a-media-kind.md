# 0005: Audio is a media kind, not a new target

**Status:** accepted

Targets say what a file is *for*. Audio versus video says what it
*contains*. They are independent, so `--audio` (`-x`) is a flag and the
strategy is chosen by `(media kind, target)`. Audio with `--target status`
is a usage error because Status needs a picture.
