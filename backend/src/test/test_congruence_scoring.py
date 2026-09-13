# Tests congruence judge scoring thresholds and rule overrides.
# Uses a fake judge response so no live DeepSeek call is required.
from __future__ import annotations
import json
import pytest
from src.config import Settings
from src.models.descriptor import EnergyLevel
from src.services import congruence_scoring
from src.services.llm_chat import TextRole



def _install_fake_judge(monkeypatch, content: str | dict):
    def _fake(role, *, system, user, temperature=0.3, max_tokens=1024, settings=None):
        assert role in (TextRole.JUDGE, "judge")
        if isinstance(content, dict):
            return json.dumps(content)
        return str(content)

    monkeypatch.setattr("src.services.llm_chat.chat_completion", _fake)
    monkeypatch.setattr(
        "src.services.llm_chat.require_role_credentials",
        lambda *a, **k: None,
    )

def test_compute_congruence_requires_replicate_token(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(musicgen_api_key=""),
    )
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.delenv("MUSICGEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Replicate token"):
        congruence_scoring.compute_congruence(sample_bad, sample_fragrance, sample_music)

def test_compute_congruence_parses_judge_json(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(musicgen_api_key="r8_test"),
    )
    _install_fake_judge(
        monkeypatch,
        {
            "fragrance_score": 5,
            "music_score": 2,
            "fragrance_aligns_descriptor": True,
            "music_aligns_descriptor": True,
            "fragrance_issues": [],
            "music_issues": ["Music energy feels too bright for low-energy BAD"],
            "details": "Music energy feels too bright for low-energy BAD",
            "summary": "Fragrance fits; music needs softening.",
        },
    )

    report = congruence_scoring.compute_congruence(sample_bad, sample_fragrance, sample_music)

    assert report.descriptor_consistency.fragrance_aligns_descriptor is True
    assert report.descriptor_consistency.music_aligns_descriptor is False
    assert report.descriptor_consistency.music_score == 2
    assert "Music energy" in report.descriptor_consistency.details
    assert report.descriptor_consistency.music_issues
    assert "Fragrance fits" in report.summary
    assert report.automated_proxies.clip_score_image_fragrance_text is None

def test_build_regen_feedback_targets_failed_modality(sample_bad):
    from src.models.congruence import DescriptorConsistency

    consistency = DescriptorConsistency(
        fragrance_aligns_descriptor=True,
        music_aligns_descriptor=False,
        details="music too fast",
        music_score=2,
        music_issues=["tempo too fast for low energy"],
    )
    feedback = congruence_scoring.build_regen_feedback(consistency, "summary")
    assert "MUSIC REJECTED" in feedback
    assert "tempo too fast" in feedback
    assert "FRAGRANCE REJECTED" not in feedback

def test_critical_rule_overrides_lenient_judge(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    bad = sample_bad.model_copy(update={"energy": EnergyLevel.HIGH})
    music = sample_music.model_copy(update={"tempo": "slow", "style": "ambient"})
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(musicgen_api_key="r8_test"),
    )
    _install_fake_judge(
        monkeypatch,
        {
            "fragrance_score": 5,
            "music_score": 5,
            "fragrance_aligns_descriptor": True,
            "music_aligns_descriptor": True,
            "fragrance_issues": [],
            "music_issues": [],
            "details": "all good",
            "summary": "aligned",
        },
    )

    report = congruence_scoring.compute_congruence(bad, sample_fragrance, music)
    assert report.descriptor_consistency.music_aligns_descriptor is False
    assert report.descriptor_consistency.music_score <= 2

def test_compute_congruence_strips_markdown_fence(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(musicgen_api_key="r8_test"),
    )
    _install_fake_judge(
        monkeypatch,
        '```json\n{"fragrance_aligns_descriptor": true, '
        '"music_aligns_descriptor": true, "details": "ok", "summary": "aligned"}\n```',
    )

    report = congruence_scoring.compute_congruence(sample_bad, sample_fragrance, sample_music)
    assert report.descriptor_consistency.music_aligns_descriptor is True
    assert report.summary == "aligned"
