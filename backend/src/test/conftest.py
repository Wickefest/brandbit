# Shared pytest fixtures and helpers for Brandbit backend unit tests.
# Provides sample brand descriptor visual fragrance and music objects
# plus a fake OpenAI client installer for specialist call tests.
from __future__ import annotations
import json
from typing import Any
import pytest
from src.models.descriptor import (
    BrandAestheticDescriptor,
    ColorTemperature,
    EnergyLevel,
)
from src.models.fragrance import FragranceConcept, IntensityProfile, NoteGuideEntry
from src.models.music import MusicDirection
from src.models.visual_analysis import VisualAnalysis


# Shared sample brand aesthetic descriptor used across offline unit tests.
@pytest.fixture
def sample_bad() -> BrandAestheticDescriptor:
    return BrandAestheticDescriptor(
        brand_item="linen home fragrance bottle",
        mood=["hushed luxury", "intimate warmth"],
        energy=EnergyLevel.LOW,
        color_temperature=ColorTemperature.WARM,
        colours=["warm ivory", "soft amber"],
        texture=["soft matte linen", "polished stone"],
        visual_style=["minimal luxury"],
        sensory_metaphors=["velvet dusk", "warm amber glow"],
        narrative="A restrained luxury brand with soft warm florals.",
    )

# Shared sample visual analysis used when testing descriptor and pipeline helpers.
@pytest.fixture
def sample_visual() -> VisualAnalysis:
    return VisualAnalysis(
        primary_subject="linen home fragrance bottle",
        dominant_colours=["warm ivory", "soft amber"],
        objects=["bottle", "linen cloth"],
        mood_indicators=["calm", "intimate"],
        energy=EnergyLevel.LOW,
        color_temperature=ColorTemperature.WARM,
        composition_style="centered product with soft negative space",
        textures=["matte glass", "woven linen"],
    )

# Shared sample fragrance concept used by congruence and specialist tests.
@pytest.fixture
def sample_fragrance() -> FragranceConcept:
    return FragranceConcept(
        top_notes=["bergamot"],
        heart_notes=["jasmine"],
        base_notes=["sandalwood"],
        dominant_accords=["floral", "woody"],
        intensity_profile=IntensityProfile.MODERATE,
        emotional_descriptors=["intimate", "elegant"],
        smell_signature=(
            "Combined together, these ingredients will smell like a bright citrus-floral blend "
            "with a creamy woody dry-down. Think of a quiet luxury perfume that opens fresh "
            "and settles into soft sandalwood warmth."
        ),
        note_guide=[
            NoteGuideEntry(ingredient="bergamot", smells_like="bright citrus peel"),
            NoteGuideEntry(ingredient="jasmine", smells_like="sweet white floral"),
            NoteGuideEntry(ingredient="sandalwood", smells_like="creamy warm wood"),
        ],
        grounded_notes=["bergamot", "jasmine", "sandalwood"],
        pyrfume_sources=["goodscents"],
    )

# Shared sample music direction used by congruence and specialist tests.
@pytest.fixture
def sample_music() -> MusicDirection:
    return MusicDirection(
        tempo="slow",
        bpm=72,
        timbre=["warm pads", "soft strings"],
        instrumentation=["piano", "synth pads"],
        mood="contemplative",
        style="ambient",
        music_signature=(
            "This is the hush of a linen-lined room at dusk: slow piano over warm pads, "
            "no crowd, no lobby sparkle. It should feel intimate and textile, like cloth "
            "settling in warm light."
        ),
    )

class FakeOpenAI:
                                                                      

    def __init__(self, content: str | dict[str, Any]):
        if isinstance(content, dict):
            content = json.dumps(content)
        self._content = content
        self.chat = self
        self.completions = self
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any):
        self.calls.append(kwargs)

        class _Msg:
            def __init__(self, text: str):
                self.content = text

        class _Choice:
            def __init__(self, text: str):
                self.message = _Msg(text)

        class _Resp:
            def __init__(self, text: str):
                self.choices = [_Choice(text)]

        return _Resp(self._content)

    def __call__(self, *args: Any, **kwargs: Any):
        return self

# Installs a fake OpenAI style client so specialist tests can run offline.
def install_fake_openai(monkeypatch: pytest.MonkeyPatch, content: str | dict[str, Any]) -> FakeOpenAI:
    fake = FakeOpenAI(content)

    class _Factory:
        def __new__(cls, *args: Any, **kwargs: Any):
            return fake

    monkeypatch.setattr("openai.OpenAI", _Factory)
    return fake
