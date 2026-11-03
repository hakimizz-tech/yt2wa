# 0007: Audio size guard is a bitrate-only ladder

**Status:** accepted

Audio has no resolution to lower. The planner lists bitrates (128, 96,
64 kbit/s by default), skips any that cannot fit the cap even in theory,
and fails early when none can.
