# yt2wa

Download a YouTube video or Short with
[yt-dlp](https://github.com/yt-dlp/yt-dlp) and, when you want to share it,
convert it with [ffmpeg](https://ffmpeg.org) into a file that WhatsApp can
send as a Status or in a chat.

> **Legal note.** Downloading may break YouTube's Terms of Service or
> copyright law. Use this tool only for content you own, have permission to
> use, or that is licensed for reuse.

## Install

ffmpeg and ffprobe must be on your `PATH` (or set `YT2WA_FFMPEG_BIN` and
`YT2WA_FFPROBE_BIN`).

```bash
pip install -e ".[dev]"
yt2wa doctor
```

## Usage

```bash
# Share in a chat or group (default target, 480p).
yt2wa "https://youtu.be/VIDEO_ID"

# Post as a Status in 720p.
yt2wa "https://youtu.be/VIDEO_ID" -t status -r 720

# Keep the video as it is, for watching on your own phone.
yt2wa "https://youtu.be/VIDEO_ID" --keep-original -r best

# Check any file against the WhatsApp profile.
yt2wa verify clip.mp4 -t status
```

## Targets

| Target     | Purpose                      | Re-encode?                 |
|------------|------------------------------|----------------------------|
| `original` | Watch later, not for sharing | Never                      |
| `chat`     | Send to a person or group    | Only when the file needs it |
| `status`   | Post as a WhatsApp Status    | Only when the file needs it |

`-r/--resolution` accepts `144, 240, 360, 480, 720, 1080, best`. The number
is the short edge, so `1080` means 1920x1080 or 1080x1920. Output is never
upscaled. The default is `480`.

A passing compliance report means the file matches the recommended
settings. It is not a guarantee that WhatsApp accepts it. WhatsApp may
re-compress media. Send the file as a **Document** to keep its quality.

## Exit codes

| Code | Meaning                                  |
|------|------------------------------------------|
| 0    | Success                                  |
| 2    | Invalid usage or configuration           |
| 3    | Unsupported URL                          |
| 4    | Source unavailable                       |
| 5    | Network failure                          |
| 6    | Missing or incompatible dependency       |
| 7    | Transcode failed                         |
| 8    | Could not meet size or compliance limits |
| 130  | Interrupted                              |

## Development

```bash
make check      # ruff, mypy, import-linter and pytest
```

See `docs/architecture.md` for the design.
