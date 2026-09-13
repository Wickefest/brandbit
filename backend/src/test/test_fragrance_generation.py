# Tests fragrance specialist generation grounding and fallbacks.
# Uses fake retrieval and a fake model client without live API calls.
from __future__ import annotations
import pytest
from src.config import Settings
from src.models.fragrance import FragranceConcept, IntensityProfile
from src.services import fragrance_generation
from src.services.pyrfume_catalog import IngredientRecord, RetrievalResult
from src.test.conftest import install_fake_openai

def _records() -> list[IngredientRecord]:
    return [
        IngredientRecord(
            name="bergamot oil",
            display_name="Bergamot",
            descriptors=("citrus", "fresh"),
            sources=("goodscents",),
        ),
        IngredientRecord(
            name="jasmine absolute",
            display_name="Jasmine",
            descriptors=("floral", "rich"),
            sources=("leffingwell",),
        ),
        IngredientRecord(
            name="sandalwood oil",
            display_name="Sandalwood",
            descriptors=("woody", "creamy"),
            sources=("ifra_2019",),
        ),
        IngredientRecord(
            name="vanilla absolute",
            display_name="Vanilla",
            descriptors=("sweet", "warm"),
            sources=("goodscents",),
        ),
        IngredientRecord(
            name="cedarwood oil",
            display_name="Cedarwood",
            descriptors=("woody", "dry"),
            sources=("leffingwell",),
        ),
        IngredientRecord(
            name="rose otto",
            display_name="Rose",
            descriptors=("floral", "romantic"),
            sources=("goodscents",),
        ),
        IngredientRecord(
            name="menthyl acetate",
            display_name="menthyl acetate",
            descriptors=("minty", "cooling", "fresh"),
            sources=("goodscents",),
        ),
    ]

def test_concept_from_retrieval_uses_ingredient_descriptors():
    names = ["Bergamot", "Jasmine", "Sandalwood"]
    records = [
        IngredientRecord(
            name="bergamot oil",
            display_name="Bergamot",
            descriptors=("citrus", "fresh"),
            sources=("goodscents",),
        ),
        IngredientRecord(
            name="jasmine absolute",
            display_name="Jasmine",
            descriptors=("floral", "rich"),
            sources=("leffingwell",),
        ),
        IngredientRecord(
            name="sandalwood oil",
            display_name="Sandalwood",
            descriptors=("woody", "creamy"),
            sources=("ifra_2019",),
        ),
    ]
    concept = fragrance_generation._concept_from_retrieval(
        names,
        ingredients=records,
        mood=["calm", "intimate"],
    )
    assert "floral" not in concept.dominant_accords
    assert "woody" not in concept.dominant_accords
    assert set(concept.dominant_accords) <= {"citrus", "rich", "creamy"}
    assert concept.emotional_descriptors == ["calm", "intimate"]


def test_concept_from_retrieval_builds_pyramid():
    names = ["Bergamot", "Jasmine", "Sandalwood", "Vanilla", "Cedarwood", "Rose"]
    concept = fragrance_generation._concept_from_retrieval(names)
    assert concept.top_notes == ["Bergamot", "Jasmine"]
    assert "Sandalwood" in concept.heart_notes
    assert concept.grounded_notes
    assert concept.intensity_profile == IntensityProfile.MODERATE

def test_concept_from_retrieval_requires_enough_materials():
    with pytest.raises(RuntimeError, match="not enough"):
        fragrance_generation._concept_from_retrieval(["Bergamot", "Jasmine"])

def test_validate_grounding_resolves_display_names():
    allowed = fragrance_generation._allowed_name_map(_records())
    concept = FragranceConcept(
        top_notes=["bergamot oil"],
        heart_notes=["jasmine absolute"],
        base_notes=["sandalwood oil"],
        dominant_accords=["floral"],
        intensity_profile=IntensityProfile.LIGHT,
        emotional_descriptors=["soft"],
        grounded_notes=[],
    )
    grounded = fragrance_generation._validate_grounding(concept, allowed)
    assert grounded.top_notes == ["Bergamot"]
    assert grounded.heart_notes == ["Jasmine"]
    assert grounded.base_notes == ["Sandalwood"]
    assert grounded.grounded_notes == ["Bergamot", "Jasmine", "Sandalwood"]

def test_validate_grounding_falls_back_when_notes_ungrounded():
    allowed = fragrance_generation._allowed_name_map(_records())
    concept = FragranceConcept(
        top_notes=["unicorn dust"],
        heart_notes=["dragon scale"],
        base_notes=["phoenix ash"],
        dominant_accords=["fantasy"],
        intensity_profile=IntensityProfile.BOLD,
        emotional_descriptors=["wild"],
        grounded_notes=[],
    )
    grounded = fragrance_generation._validate_grounding(concept, allowed)
    assert grounded.grounded_notes
    assert "unicorn dust" not in grounded.top_notes

def test_validate_grounding_drops_odor_class_words():
    allowed = fragrance_generation._allowed_name_map(_records())
    concept = FragranceConcept(
        top_notes=["refreshing odor", "Bergamot"],
        heart_notes=["marine"],
        base_notes=["ozonic"],
        dominant_accords=["fresh"],
        intensity_profile=IntensityProfile.MODERATE,
        emotional_descriptors=["clean"],
        grounded_notes=[],
    )
    grounded = fragrance_generation._validate_grounding(concept, allowed)
    pyramid = [
        n.lower()
        for n in [*grounded.top_notes, *grounded.heart_notes, *grounded.base_notes]
    ]
    assert "refreshing odor" not in pyramid
    assert "marine" not in pyramid
    assert "ozonic" not in pyramid
    assert "bergamot" in pyramid
    assert all(n in {r.display_name.lower() for r in _records()} for n in pyramid)

def test_enrich_readability_builds_signature_and_keeps_material_names():
    records = _records()
    concept = FragranceConcept(
        top_notes=["menthyl acetate"],
        heart_notes=["Jasmine"],
        base_notes=["Sandalwood"],
        dominant_accords=["fresh", "clean"],
        intensity_profile=IntensityProfile.MODERATE,
        emotional_descriptors=["cool"],
        smell_signature="",
        note_guide=[],
        grounded_notes=["menthyl acetate", "Jasmine", "Sandalwood"],
    )
    enriched = fragrance_generation._enrich_readability(concept, records)
    assert "smell" in enriched.smell_signature.lower()
    assert len(enriched.smell_signature) > 80
    assert enriched.top_notes[0].lower() == "menthyl acetate"
    assert "refreshing" not in enriched.top_notes[0].lower()
    assert enriched.note_guide
    assert all(entry.smells_like for entry in enriched.note_guide)
    assert all(entry.chemical_name for entry in enriched.note_guide)
    assert not fragrance_generation._looks_chemical(enriched.note_guide[0].smells_like)

def test_generate_fragrance_with_mocked_llm(sample_bad, monkeypatch):
    retrieval = RetrievalResult(
        ingredients=_records(),
        query="hushed luxury",
        datasets=["goodscents", "leffingwell", "ifra_2019"],
    )
    monkeypatch.setattr(fragrance_generation, "retrieve_ingredients", lambda *_a, **_k: retrieval)
    monkeypatch.setattr(
        fragrance_generation,
        "_get_settings",
        lambda: Settings(kimi_api_key="test-key"),
    )
    install_fake_openai(
        monkeypatch,
        {
            "top_notes": ["Bergamot"],
            "heart_notes": ["Jasmine"],
            "base_notes": ["Sandalwood"],
            "dominant_accords": ["floral", "woody"],
            "intensity_profile": "moderate",
            "emotional_descriptors": ["intimate"],
            "smell_signature": (
                "Combined together, these ingredients will smell like a bright citrus-floral "
                "blend with a creamy woody dry-down. Think of a quiet luxury perfume brief."
            ),
            "note_guide": [
                {"ingredient": "Bergamot", "smells_like": "bright citrus peel"},
                {"ingredient": "Jasmine", "smells_like": "sweet white floral"},
                {"ingredient": "Sandalwood", "smells_like": "creamy warm wood"},
            ],
            "grounded_notes": ["Bergamot", "Jasmine", "Sandalwood"],
        },
    )

    concept = fragrance_generation.generate_fragrance(sample_bad)
    assert concept.top_notes == ["Bergamot"]
    assert concept.pyrfume_sources == retrieval.datasets
    assert "Jasmine" in concept.grounded_notes
    assert "smell" in concept.smell_signature.lower()
    assert len(concept.smell_signature) > 80
    assert len(concept.note_guide) >= 3
