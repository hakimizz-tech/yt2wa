# 0004: Verify the output file, not the encoder settings

**Status:** accepted

Re-encoding does not guarantee a compliant or smaller file. One pure
function, `check_compliance`, decides remux vs. transcode, verifies the
result and powers `yt2wa verify`.
