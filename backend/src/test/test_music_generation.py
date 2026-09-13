# Tests music specialist generation with a fake model client.
# Covers missing API key parsing and optional audio synthesis skip.
from __future__ import annotations
import pytest
from src.config import Settings
from src.services import music_generation
from src.test.conftest import install_fake_openai

def test_generate_music_requires_api_key(sample_bad, monkeypatch):
    monkeypatch.setattr(
        music_generation,
        "_get_settings",
        lambda: Settings(kimi_api_key=""),
    )
    with pytest.raises(RuntimeError, match="KIMI_API_KEY"):
        music_generation.generate_music(sample_bad)

def test_generate_music_parses_direction(sample_bad, monkeypatch):
    monkeypatch.setattr(
        music_generation,
        "_get_settings",
        lambda: Settings(kimi_api_key="test-key"),
    )
    install_fake_openai(
        monkeypatch,
        {
            "tempo": "slow",
            "bpm": 72,
            "timbre": ["warm pads"],
            "instrumentation": ["piano"],
            "mood": "contemplative",
            "style": "ambient",
            "music_signature": (
                "Quiet linen-room pads and piano. Intimate textile hush, not a hotel lobby."
            ),
        },
    )

    direction = music_generation.generate_music(sample_bad)
    assert direction.tempo == "slow"
    assert direction.bpm == 72
    assert direction.style == "ambient"
    assert "linen-room" in direction.music_signature
    assert direction.audio_sample_ref is None

def test_generate_music_attaches_audio_ref_when_synthesis_succeeds(sample_bad, monkeypatch):
    monkeypatch.setattr(
        music_generation,
        "_get_settings",
        lambda: Settings(kimi_api_key="test-key"),
    )
    install_fake_openai(
        monkeypatch,
        {
            "tempo": "moderate",
            "bpm": 100,
            "timbre": ["bright synths"],
            "instrumentation": ["synth pads"],
            "mood": "uplifting",
            "style": "minimal",
        },
    )
    monkeypatch.setattr(
        music_generation,
        "synthesize_audio",
        lambda *_a, **_k: "/api/audio/exec-1",
    )

    direction = music_generation.generate_music(sample_bad, execution_id="exec-1")
    assert direction.audio_sample_ref == "/api/audio/exec-1"

def test_generate_music_requires_audio_when_execution_id_set(sample_bad, monkeypatch):
    monkeypatch.setattr(
        music_generation,
        "_get_settings",
        lambda: Settings(kimi_api_key="test-key"),
    )
    install_fake_openai(
        monkeypatch,
        {
            "tempo": "slow",
            "bpm": 68,
            "timbre": ["soft strings"],
            "instrumentation": ["cello"],
            "mood": "calm",
            "style": "neo-classical",
        },
    )

    def boom(*_a, **_k):
        raise RuntimeError("GPU unavailable")

    monkeypatch.setattr(music_generation, "synthesize_audio", boom)

    with pytest.raises(RuntimeError, match="GPU unavailable"):
        music_generation.generate_music(sample_bad, execution_id="exec-2")

def test_music_prompt_asks_for_sound_world_and_signature(sample_bad):
    system = music_generation.MUSIC_SYSTEM_PROMPT
    user = music_generation.build_music_user_message(sample_bad)
    lowered = system.lower()
    assert "music_signature" in lowered
    assert "contemporary-gamelan" in lowered
    assert "suling" in lowered
    assert "bpm" in lowered
    assert "single word genre" not in lowered
    assert "sound world" in user.lower()
    assert "luxury-lobby" in user or "luxury lobby" in user
    assert "music_signature" in user
    assert "bpm" in user.lower()
    assert "generation model.\n\nBrand Aesthetic Descriptor:" in user
    assert '"rock"' in system or "rock\"" in system
    assert '"rock.' not in system
