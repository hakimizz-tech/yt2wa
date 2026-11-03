from hypothesis import given
from hypothesis import strategies as st

from yt2wa.domain.audio_size_guard import (
    estimated_size_bytes,
    plan_audio_ladder,
)

MB = 1024 * 1024
LADDER = (128, 96, 64)


def rates(steps):
    return [s.bitrate_k for s in steps]


def test_ladder_starts_at_the_requested_bitrate_and_goes_down():
    steps = plan_audio_ladder(200, 16 * MB, LADDER, 48, 192)
    assert rates(steps) == [192, 128, 96, 64]


def test_ladder_skips_rates_that_cannot_fit():
    # 1 hour: 128 kbit/s is about 59 MB and 64 kbit/s about 30 MB.
    assert rates(plan_audio_ladder(3600, 40 * MB, LADDER, 48, 128)) == [64]


def test_ladder_is_empty_when_nothing_can_fit():
    assert plan_audio_ladder(7200, 16 * MB, LADDER, 48, 128) == ()


def test_no_cap_means_a_single_attempt():
    assert rates(plan_audio_ladder(9999, None, LADDER, 48, 96)) == [96]


def test_rates_below_the_minimum_are_dropped():
    steps = plan_audio_ladder(60, 16 * MB, LADDER, 100, 128)
    assert rates(steps) == [128]


@given(
    duration=st.floats(min_value=1, max_value=20_000),
    cap_mb=st.integers(min_value=1, max_value=200),
    start=st.sampled_from([64, 96, 128, 192]),
)
def test_ladder_properties(duration, cap_mb, start):
    cap = cap_mb * MB
    steps = plan_audio_ladder(duration, cap, LADDER, 48, start)
    values = rates(steps)
    assert values == sorted(set(values), reverse=True)
    assert all(v >= 48 for v in values)
    assert all(estimated_size_bytes(v, duration) <= cap for v in values)
