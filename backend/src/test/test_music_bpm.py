# Tests MusicDirection BPM requirements and tempo based inference.
# Covers new payloads and legacy payloads that omit bpm.
from src.models.music import MusicDirection, _bpm_from_tempo_label


def test_bpm_required_on_new_direction():
    music = MusicDirection(
        tempo="moderate",
        bpm=104,
        timbre=["bright"],
        instrumentation=["marimba"],
        mood="refreshing",
        style="minimal-clean",
    )
    assert music.bpm == 104

def test_legacy_payload_without_bpm_infers_from_tempo():
    music = MusicDirection.model_validate(
        {
            "tempo": "slow",
            "timbre": ["warm pads"],
            "instrumentation": ["piano"],
            "mood": "calm",
            "style": "ambient",
        }
    )
    assert music.bpm == 72

def test_bpm_from_tempo_label_bands():
    assert _bpm_from_tempo_label("very slow") == 60
    assert _bpm_from_tempo_label("slow") == 72
    assert _bpm_from_tempo_label("moderate") == 96
    assert _bpm_from_tempo_label("uptempo") == 128
