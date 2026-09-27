# Tests deterministic congruence rule checks for energy mood and intensity.
# Flags hard clashes before the language model judge runs.
from __future__ import annotations
from src.models.descriptor import ColorTemperature, EnergyLevel
from src.models.fragrance import IntensityProfile, NoteGuideEntry
from src.services.congruence_rules import run_rule_checks



def test_rule_flags_high_energy_slow_tempo(sample_bad, sample_fragrance, sample_music):
    bad = sample_bad.model_copy(update={"energy": EnergyLevel.HIGH})
    music = sample_music.model_copy(update={"tempo": "slow", "style": "ambient"})
    rules = run_rule_checks(bad, sample_fragrance, music)
    assert rules.critical_music_fail is True
    assert any("tempo" in i.lower() for i in rules.music_issues)

def test_rule_flags_low_energy_bold_fragrance(sample_bad, sample_fragrance, sample_music):
    bad = sample_bad.model_copy(update={"energy": EnergyLevel.LOW})
    fragrance = sample_fragrance.model_copy(update={"intensity_profile": IntensityProfile.BOLD})
    rules = run_rule_checks(bad, fragrance, sample_music)
    assert rules.critical_fragrance_fail is True
    assert any("intensity" in i.lower() for i in rules.fragrance_issues)

def test_rule_flags_calm_bad_aggressive_music(sample_bad, sample_fragrance, sample_music):
    bad = sample_bad.model_copy(update={"mood": ["calm", "serene"]})
    music = sample_music.model_copy(
        update={"style": "techno", "instrumentation": ["synth", "kick drum"]}
    )
    rules = run_rule_checks(bad, sample_fragrance, music)
    assert rules.critical_music_fail is True

def test_rule_passes_aligned_outputs(sample_bad, sample_fragrance, sample_music):
    bad = sample_bad.model_copy(update={"energy": EnergyLevel.LOW, "mood": ["calm"]})
    fragrance = sample_fragrance.model_copy(update={"intensity_profile": IntensityProfile.LIGHT})
    music = sample_music.model_copy(update={"tempo": "slow", "style": "ambient", "mood": "calm"})
    rules = run_rule_checks(bad, fragrance, music)
    assert rules.critical_fragrance_fail is False
    assert rules.critical_music_fail is False

def test_soft_cool_warm_fragrance_flag(sample_bad, sample_fragrance, sample_music):
    bad = sample_bad.model_copy(update={"color_temperature": ColorTemperature.COOL})
    fragrance = sample_fragrance.model_copy(
        update={
            "dominant_accords": ["cozy warmth", "amber warmth"],
            "emotional_descriptors": ["warm"],
            "top_notes": ["amber"],
            "heart_notes": ["vanilla"],
            "base_notes": ["musk"],
            "smell_signature": "Smells like cozy amber warmth and soft vanilla musk.",
            "note_guide": [
                NoteGuideEntry(ingredient="amber", smells_like="warm resin"),
                NoteGuideEntry(ingredient="vanilla", smells_like="sweet vanilla"),
                NoteGuideEntry(ingredient="musk", smells_like="soft musk"),
            ],
        }
    )
    rules = run_rule_checks(bad, fragrance, sample_music)
    assert any("cool" in i.lower() for i in rules.fragrance_issues)
    assert rules.critical_fragrance_fail is False
