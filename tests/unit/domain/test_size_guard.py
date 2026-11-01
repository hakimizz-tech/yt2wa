import pytest
from hypothesis import given
from hypothesis import strategies as st

from yt2wa.domain.models import RESOLUTION_RUNGS
from yt2wa.domain.profile import DEFAULT_CHAT
from yt2wa.domain.size_guard import (
    compute_video_bitrate_k,
    plan_size_ladder,
    rung_for,
)

MB = 1024 * 1024
MIN = DEFAULT_CHAT.min_video_bitrate_k


def test_bitrate_fits_inside_the_cap():
    rate = compute_video_bitrate_k(16 * MB, 60, 128)
    total_bytes = (rate + 128) * 1000 * 60 / 8
    assert total_bytes <= 16 * MB


def test_bitrate_rejects_zero_duration():
    with pytest.raises(ValueError):
        compute_video_bitrate_k(16 * MB, 0, 128)


def test_rung_for_rounds_up():
    assert rung_for(404) == 480
    assert rung_for(480) == 480
    assert rung_for(5000) == 1080


def test_ladder_starts_with_a_quality_encode():
    steps = plan_size_ladder(480, 360, 60, 16 * MB, 128, MIN)
    assert steps[0].kind == "crf"
    assert [s.kind for s in steps[1:]] == ["bitrate", "bitrate"]
    assert [s.resolution for s in steps] == [480, 480, 360]


def test_ladder_without_a_cap_is_a_single_step():
    assert len(plan_size_ladder(480, 360, 60, None, 128, MIN)) == 1


def test_ladder_skips_rungs_with_too_little_bitrate():
    # A 2 hour video at 16 MB leaves only ~15 kbit/s, so nothing is viable.
    steps = plan_size_ladder(720, 360, 7200, 16 * MB, 128, MIN)
    assert [s.kind for s in steps] == ["crf"]


@given(
    start=st.sampled_from(RESOLUTION_RUNGS),
    duration=st.floats(min_value=1, max_value=7200),
    cap_mb=st.integers(min_value=1, max_value=200),
)
def test_ladder_always_ends_and_never_goes_up(start, duration, cap_mb):
    steps = plan_size_ladder(start, 360, duration, cap_mb * MB, 128, MIN)
    resolutions = [s.resolution for s in steps]
    assert resolutions == sorted(resolutions, reverse=True)
    assert len(steps) <= len(RESOLUTION_RUNGS) + 1
    for step in steps:
        if step.kind == "bitrate":
            assert step.video_bitrate_k >= MIN[rung_for(step.resolution)]
