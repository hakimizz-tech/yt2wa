# WhatsApp constraints

Last verified: never (check before release)

## Video

| Item             | Value used by yt2wa                 |
|------------------|-------------------------------------|
| Container        | MP4 with `+faststart`               |
| Video            | H.264, yuv420p, up to 30 fps        |
| Audio            | AAC-LC, stereo, 44.1 or 48 kHz      |
| Chat resolution  | Up to 1920x1080 (long x short edge) |
| Status           | Up to 1080x1920, 9:16 is ideal      |
| Size cap         | 16 MB (media, not Document)         |
| Status duration  | Advisory warning above 60 s         |

## Audio

| Item             | Value used by yt2wa                      |
|------------------|------------------------------------------|
| Container        | M4A (MP4 audio) with `+faststart`, or MP3 |
| Codec            | AAC-LC (M4A) or MP3                      |
| Channels         | Mono or stereo                           |
| Sample rate      | 44.1 or 48 kHz                           |
| Bitrate          | Up to 128 kbit/s by default              |
| Size cap         | 16 MB (media, not Document)              |
| Status           | Not possible: Status needs a picture     |

These are recommended settings, not a guarantee of acceptance.
