# Tests brand aesthetic descriptor schema validation helpers.
# Covers valid payloads invalid enums and instance round trip checks.
from __future__ import annotations
from src.models.descriptor import BrandAestheticDescriptor
from src.services.descriptor_validation import (
    validate_descriptor,
    validate_descriptor_instance,
)


def _valid_payload(**overrides):
    payload = {
        "brand_item": "wristwatch",
        "mood": ["quiet confidence"],
        "energy": "moderate",
        "color_temperature": "cool",
        "colours": ["brushed steel", "cool grey"],
        "texture": ["brushed steel"],
        "visual_style": ["minimal"],
        "sensory_metaphors": ["frosted glass"],
        "narrative": "A precise, cool-toned luxury object.",
    }
    payload.update(overrides)
    return payload

def test_validate_descriptor_accepts_valid_payload():
    result = validate_descriptor(_valid_payload())
    assert result.is_valid
    assert result.errors == []

def test_validate_descriptor_rejects_missing_brand_item():
    payload = _valid_payload()
    del payload["brand_item"]
    result = validate_descriptor(payload)
    assert not result.is_valid
    assert any(err.field == "brand_item" for err in result.errors)

def test_validate_descriptor_rejects_invalid_energy_enum():
    result = validate_descriptor(_valid_payload(energy="sleepy"))
    assert not result.is_valid
    assert any(err.field == "energy" for err in result.errors)

def test_validate_descriptor_rejects_empty_mood():
    result = validate_descriptor(_valid_payload(mood=[]))
    assert not result.is_valid
    assert any(err.field == "mood" for err in result.errors)

def test_validate_descriptor_instance_accepts_constructed_model():
    descriptor = BrandAestheticDescriptor(**_valid_payload())
    result = validate_descriptor_instance(descriptor)
    assert result.is_valid
