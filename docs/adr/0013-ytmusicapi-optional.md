# 0013: ytmusicapi is an optional extra, used without logging in

**Status:** accepted

Install it with `pip install "yt2wa[music]"`. It is imported lazily, used
for search only and never given credentials or cookies. If it is missing,
`auto` skips it and `doctor` reports it as optional.
