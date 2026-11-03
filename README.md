# yt2wa

Download a YouTube video, Short or just its audio with
[yt-dlp](https://github.com/yt-dlp/yt-dlp), find the song or video you
mean by searching, and convert the result with [ffmpeg](https://ffmpeg.org)
into a file that WhatsApp can send as a Status or in a chat.

> **Legal note.** Downloading may break YouTube's Terms of Service or
> copyright law. Use this tool only for content you own, have permission to
> use, or that is licensed for reuse.

## Install

ffmpeg and ffprobe must be on your `PATH` (or set `YT2WA_FFMPEG_BIN` and
`YT2WA_FFPROBE_BIN`).

```bash
pip install -e ".[dev,music]"   # "music" adds the best song search
yt2wa doctor
```

The `music` extra installs [ytmusicapi](https://github.com/sigma67/ytmusicapi).
It is optional. Without it, music searches fall back to yt-dlp.

## Usage

```bash
# Share a video in a chat or group (default target, 480p).
yt2wa "https://youtu.be/VIDEO_ID"

# Post as a Status in 720p.
yt2wa "https://youtu.be/VIDEO_ID" -t status -r 720

# Keep the video as it is, for watching on your own phone.
yt2wa "https://youtu.be/VIDEO_ID" --keep-original -r best

# Audio only, ready to send on WhatsApp (M4A, AAC-LC).
yt2wa "https://youtu.be/VIDEO_ID" -x

# Audio only, exactly as YouTube serves it.
yt2wa "https://youtu.be/VIDEO_ID" -x --keep-original

# Check any file against the WhatsApp profile.
yt2wa verify clip.mp4 -t status
```

### Search

```bash
# Find the most likely song and show alternates.
yt2wa search "daft punk one more time" --type music

# Richer metadata (album, track, upload date) for the best match.
yt2wa search "bohemian rhapsody" --detail --json

# Search, then download the audio of the best match.
yt2wa search "one more time daft punk" --type music -x --download

# Several results match equally well? Pick one yourself.
yt2wa search "one more time" --type music -x --download --pick 2
```

The best match's link is printed on stdout (or the file path when you use
`--download`). Everything else goes to stderr, so the output is easy to
use in scripts.

**Search methods** (`--provider`, default `auto`):

| Method        | What it is                                  |
|---------------|---------------------------------------------|
| `ytmusicapi`  | YouTube Music via the optional `music` extra |
| `ytmusic-url` | The YouTube Music search page, through yt-dlp |
| `ytsearch`    | Regular YouTube search, through yt-dlp      |

For `--type music`, `auto` tries them in that order and moves on when one
fails or finds nothing. Video and `any` searches use `ytsearch`. Naming a
method yourself turns the fallback off.

`--download` only runs when the match is confident enough
(`--min-confidence`, default 0.6) and not tied with another result.

## Targets

| Target     | Purpose                      | Re-encode?                  |
|------------|------------------------------|-----------------------------|
| `original` | Watch later, not for sharing | Never                       |
| `chat`     | Send to a person or group    | Only when the file needs it |
| `status`   | Post as a WhatsApp Status    | Only when the file needs it |

Audio (`-x`) works with `original` and `chat`. Status needs a picture, so
`-x -t status` is an error.

`-r/--resolution` accepts `144, 240, 360, 480, 720, 1080, best`. The number
is the short edge, so `1080` means 1920x1080 or 1080x1920. Output is never
upscaled. The default is `480`. It is ignored for audio.

`--audio-format {m4a,mp3}` and `--audio-bitrate {64,96,128,192}` apply to
`chat`. If a file is too big, the tool tries lower bitrates before it
gives up.

A passing compliance report means the file matches the recommended
settings. It is not a guarantee that WhatsApp accepts it. WhatsApp may
re-compress media. Send the file as a **Document** to keep its quality.

## Exit codes

| Code | Meaning                                       |
|------|-----------------------------------------------|
| 0    | Success                                       |
| 2    | Invalid usage or configuration                |
| 3    | Unsupported URL                               |
| 4    | Source unavailable                            |
| 5    | Network failure                               |
| 6    | Missing or incompatible dependency            |
| 7    | Transcode failed                              |
| 8    | Could not meet size or compliance limits      |
| 9    | Nothing found, or no confident enough match   |
| 130  | Interrupted                                   |

## Configuration

Everything is configured with `YT2WA_*` environment variables (see
`.env.example`). Command line flags win over the environment.

## Development

```bash
make check      # ruff, mypy, import-linter and pytest
```

The test suite includes architecture and twelve-factor checks
(`tests/architecture`) and a v0.2 compatibility contract
(`tests/regression`). See `docs/architecture.md` for the design and
`docs/adr` for the decisions.
