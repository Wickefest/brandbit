# Saves specialist fragrance and music JSON beside execution logs.
from __future__ import annotations
from pathlib import Path
from src.config import Settings
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection
from src.services.path_safety import contained_path


def _fragrance_dir(settings: Settings) -> Path:
    return Path(settings.fragrance_output_dir)


def _music_dir(settings: Settings) -> Path:
    return Path(settings.musicgen_output_dir)


# Writes fragrance concept JSON under the fragrance output directory.
def save_fragrance_output(
    execution_id: str,
    fragrance: FragranceConcept,
    settings: Settings | None = None,
) -> Path:
    settings = settings or Settings()
    out_dir = _fragrance_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = contained_path(out_dir, execution_id, suffix=".json")
    path.write_text(fragrance.model_dump_json(indent=2), encoding="utf-8")
    return path


# Writes music direction JSON under the music output directory.
def save_music_output(
    execution_id: str,
    music: MusicDirection,
    settings: Settings | None = None,
) -> Path:
    settings = settings or Settings()
    out_dir = _music_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = contained_path(out_dir, execution_id, suffix=".json")
    path.write_text(music.model_dump_json(indent=2), encoding="utf-8")
    return path


# Saves both specialist outputs and returns their file paths.
def save_specialist_outputs(
    execution_id: str,
    fragrance: FragranceConcept,
    music: MusicDirection,
    settings: Settings | None = None,
    *,
    save_fragrance: bool = True,
    save_music: bool = True,
) -> dict[str, str]:
    settings = settings or Settings()
    paths: dict[str, str] = {}
    if save_fragrance:
        paths["fragrance_path"] = str(save_fragrance_output(execution_id, fragrance, settings))
    if save_music:
        paths["music_path"] = str(save_music_output(execution_id, music, settings))
    return paths
