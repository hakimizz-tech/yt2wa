# 0008: Search is a port with three providers

**Status:** accepted

`SearchProvider` has three adapters: `ytsearch` (yt-dlp `ytsearchN:`),
`ytmusic-url` (yt-dlp on the YouTube Music search page) and `ytmusicapi`
(optional library). Providers only find candidates. Downloads always go
through yt-dlp using a canonical `watch?v=` URL.
