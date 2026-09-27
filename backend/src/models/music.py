# Music direction with tempo timbre instruments mood style and signature.
# Optional audio sample reference points to the generated sound file.

from pydantic import BaseModel, Field, model_validator
from typing import Any, List, Optional

def _bpm_from_tempo_label(tempo: str) -> int:
                                                                                   
    label = (tempo or "").strip().lower()
    if any(token in label for token in ("very slow", "adagio", "languid")):
        return 60
    if any(token in label for token in ("slow", "leisurely", "downtempo", "relaxed")):
        return 72
    if any(
        token in label
        for token in ("very fast", "fast", "uptempo", "up-tempo", "allegro", "brisk", "driving")
    ):
        return 128
    return 96

class MusicDirection(BaseModel):
    tempo: str
    bpm: int = Field(
        ...,
        ge=40,
        le=200,
        description="Approximate beats per minute as an integer (e.g. 72, 96, 120)",
    )
    timbre: List[str]
    instrumentation: List[str]
    mood: str
    style: str = Field(
        description=(
            "Short style label, 1-3 words, hyphenated if needed "
            "(e.g. 'ambient', 'contemporary-gamelan', 'gamelan-lounge')"
        ),
    )
    music_signature: str = Field(
        default="",
        description=(
            "2-4 sentence story of why these instruments and textures belong "
            "to this brand object/place/craft, for non-musicians"
        ),
    )
    audio_sample_ref: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _ensure_bpm(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("bpm")
        if raw in (None, ""):
            data = {**data, "bpm": _bpm_from_tempo_label(str(data.get("tempo") or ""))}
            return data
        try:
            data = {**data, "bpm": int(round(float(raw)))}
        except (TypeError, ValueError):
            data = {**data, "bpm": _bpm_from_tempo_label(str(data.get("tempo") or ""))}
        return data
