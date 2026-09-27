"""Offline artifact and failure checks for selective refinement."""
from __future__ import annotations

import hashlib
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
from src.services import audio_synthesis, congruence_scoring, evaluation_logging, refinement


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def saved_run(tmp_path, sample_bad, sample_fragrance, sample_music, monkeypatch):
    settings = Settings(
        execution_log_dir=str(tmp_path / "result"),
        fragrance_output_dir=str(tmp_path / "fragrance"),
        musicgen_output_dir=str(tmp_path / "music"),
        congruence_regen_max_retries=2,
    )
    execution_id = "Selective_001"
    audio_ref = f"/api/audio/{execution_id}"
    music = sample_music.model_copy(update={"audio_sample_ref": audio_ref})
    audio_path = audio_synthesis.audio_file_path(execution_id, settings)
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"original wav bytes")
    record = PipelineExecutionRecord(
        execution_id=execution_id,
        timestamp=datetime.now(timezone.utc),
        input_image_ref="demo.jpg",
        brand_aesthetic_descriptor=sample_bad,
        fragrance_concept=sample_fragrance,
        music_direction=music,
        audio_sample_ref=audio_ref,
        rationale="original",
        congruence_report=CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="aligned",
            ),
            summary="aligned",
        ),
    )
    evaluation_logging.log_execution(record, settings)
    monkeypatch.setattr(
        refinement, "get_execution",
        lambda run_id: evaluation_logging.get_execution(run_id, settings),
    )
    monkeypatch.setattr(
        refinement, "log_execution",
        lambda value, **kwargs: evaluation_logging.log_execution(value, settings, **kwargs),
    )
    monkeypatch.setattr(refinement, "resolve_image_bytes", lambda *_args: None)
    monkeypatch.setattr(
        "src.services.clip_proxies.compute_clip_proxies",
        lambda *_args, **_kwargs: AutomatedProxySignals(),
    )
    monkeypatch.setattr(congruence_scoring, "_get_settings", lambda: settings)
    monkeypatch.setattr(
        audio_synthesis,
        "load_audio_bytes",
        lambda run_id: (
            audio_synthesis.audio_file_path(run_id, settings).read_bytes()
            if audio_synthesis.audio_file_path(run_id, settings).exists()
            else None
        ),
    )
    monkeypatch.setattr(refinement, "generate_rationale", lambda *_args: "updated")
    return settings, record


@pytest.mark.parametrize("scope", ["fragrance", "music", "shared"])
def test_selected_outputs_change_and_retained_files_keep_hash(
    scope, saved_run, monkeypatch
):
    settings, record = saved_run
    frag_file = settings.fragrance_output_dir
    music_file = settings.musicgen_output_dir
    frag_path = Path(frag_file) / f"{record.execution_id}.json"
    music_path = Path(music_file) / f"{record.execution_id}.json"
    audio_path = audio_synthesis.audio_file_path(record.execution_id, settings)
    before = tuple(_sha(path) for path in (frag_path, music_path, audio_path))
    calls = {"fragrance": 0, "music": 0, "audio": 0}

    monkeypatch.setattr(
        refinement,
        "interpret_and_refine",
        lambda *_args: refinement.RefinementResult(
            success=True,
            target_modality=scope,
            changed_fields=["energy"],
            updated_bad=record.brand_aesthetic_descriptor.model_copy(
                update={"energy": EnergyLevel.HIGH}
            ),
        ),
    )

    def fragrance_provider(*_args, **_kwargs):
        calls["fragrance"] += 1
        return record.fragrance_concept.model_copy(update={"smell_signature": "new scent"})

    def music_provider(*_args, **_kwargs):
        calls["music"] += 1
        return record.music_direction.model_copy(
            update={"style": "new music", "audio_sample_ref": None}
        )

    def audio_provider(_direction, run_id, **_kwargs):
        calls["audio"] += 1
        path = audio_synthesis.audio_file_path(run_id, settings)
        path.write_bytes(b"new wav bytes")
        return audio_synthesis.audio_api_path(run_id)

    monkeypatch.setattr("src.services.fragrance_generation.generate_fragrance", fragrance_provider)
    monkeypatch.setattr("src.services.music_generation.generate_music_direction", music_provider)
    monkeypatch.setattr(audio_synthesis, "synthesize_audio", audio_provider)
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_args: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="aligned",
            ),
            summary="aligned",
        ),
    )

    result = refinement.run_refinement(record.execution_id, "make it more energetic")
    after = tuple(_sha(path) for path in (frag_path, music_path, audio_path))
    event = result["refinement_history"][-1]
    assert result["success"] is True
    assert calls == {
        "fragrance": int(scope in {"fragrance", "shared"}),
        "music": int(scope in {"music", "shared"}),
        "audio": int(scope in {"music", "shared"}),
    }
    assert before[2] == after[2]  # No successful refinement overwrites the original WAV.
    if scope == "fragrance":
        assert before[1] == after[1]
        assert result["audio_sample_ref"] == record.audio_sample_ref
        assert event["before_hashes"]["music"] == event["after_hashes"]["music"]
        assert event["before_hashes"]["audio"] == event["after_hashes"]["audio"]
    if scope == "music":
        assert before[0] == after[0]
        assert event["before_hashes"]["fragrance"] == event["after_hashes"]["fragrance"]
    if scope in {"music", "shared"}:
        assert result["audio_sample_ref"].endswith("__r001")
        assert audio_synthesis.audio_file_path(
            f"{record.execution_id}__r001", settings
        ).read_bytes() == b"new wav bytes"
    assert event["timings_ms"]["total_before_save"] >= 0


@pytest.mark.parametrize("failure", ["specialist", "judge", "audio", "rationale"])
def test_provider_failure_does_not_replace_saved_run(failure, saved_run, monkeypatch):
    settings, record = saved_run
    execution_path = Path(settings.execution_log_dir) / f"{record.execution_id}.json"
    before = _sha(execution_path)
    monkeypatch.setattr(
        refinement,
        "interpret_and_refine",
        lambda *_args: refinement.RefinementResult(
            success=True,
            target_modality="shared",
            changed_fields=["energy"],
            updated_bad=record.brand_aesthetic_descriptor.model_copy(
                update={"energy": EnergyLevel.HIGH}
            ),
        ),
    )

    def fail_here(stage):
        if failure == stage:
            raise RuntimeError(f"injected {stage} failure")

    def fragrance_provider(*_args, **_kwargs):
        fail_here("specialist")
        return record.fragrance_concept

    def judge(*_args):
        fail_here("judge")
        return record.congruence_report

    def audio_provider(*_args, **_kwargs):
        fail_here("audio")
        return "/api/audio/new"

    def rationale_provider(*_args):
        fail_here("rationale")
        return "updated"

    monkeypatch.setattr("src.services.fragrance_generation.generate_fragrance", fragrance_provider)
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda *_args, **_kwargs: record.music_direction,
    )
    monkeypatch.setattr(congruence_scoring, "compute_congruence", judge)
    monkeypatch.setattr(audio_synthesis, "synthesize_audio", audio_provider)
    monkeypatch.setattr(refinement, "generate_rationale", rationale_provider)

    with pytest.raises(RuntimeError):
        refinement.run_refinement(record.execution_id, "make it more energetic")
    assert _sha(execution_path) == before
    assert evaluation_logging.get_execution(record.execution_id, settings).refinement_history == []
