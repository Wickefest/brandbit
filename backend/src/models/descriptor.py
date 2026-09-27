# Shared brand identity that stays free of scent and music answers.
# Fragrance and music specialists invent those modalities separately.

from enum import Enum
from typing import Any, List
from pydantic import BaseModel, Field, model_validator

class EnergyLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

class ColorTemperature(str, Enum):
    COOL = "cool"
    NEUTRAL = "neutral"
    WARM = "warm"

class BrandAestheticDescriptor(BaseModel):
           

    brand_item: str = Field(
        ...,
        min_length=1,
        description=(
            "Primary product or object depicted (e.g. 'wristwatch', 'skincare bottle', "
            "'logo mark'). Modality-neutral — not a scent or music answer."
        ),
    )
    mood: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Emotional tone descriptors; free-form vivid language encouraged",
    )
    energy: EnergyLevel = Field(..., description="Ordinal energy level chosen by the model")
    color_temperature: ColorTemperature = Field(
        ..., description="Dominant color temperature chosen by the model"
    )
    colours: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Free-form dominant colour names of the brand object "
            "(e.g. 'warm ivory', 'deep forest green')"
        ),
    )
    texture: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Tactile or surface-quality descriptors; free-form",
    )
    visual_style: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Visual style tags; free-form",
    )
    sensory_metaphors: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Cross-modal bridges linking sight to other senses (not modality answers)",
    )
    narrative: str = Field(
        default="",
        description="2-3 sentence brand feeling summary for downstream generators",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_colours_alias(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("colours") and data.get("colors"):
            data = {**data, "colours": data.get("colors")}
        return data

    def to_generation_context(self) -> dict[str, Any]:
                                                                                        
        return self.model_dump(mode="json")

                                          
BrandSensoryProfile = BrandAestheticDescriptor
