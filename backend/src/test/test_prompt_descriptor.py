# Tests Prompt Only brand descriptor building from visual analysis.
# Checks field pass through and brand item override without a language model.
from src.models.descriptor import ColorTemperature, EnergyLevel
from src.models.visual_analysis import VisualAnalysis
from src.services.prompt_descriptor import build_descriptor_from_visual



def test_build_descriptor_from_visual_passes_through_llm_fields():
    visual = VisualAnalysis(
        primary_subject="water bottle",
        dominant_colours=["crystal aquamarine", "soft frost white"],
        objects=["bottle", "cap"],
        mood_indicators=["refreshing", "open-air calm"],
        energy=EnergyLevel.LOW,
        color_temperature=ColorTemperature.COOL,
        composition_style="centered product shot",
        textures=["smooth", "reflective"],
    )
    bad = build_descriptor_from_visual(visual)
    assert bad.brand_item == "water bottle"
    assert bad.mood == ["refreshing", "open-air calm"]
    assert bad.colours == ["crystal aquamarine", "soft frost white"]
    assert bad.texture == ["smooth", "reflective"]
    assert bad.energy == EnergyLevel.LOW
    assert bad.color_temperature == ColorTemperature.COOL
    assert bad.visual_style[0] == "centered product shot"
    assert "crystal aquamarine" in bad.narrative

def test_brand_item_override_keeps_vision_judgement():
    visual = VisualAnalysis(
        primary_subject="bottle",
        dominant_colours=["burnished gold leaf"],
        objects=["bottle"],
        mood_indicators=["ceremonial"],
        energy=EnergyLevel.HIGH,
        color_temperature=ColorTemperature.WARM,
        composition_style="studio",
        textures=["matte"],
    )
    bad = build_descriptor_from_visual(visual, brand_item="luxury flask")
    assert bad.brand_item == "luxury flask"
    assert bad.colours == ["burnished gold leaf"]
    assert bad.energy == EnergyLevel.HIGH
    assert bad.color_temperature == ColorTemperature.WARM
