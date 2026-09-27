# Tests vision response cleaning parsing and bakeoff payload scoring.
# Covers valid JSON parse failures and schema failures without live API calls.
from __future__ import annotations
import json
from src.services.visual_analysis import (
    _parse_visual_analysis,
    evaluate_bakeoff_payload,
    evaluate_model_text,
)


_VALID = {
    "primary_subject": "bottled water",
    "dominant_colours": ["clear blue"],
    "objects": ["cap", "label"],
    "mood_indicators": ["fresh"],
    "energy": "moderate",
    "color_temperature": "cool",
    "composition_style": "centered product shot",
    "textures": ["smooth plastic"],
}

def test_evaluate_model_text_all_ok():
    visual, rel = evaluate_model_text(json.dumps(_VALID))
    assert visual is not None
    assert rel.run_ok and rel.parse_ok and rel.schema_ok and rel.all_ok

def test_evaluate_model_text_parse_fail():
    visual, rel = evaluate_model_text("not json {{{")
    assert visual is None
    assert rel.run_ok
    assert not rel.parse_ok
    assert not rel.schema_ok

def test_evaluate_model_text_schema_fail():
    visual, rel = evaluate_model_text(json.dumps({"primary_subject": "only this"}))
    assert visual is None
    assert rel.run_ok
    assert rel.parse_ok
    assert not rel.schema_ok

def test_parse_visual_analysis_raises_on_bad_json():
    try:
        _parse_visual_analysis("not json")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "invalid JSON" in str(e)

def test_evaluate_bakeoff_run_fail():
    _, rel = evaluate_bakeoff_payload({"error": "Replicate timeout", "visual_analysis": None})
    assert not rel.run_ok
    assert not rel.parse_ok
    assert not rel.schema_ok

def test_evaluate_bakeoff_parse_fail():
    _, rel = evaluate_bakeoff_payload(
        {
            "visual_analysis": None,
            "parse_error": "Expecting value",
            "raw_text": "oops",
        }
    )
    assert rel.run_ok
    assert not rel.parse_ok
    assert not rel.schema_ok

def test_evaluate_bakeoff_schema_fail_with_raw_text_still_parse_ok():
                                                                                         
    _, rel = evaluate_bakeoff_payload(
        {
            "visual_analysis": {"primary_subject": "watch"},
            "schema_error": "missing fields",
            "raw_text": '{"primary_subject": "watch"}',
        }
    )
    assert rel.run_ok
    assert rel.parse_ok
    assert not rel.schema_ok
