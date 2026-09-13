# Structured output from the vision model for a brand image.
# Used as the first pipeline stage before building the brand aesthetic descriptor.

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, List
from pydantic import BaseModel, Field, computed_field
from src.models.descriptor import ColorTemperature, EnergyLevel

class VisualAnalysis(BaseModel):
    primary_subject: str = Field(
        ...,
        min_length=1,
        description=(
            "Main brandable product or object in the image "
            "(e.g. 'wristwatch', 'bottled water', 'sneaker', 'logo mark')"
        ),
    )
    dominant_colours: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Dominant colour descriptions of the primary subject only "
            "(not background or unrelated surroundings). Free-form — "
            "the vision model invents precise colour language."
        ),
    )
    objects: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Key objects or subjects identified in the image",
    )
    mood_indicators: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Emotional or atmospheric qualities conveyed by the image",
    )
    energy: EnergyLevel = Field(
        ...,
        description="Overall visual energy as judged by the vision model",
    )
    color_temperature: ColorTemperature = Field(
        ...,
        description="Overall colour temperature as judged by the vision model",
    )
    composition_style: str = Field(
        ...,
        description="Description of the image's compositional approach",
    )
    textures: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Textural qualities observed in the image",
    )

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> VisualAnalysis:
                                                                                
        if "visual_analysis" in data and isinstance(data["visual_analysis"], dict):
            data = data["visual_analysis"]
                                                                       
        payload = dict(data)
        payload.setdefault("energy", "moderate")
        payload.setdefault("color_temperature", "neutral")
        return cls.model_validate(payload)

    @classmethod
    def from_json_file(cls, path: str | Path) -> VisualAnalysis:
                                                                                    
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Visual JSON not found: {file_path}")
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {file_path}")
        return cls.from_payload(payload)

class VisualReliability(BaseModel):
           

    run_ok: bool = Field(
        ...,
        description="Run success — the API/model completed successfully",
    )
    parse_ok: bool = Field(
        ...,
        description="Parse success — the response could be parsed as JSON",
    )
    schema_ok: bool = Field(
        ...,
        description="Schema success — parsed object matches VisualAnalysis",
    )
    error: str | None = None

    @computed_field
    @property
    def all_ok(self) -> bool:
        return self.run_ok and self.parse_ok and self.schema_ok
