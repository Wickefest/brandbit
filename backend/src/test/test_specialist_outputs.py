# Tests writing fragrance and music specialist JSON side files.
# Checks that save_specialist_outputs creates the expected output paths.
from pathlib import Path
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection
from src.services.specialist_outputs import save_specialist_outputs



def test_save_specialist_outputs(tmp_path):
    settings = type(
        "S",
        (),
        {
            "fragrance_output_dir": str(tmp_path / "fragrance"),
            "musicgen_output_dir": str(tmp_path / "music"),
        },
    )()
    fragrance = FragranceConcept(
        top_notes=["citrus"],
        heart_notes=["rose"],
        base_notes=["musk"],
        dominant_accords=["floral"],
        intensity_profile="moderate",
        emotional_descriptors=["fresh"],
        smell_signature="A bright floral test scent.",
    )
    music = MusicDirection(
        tempo="moderate",
        bpm=96,
        timbre=["warm"],
        instrumentation=["piano"],
        mood="calm",
        style="ambient",
    )
    paths = save_specialist_outputs("Test_001", fragrance, music, settings)
    assert Path(paths["fragrance_path"]).is_file()
    assert Path(paths["music_path"]).is_file()
    assert "rose" in Path(paths["fragrance_path"]).read_text(encoding="utf-8")
    assert "ambient" in Path(paths["music_path"]).read_text(encoding="utf-8")
