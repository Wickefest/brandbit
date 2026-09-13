# Tests the specialist congruence regen loop accept and retry paths.
# Mocks fragrance music judge and audio so the loop stays offline.
from __future__ import annotations
import pytest
from src.config import Settings
from src.models.congruence import (
    AutomatedProxySignals,
    CongruenceReport,
    DescriptorConsistency,
)
from src.services import congruence_scoring



def test_specialist_loop_accepts_without_regen(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=2, musicgen_api_key="r8_test"),
    )
    monkeypatch.setattr(
        "src.services.fragrance_generation.generate_fragrance",
        lambda bad, judge_feedback=None: sample_fragrance,
    )
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda bad, judge_feedback=None: sample_music,
    )
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_a, **_k: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned",
        ),
    )

    fragrance, music, report = congruence_scoring.run_specialist_congruence_loop(sample_bad)
    assert fragrance is sample_fragrance
    assert music.style == sample_music.style
    assert report.accepted is True
    assert report.regen_count == 0
    assert len(report.attempts) == 1

def test_specialist_loop_regenerates_failing_music_only(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=2, musicgen_api_key="r8_test"),
    )

    frag_calls = {"n": 0, "feedback": []}
    music_calls = {"n": 0, "feedback": []}

    def _frag(bad, judge_feedback=None):
        frag_calls["n"] += 1
        frag_calls["feedback"].append(judge_feedback)
        return sample_fragrance

    def _music(bad, judge_feedback=None):
        music_calls["n"] += 1
        music_calls["feedback"].append(judge_feedback)
        return sample_music.model_copy(update={"style": f"pass-{music_calls['n']}"})

    judge_passes = [
        CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=False,
                details="music too aggressive",
            ),
            summary="music mismatch",
        ),
        CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned after regen",
        ),
    ]
    judge_idx = {"i": 0}

    def _judge(*_a, **_k):
        i = judge_idx["i"]
        judge_idx["i"] += 1
        return judge_passes[min(i, len(judge_passes) - 1)]

    monkeypatch.setattr("src.services.fragrance_generation.generate_fragrance", _frag)
    monkeypatch.setattr("src.services.music_generation.generate_music_direction", _music)
    monkeypatch.setattr(congruence_scoring, "compute_congruence", _judge)

    fragrance, music, report = congruence_scoring.run_specialist_congruence_loop(sample_bad)

    assert fragrance is sample_fragrance
    assert frag_calls["n"] == 1                          
    assert music_calls["n"] == 2                       
    assert music_calls["feedback"][1] is not None
    assert "music too aggressive" in music_calls["feedback"][1]
    assert report.accepted is True
    assert report.regen_count == 1
    assert report.attempts[0].regenerated == ["music"]
    assert music.style == "pass-2"

def test_audio_synthesized_once_after_music_judge_regens(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
                                                                                                 
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=2, musicgen_api_key="r8_test"),
    )

    music_calls = {"n": 0}
    audio_calls: list[object] = []

    def _music(bad, judge_feedback=None):
        music_calls["n"] += 1
        return sample_music.model_copy(update={"style": f"draft-{music_calls['n']}"})

    def _audio(direction, execution_id, bad=None, settings=None):
        audio_calls.append((direction.style, execution_id))
        return f"/api/audio/{execution_id}"

    judge_passes = [
        CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=False,
                details="music off",
            ),
            summary="music mismatch",
        ),
        CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=False,
                details="still off",
            ),
            summary="music still mismatch",
        ),
        CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned",
        ),
    ]
    judge_idx = {"i": 0}

    def _judge(*_a, **_k):
        i = judge_idx["i"]
        judge_idx["i"] += 1
        return judge_passes[min(i, len(judge_passes) - 1)]

    monkeypatch.setattr(
        "src.services.fragrance_generation.generate_fragrance",
        lambda bad, judge_feedback=None: sample_fragrance,
    )
    monkeypatch.setattr("src.services.music_generation.generate_music_direction", _music)
    monkeypatch.setattr("src.services.audio_synthesis.synthesize_audio", _audio)
    monkeypatch.setattr(congruence_scoring, "compute_congruence", _judge)

    _frag, music, report = congruence_scoring.run_specialist_congruence_loop(
        sample_bad,
        execution_id="Indomie_001",
    )

    assert music_calls["n"] == 3                           
    assert report.regen_count == 2
    assert len(audio_calls) == 1
    assert audio_calls[0] == ("draft-3", "Indomie_001")
    assert music.style == "draft-3"
    assert music.audio_sample_ref == "/api/audio/Indomie_001"

def test_specialist_loop_stops_at_max_regen(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=1, musicgen_api_key="r8_test"),
    )
    monkeypatch.setattr(
        "src.services.fragrance_generation.generate_fragrance",
        lambda bad, judge_feedback=None: sample_fragrance,
    )
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda bad, judge_feedback=None: sample_music,
    )
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_a, **_k: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=False,
                music_aligns_descriptor=False,
                details="both off",
            ),
            summary="fail",
        ),
    )

    _fragrance, _music, report = congruence_scoring.run_specialist_congruence_loop(sample_bad)
    assert report.accepted is False
    assert report.regen_count == 1
    assert len(report.attempts) == 2

def test_specialist_loop_requires_audio_when_execution_id_set(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=0, musicgen_api_key="r8_test"),
    )
    monkeypatch.setattr(
        "src.services.fragrance_generation.generate_fragrance",
        lambda bad, judge_feedback=None: sample_fragrance,
    )
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda bad, judge_feedback=None: sample_music,
    )
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_a, **_k: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned",
        ),
    )
    monkeypatch.setattr(
        "src.services.audio_synthesis.synthesize_audio",
        lambda *_a, **_k: None,
    )

    with pytest.raises(RuntimeError, match="MusicGen audio is required"):
        congruence_scoring.run_specialist_congruence_loop(
            sample_bad,
            execution_id="Indomie_001",
        )


def test_specialist_loop_can_keep_existing_fragrance(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=0),
    )
    frag_calls = {"n": 0}

    def _frag(*_a, **_k):
        frag_calls["n"] += 1
        return sample_fragrance

    monkeypatch.setattr("src.services.fragrance_generation.generate_fragrance", _frag)
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda bad, judge_feedback=None: sample_music.model_copy(update={"style": "new"}),
    )
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_a, **_k: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned",
            accepted=True,
        ),
    )

    kept = sample_fragrance.model_copy(update={"smell_signature": "keep"})
    fragrance, music, report = congruence_scoring.run_specialist_congruence_loop(
        sample_bad,
        existing_fragrance=kept,
        regenerate=frozenset({"music"}),
    )
    assert frag_calls["n"] == 0
    assert fragrance.smell_signature == "keep"
    assert music.style == "new"
    assert report.accepted is True
