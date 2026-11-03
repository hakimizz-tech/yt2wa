# 0006: Audio compliance is its own pure function

**Status:** accepted

`check_audio_compliance` and `AudioProfile` sit beside the video ones, so
neither needs conditionals for the other. The same function decides
remux versus transcode, verifies the result and powers `verify`.
