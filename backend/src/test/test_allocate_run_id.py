# Tests execution id formatting and sequential allocate_run_id behavior.
# Covers BAD and Prompt Only suffixes and first versus later run numbers.
from __future__ import annotations
from src.config import Settings
from src.main import allocate_run_id, format_run_id



def _settings(tmp_path) -> Settings:
    return Settings(
        execution_log_dir=str(tmp_path / "result"),
        fragrance_output_dir=str(tmp_path / "fragrance"),
        musicgen_output_dir=str(tmp_path / "music"),
    )

def test_format_run_id_prompt_and_bad():
    assert format_run_id("Indomie", 1, "prompt") == "Indomie_001 (Prompt Only)"
    assert format_run_id("Indomie", 1, "bad") == "Indomie_001 (BAD)"
    assert format_run_id("Indomie", 1, "prompt_only") == "Indomie_001 (Prompt Only)"
    assert format_run_id("Indomie", 1, "sensory_profile") == "Indomie_001 (BAD)"

def test_first_run_is_001_with_mode_suffix(tmp_path):
    settings = _settings(tmp_path)
    assert (
        allocate_run_id("Indomie.jpg", "prompt", settings)
        == "Indomie_001 (Prompt Only)"
    )
    assert allocate_run_id("Indomie.jpg", "bad", settings) == "Indomie_001 (BAD)"

def test_regen_reuses_same_mode_slot_instead_of_incrementing(tmp_path):
    settings = _settings(tmp_path)
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    (result_dir / "Indomie_001 (Prompt Only).json").write_text("{}", encoding="utf-8")

    again = allocate_run_id("Indomie.jpg", "prompt", settings)
    assert again == "Indomie_001 (Prompt Only)"
    assert allocate_run_id("Indomie.jpg", "bad", settings) == "Indomie_001 (BAD)"

def test_legacy_numbered_drafts_share_001_instead_of_creating_004(tmp_path):
    settings = _settings(tmp_path)
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    for name in ("Indomie_001.json", "Indomie_002.json", "Indomie_003.json"):
        (result_dir / name).write_text("{}", encoding="utf-8")

    assert (
        allocate_run_id("Indomie.jpg", "prompt", settings)
        == "Indomie_001 (Prompt Only)"
    )
    assert allocate_run_id("Indomie.jpg", "bad", settings) == "Indomie_001 (BAD)"
