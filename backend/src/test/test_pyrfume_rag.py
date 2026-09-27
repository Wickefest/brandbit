# Tests Pyrfume catalog filtering query building and retrieval behavior.
# Uses sample ingredients and a live cache load check when available.
from __future__ import annotations
import pytest
from src.models.descriptor import (
    BrandAestheticDescriptor,
    ColorTemperature,
    EnergyLevel,
)
from src.services.pyrfume_catalog import (
    IngredientRecord,
    LsaKnnRetriever,
    build_query,
    filter_material_records,
    is_odor_class_label,
    retrieve_ingredients,
)



def _sample_bad(**overrides) -> BrandAestheticDescriptor:
    payload = {
        "brand_item": "linen home fragrance bottle",
        "mood": ["hushed luxury", "intimate warmth"],
        "energy": EnergyLevel.LOW,
        "color_temperature": ColorTemperature.WARM,
        "colours": ["warm ivory", "soft amber"],
        "texture": ["soft matte linen", "polished stone"],
        "visual_style": ["minimal luxury"],
        "sensory_metaphors": ["velvet dusk", "warm amber glow", "soft floral hush"],
        "narrative": "A restrained luxury brand with soft warm florals.",
    }
    payload.update(overrides)
    return BrandAestheticDescriptor(**payload)

def _tiny_catalog():
    from src.services.pyrfume_catalog import IngredientRecord

    return [
        IngredientRecord("bergamot oil", "Bergamot", ("citrus", "fresh", "bright"), ("goodscents",)),
        IngredientRecord("jasmine absolute", "Jasmine", ("floral", "rich", "white flower"), ("leffingwell",)),
        IngredientRecord("rose otto", "Rose", ("floral", "romantic", "petal"), ("goodscents",)),
        IngredientRecord("sandalwood oil", "Sandalwood", ("woody", "creamy", "warm"), ("ifra_2019",)),
        IngredientRecord("cedarwood oil", "Cedarwood", ("woody", "dry"), ("leffingwell",)),
        IngredientRecord("vanilla absolute", "Vanilla", ("sweet", "warm", "gourmand"), ("goodscents",)),
        IngredientRecord("peppermint oil", "Peppermint", ("mint", "cool", "fresh"), ("goodscents",)),
        IngredientRecord("oakmoss", "Oakmoss", ("earthy", "mossy", "woody"), ("ifra_2019",)),
    ]

def test_lsa_knn_retrieves_floral_neighbors():
    bad = _sample_bad(
        mood=["soft floral hush"],
        sensory_metaphors=["rose petal dusk"],
        narrative="Quiet luxury with soft warm florals.",
    )
    retriever = LsaKnnRetriever(_tiny_catalog())
    result = retriever.retrieve_for_profile(bad, top_k=4)
    assert result.ingredients
    joined = " ".join(record.search_text for record in result.ingredients)
    assert any(term in joined for term in ("floral", "rose", "jasmine", "petal"))

@pytest.fixture(scope="module")
def catalog_records():
    from src.config import Settings
    from src.services.pyrfume_catalog import build_catalog, load_catalog_cache

    settings = Settings()
    cached = load_catalog_cache(settings.pyrfume_catalog_cache_path)
    if cached:
        return cached
    return build_catalog(settings.pyrfume_datasets)

def test_display_name_is_molecule_name_not_odor_tag():
    from src.services.pyrfume_catalog import IngredientRecord, _derive_display_name

    chemical = "(1r,2s,4r)-(+)-bornyl acetate"
    assert _derive_display_name(chemical, ("camphoreous", "woody", "cool")) == chemical
    record = IngredientRecord(
        chemical,
        _derive_display_name(chemical, ("camphoreous",)),
        ("camphoreous", "woody"),
        ("goodscents",),
        cid=443131,
    )
    kept = filter_material_records([record])
    assert kept == [record]
    assert kept[0].display_name == chemical
    assert "camphoreous" in kept[0].descriptors

def test_odor_class_labels_are_not_selectable_ingredients():
    from src.services.pyrfume_catalog import IngredientRecord

    assert is_odor_class_label("refreshing odor")
    assert is_odor_class_label("marine")
    assert is_odor_class_label("woody")
    assert is_odor_class_label("ozonic")
    assert is_odor_class_label("cool")
    assert is_odor_class_label("watery")
    assert is_odor_class_label("phenolic")
    assert is_odor_class_label("cortex")
    assert is_odor_class_label("minty")
    assert is_odor_class_label("cherry")
    assert not is_odor_class_label("sandalwood")
    assert not is_odor_class_label("menthyl formate")
    assert not is_odor_class_label("gamma-terpinene")
    assert not is_odor_class_label("eucalyptus")
    assert not is_odor_class_label("cashmeran")

    junk = [
        IngredientRecord("refreshing odor", "refreshing odor", ("fresh",), ("goodscents",)),
        IngredientRecord("cool", "cool", ("mint",), ("goodscents",)),
        IngredientRecord("zinc2242754", "zinc2242754", ("woody",), ("goodscents",)),
        IngredientRecord("almond bitter almond", "almond bitter almond", ("nutty",), ("goodscents",)),
        IngredientRecord("herbal green", "herbal green", ("green",), ("leffingwell",)),
        IngredientRecord("musk like", "musk like", ("musky",), ("ifra_2019",)),
        IngredientRecord("caramellic", "caramellic", ("sweet",), ("goodscents",)),
    ]
    real = [
        IngredientRecord("sandalwood oil", "Sandalwood", ("woody", "creamy"), ("ifra_2019",)),
        IngredientRecord("peppermint oil", "Peppermint oil", ("mint", "cool"), ("goodscents",)),
        IngredientRecord("tea tree oil", "Tea tree oil", ("herbal",), ("goodscents",)),
    ]
    kept = {item.display_name for item in filter_material_records([*junk, *real])}
    assert kept == {"Sandalwood", "Peppermint oil", "Tea tree oil"}

def test_build_query_includes_mood_and_metaphors():
    bad = _sample_bad()
    query = build_query(bad)
    assert "hushed luxury" in query
    assert "velvet dusk" in query
    assert "florals" in query
    assert "scent_family" not in query

def test_retriever_returns_relevant_floral_materials(catalog_records):
    bad = _sample_bad(
        mood=["soft floral hush", "intimate warmth"],
        sensory_metaphors=["rose petal dusk", "velvet bloom"],
        narrative="Quiet luxury with soft warm florals and petal-like textures.",
    )
    retriever = LsaKnnRetriever(catalog_records)
    result = retriever.retrieve_for_profile(bad, top_k=15)

    assert result.ingredients
    joined = " ".join(record.search_text for record in result.ingredients)
    assert any(term in joined for term in ("floral", "rose", "jasmine", "petal"))

def test_retrieve_ingredients_tracks_sources(catalog_records, monkeypatch):
    from src.services import pyrfume_catalog

    monkeypatch.setattr(
        pyrfume_catalog,
        "get_pyrfume_retriever",
        lambda *_args, **_kwargs: LsaKnnRetriever(catalog_records),
    )

    result = retrieve_ingredients(_sample_bad())
    assert result.ingredients
    assert result.datasets
