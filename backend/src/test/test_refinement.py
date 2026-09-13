# Tests refinement interpret and run paths with mocked specialists.
# Covers clarification failures modality targeting and execution updates.
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pytest
from src.config import Settings
from src.models.congruence import (
    AutomatedProxySignals,
    CongruenceReport,
    DescriptorConsistency,
)
from src.models.descriptor import EnergyLevel
from src.models.execution import PipelineExecutionRecord
from src.services import refinement as refinement_mod
from src.services.refinement import interpret_and_refine, run_refinement

def _congruence_ok() -> CongruenceReport:
    return CongruenceReport(
        automated_proxies=AutomatedProxySignals(),
        descriptor_consistency=DescriptorConsistency(
            fragrance_aligns_descriptor=True,
            music_aligns_descriptor=True,
            details="ok",
        ),
        summary="aligned",
        accepted=True,
        regen_count=0,
    )

def test_interpret_and_refine_updates_energy(sample_bad, monkeypatch):
    monkeypatch.setattr(
        "src.services.llm_chat.require_role_credentials",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "src.services.llm_chat.chat_completion",
        lambda *_a, **_k: (
            '{"can_interpret": true, "target_modality": "music", '
            '"changed_fields": ["energy"], "change_reason": "more drive", '
            '"updates": {"energy": "high"}, "clarification": null}'
        ),
    )

    result = interpret_and_refine("make it more energetic", sample_bad)
    assert result.success is True
    assert result.updated_bad is not None
    assert result.updated_bad.energy == EnergyLevel.HIGH
    assert "energy" in result.changed_fields

def test_interpret_and_refine_clarification(sample_bad, monkeypatch):
    monkeypatch.setattr(
        "src.services.llm_chat.require_role_credentials",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "src.services.llm_chat.chat_completion",
        lambda *_a, **_k: (
            '{"can_interpret": false, "target_modality": null, '
            '"changed_fields": [], "change_reason": "", "updates": {}, '
            '"clarification": "Which modality should change?"}'
        ),
    )

    result = interpret_and_refine("change it", sample_bad)
    assert result.success is False
    assert "modality" in (result.clarification_request or "").lower()

def test_run_refinement_happy_path(
    sample_bad,
    sample_fragrance,
    sample_music,
    tmp_path: Path,
    monkeypatch,
):
    exec_id = "Refine_Demo_001"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(
        refinement_mod,
        "_get_settings",
        lambda: Settings(execution_log_dir=str(log_dir)),
    )
    monkeypatch.setattr(
        "src.services.evaluation_logging._get_log_dir",
        lambda settings=None: log_dir,
    )

    record = PipelineExecutionRecord(
        execution_id=exec_id,
        timestamp=datetime.now(timezone.utc),
        input_image_ref="demo.jpg",
        brand_aesthetic_descriptor=sample_bad,
        fragrance_concept=sample_fragrance,
        music_direction=sample_music,
        audio_sample_ref=None,
        rationale="## Visual to Descriptor\nold",
        congruence_report=_congruence_ok(),
        refinement_history=[],
    )
    (log_dir / f"{exec_id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")

    monkeypatch.setattr(
        refinement_mod,
        "interpret_and_refine",
        lambda feedback, current_bad: refinement_mod.RefinementResult(
            success=True,
            target_modality="descriptor",
            changed_fields=["energy"],
            change_reason="user asked for higher energy",
            updated_bad=current_bad.model_copy(update={"energy": EnergyLevel.HIGH}),
        ),
    )
    monkeypatch.setattr(
        refinement_mod,
        "run_specialist_congruence_loop",
        lambda bad, execution_id=None, image_data=None, verbose=False, **_kw: (
            sample_fragrance,
            sample_music.model_copy(
                update={"audio_sample_ref": f"/api/audio/{execution_id}"}
            ),
            _congruence_ok(),
        ),
    )
    monkeypatch.setattr(
        refinement_mod,
        "generate_rationale",
        lambda *_a, **_k: "## Visual to Descriptor\nrefined",
    )

    out = run_refinement(exec_id, "make energy higher")
    assert out["success"] is True
    assert out["execution_id"] == exec_id
    assert out["brand_aesthetic_descriptor"]["energy"] == "high"
    assert out["audio_sample_ref"] == f"/api/audio/{exec_id}"
    assert len(out["refinement_history"]) == 1
    assert out["refinement"]["changed_fields"] == ["energy"]

    saved = PipelineExecutionRecord.model_validate_json(
        (log_dir / f"{exec_id}.json").read_text(encoding="utf-8")
    )
    assert saved.brand_aesthetic_descriptor.energy == EnergyLevel.HIGH
    assert len(saved.refinement_history) == 1

def test_run_refinement_selective_music_target(
    sample_bad,
    sample_fragrance,
    sample_music,
    tmp_path: Path,
    monkeypatch,
):
    exec_id = "Refine_Selective_001"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(
        refinement_mod,
        "_get_settings",
        lambda: Settings(execution_log_dir=str(log_dir)),
    )
    monkeypatch.setattr(
        "src.services.evaluation_logging._get_log_dir",
        lambda settings=None: log_dir,
    )

    kept_music = sample_music.model_copy(update={"style": "keep-me"})
    record = PipelineExecutionRecord(
        execution_id=exec_id,
        timestamp=datetime.now(timezone.utc),
        input_image_ref="demo.jpg",
        brand_aesthetic_descriptor=sample_bad,
        fragrance_concept=sample_fragrance,
        music_direction=kept_music,
        audio_sample_ref=None,
        rationale="## Visual to Descriptor\nold",
        congruence_report=_congruence_ok(),
        refinement_history=[],
    )
    (log_dir / f"{exec_id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")

    monkeypatch.setattr(
        refinement_mod,
        "interpret_and_refine",
        lambda feedback, current_bad: refinement_mod.RefinementResult(
            success=True,
            target_modality="music",
            changed_fields=["energy"],
            change_reason="more energy for music",
            updated_bad=current_bad.model_copy(update={"energy": EnergyLevel.HIGH}),
        ),
    )

    captured: dict = {}

    def _loop(bad, **kwargs):
        captured.update(kwargs)
        return (
            sample_fragrance,
            sample_music.model_copy(
                update={"style": "new-music", "audio_sample_ref": f"/api/audio/{kwargs.get('execution_id')}"}
            ),
            _congruence_ok(),
        )

    monkeypatch.setattr(refinement_mod, "run_specialist_congruence_loop", _loop)
    monkeypatch.setattr(
        refinement_mod,
        "generate_rationale",
        lambda *_a, **_k: "## Visual to Descriptor\nrefined",
    )

    out = run_refinement(exec_id, "make music more energetic")
    assert out["success"] is True
    assert out["congruence_accepted"] is True
    assert captured.get("regenerate") == frozenset({"music"})
    assert captured.get("existing_fragrance") == sample_fragrance
    assert "existing_music" not in captured or captured.get("existing_music") is None


def test_run_refinement_missing_execution(tmp_path: Path, monkeypatch):
    log_dir = tmp_path / "empty"
    log_dir.mkdir()
    monkeypatch.setattr(
        "src.services.evaluation_logging._get_log_dir",
        lambda settings=None: log_dir,
    )
    with pytest.raises(LookupError):
        run_refinement("Missing_999", "make it warmer")
