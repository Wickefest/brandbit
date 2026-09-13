# Tests MusicGen prompt building backend resolution and audio path helpers.
# Covers off backend skip and safe output path joining.
from __future__ import annotations
import pytest
from src.config import Settings
from src.models.descriptor import (
    BrandAestheticDescriptor,
    ColorTemperature,
    EnergyLevel,
)
from src.models.music import MusicDirection
from src.services.audio_synthesis import (
    audio_api_path,
    audio_file_path,
    build_musicgen_prompt,
    resolve_backend,
    synthesize_audio,
)



def _sample_direction() -> MusicDirection:
    return MusicDirection(
        tempo="slow",
        bpm=72,
        timbre=["warm pads", "soft strings"],
        instrumentation=["piano", "synth pads"],
        mood="contemplative",
        style="ambient",
        music_signature=(
            "Hushed linen-room ambient: slow piano and warm pads, intimate rather than lobby-luxe."
        ),
    )

def _sample_bad() -> BrandAestheticDescriptor:
    return BrandAestheticDescriptor(
        brand_item="linen home fragrance bottle",
        mood=["hushed luxury"],
        energy=EnergyLevel.LOW,
        color_temperature=ColorTemperature.WARM,
        colours=["warm ivory", "soft amber"],
        texture=["soft linen"],
        visual_style=["minimal luxury"],
        sensory_metaphors=["velvet dusk"],
        narrative="Quiet warm luxury.",
    )

def test_build_musicgen_prompt_includes_brand_and_direction():
    prompt = build_musicgen_prompt(_sample_direction(), _sample_bad())
    assert "ambient" in prompt
    assert "contemplative" in prompt
    assert "72 BPM" in prompt
    assert "linen home fragrance bottle" in prompt
    assert "hushed luxury" in prompt
    assert "linen-room" in prompt

def test_resolve_backend_off_by_default():
    settings = Settings(
        musicgen_backend="auto",
        musicgen_api_key="",
        musicgen_remote_url="",
    )
    assert resolve_backend(settings) == "off"

def test_resolve_backend_replicate_when_token_set():
    settings = Settings(
        musicgen_backend="auto",
        musicgen_api_key="test-token",
    )
    assert resolve_backend(settings) == "replicate"

def test_synthesize_audio_writes_wav(tmp_path, monkeypatch):
    settings = Settings(
        musicgen_backend="replicate",
        musicgen_api_key="test-token",
        musicgen_output_dir=str(tmp_path),
    )

    def fake_replicate(_prompt: str, _settings: Settings) -> bytes:
        return b"RIFFfake-wav-data"

    monkeypatch.setattr(
        "src.services.audio_synthesis._synthesize_replicate",
        fake_replicate,
    )

    execution_id = "test-exec-123"
    ref = synthesize_audio(_sample_direction(), execution_id, bad=_sample_bad(), settings=settings)

    assert ref == "/api/audio/test-exec-123"
    output = audio_file_path(execution_id, settings)
    assert output.exists()
    assert output.read_bytes() == b"RIFFfake-wav-data"

def test_audio_api_path_encodes_mode_suffix():
    assert audio_api_path("Indomie_001") == "/api/audio/Indomie_001"
    assert audio_api_path("Indomie_001 (Prompt Only)") == (
        "/api/audio/Indomie_001%20%28Prompt%20Only%29"
    )
    assert audio_api_path("Indomie_001 (BAD)") == "/api/audio/Indomie_001%20%28BAD%29"

def test_synthesize_audio_returns_none_when_disabled():
    settings = Settings(musicgen_backend="off")
    ref = synthesize_audio(_sample_direction(), "exec-1", settings=settings)
    assert ref is None
