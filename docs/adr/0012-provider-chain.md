# 0012: Provider selection and a fallback chain

**Status:** accepted

For music, `auto` tries `ytmusicapi`, then `ytmusic-url`, then `ytsearch`.
The next method is tried when one fails or finds nothing. The first method
that succeeds wins; results are not merged. Naming a method turns the
fallback off. The result records every attempt.
