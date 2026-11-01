from fakes.factories import make_facts
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.decision import choose_best_candidate, decide_path
from yt2wa.domain.models import Candidate, Method
from yt2wa.domain.profile import DEFAULT_CHAT

MB = 1024 * 1024


def decide(**overrides):
    facts = make_facts(**overrides)
    return decide_path(check_compliance(facts, DEFAULT_CHAT, 16 * MB))


def test_compliant_source_is_remuxed():
    decision = decide()
    assert decision.method is Method.REMUX
    assert decision.reasons == ("already compliant",)


def test_wrong_container_only_needs_a_remux():
    assert decide(container="matroska,webm").method is Method.REMUX


def test_missing_faststart_only_needs_a_remux():
    assert decide(faststart=False).method is Method.REMUX


def test_wrong_codec_needs_a_transcode():
    assert decide(vcodec="vp9").method is Method.TRANSCODE


def test_rotation_forces_a_transcode():
    assert decide(rotation=90).method is Method.TRANSCODE


def test_oversize_file_needs_a_transcode():
    assert decide(size_bytes=30 * MB).method is Method.TRANSCODE


def _candidate(name, size, **overrides):
    report = check_compliance(
        make_facts(size_bytes=size, **overrides), DEFAULT_CHAT, 16 * MB
    )
    return Candidate(name, report, size, Method.TRANSCODE)


def test_smallest_compliant_candidate_wins():
    big = _candidate("big", 10 * MB)
    small = _candidate("small", 4 * MB)
    assert choose_best_candidate([big, small]) is small


def test_non_compliant_candidates_are_never_chosen():
    bad = _candidate("bad", 1 * MB, vcodec="vp9")
    assert choose_best_candidate([bad]) is None
