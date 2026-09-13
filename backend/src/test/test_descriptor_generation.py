# Tests brand descriptor generation parsing and retry behavior.
# Uses a fake chat completion so no live GPT call is required.
from __future__ import annotations
import json
from src.config import Settings
from src.services import descriptor_generation
from src.services.llm_chat import TextRole


def _valid_bad_json(**overrides):
    payload = {
        "brand_item": "skincare bottle",
        "mood": ["serene clarity"],
        "energy": "low",
        "color_temperature": "cool",
        "colours": ["frosted clear", "pale mint"],
        "texture": ["frosted glass"],
        "visual_style": ["clinical minimal"],
        "sensory_metaphors": ["mountain mist"],
        "narrative": "A clean, quiet skincare object with cool restraint.",
    }
    payload.update(overrides)
    return payload

def _install_fake_chat(monkeypatch, content: str | dict | list):
                                                               
    responses = content if isinstance(content, list) else [content]
    call_idx = {"i": 0}

    def _fake(role, *, system, user, temperature=0.3, max_tokens=1024, settings=None):
        assert role in (TextRole.DESCRIPTOR, "descriptor")
        idx = call_idx["i"]
        call_idx["i"] += 1
        item = responses[min(idx, len(responses) - 1)]
        if isinstance(item, dict):
            return json.dumps(item)
        return str(item)

    monkeypatch.setattr("src.services.llm_chat.chat_completion", _fake)
    monkeypatch.setattr(
        "src.services.llm_chat.require_role_credentials",
        lambda *a, **k: None,
    )
    return call_idx

def test_generate_descriptor_parses_valid_response(sample_visual, monkeypatch):
    monkeypatch.setattr(
        descriptor_generation,
        "_get_settings",
        lambda: Settings(descriptor_generation_max_retries=1, musicgen_api_key="r8_test"),
    )
    _install_fake_chat(monkeypatch, _valid_bad_json())

    descriptor = descriptor_generation.generate_descriptor(sample_visual)
    assert descriptor.brand_item == "skincare bottle"
    assert descriptor.energy.value == "low"
    assert "serene clarity" in descriptor.mood

def test_generate_descriptor_applies_brand_item_override(sample_visual, monkeypatch):
    monkeypatch.setattr(
        descriptor_generation,
        "_get_settings",
        lambda: Settings(descriptor_generation_max_retries=1, musicgen_api_key="r8_test"),
    )
    _install_fake_chat(monkeypatch, _valid_bad_json(brand_item="ignored label"))

    descriptor = descriptor_generation.generate_descriptor(
        sample_visual,
        brand_item="user wristwatch",
    )
    assert descriptor.brand_item == "user wristwatch"

def test_generate_descriptor_drops_legacy_modality_fields(sample_visual, monkeypatch):
    monkeypatch.setattr(
        descriptor_generation,
        "_get_settings",
        lambda: Settings(descriptor_generation_max_retries=1, musicgen_api_key="r8_test"),
    )
    _install_fake_chat(
        monkeypatch,
        {
            **_valid_bad_json(),
            "scent_family": "floral",
            "music_direction": "ambient",
            "brand_name": "should be ignored when brand_item present",
        },
    )

    descriptor = descriptor_generation.generate_descriptor(sample_visual)
    dumped = descriptor.model_dump()
    assert "scent_family" not in dumped
    assert "music_direction" not in dumped
    assert descriptor.brand_item == "skincare bottle"

def test_generate_descriptor_retries_then_succeeds(sample_visual, monkeypatch):
    monkeypatch.setattr(
        descriptor_generation,
        "_get_settings",
        lambda: Settings(descriptor_generation_max_retries=3, musicgen_api_key="r8_test"),
    )
    call_idx = _install_fake_chat(monkeypatch, ["not-json", _valid_bad_json()])

    descriptor = descriptor_generation.generate_descriptor(sample_visual)
    assert descriptor.brand_item == "skincare bottle"
    assert call_idx["i"] >= 2
