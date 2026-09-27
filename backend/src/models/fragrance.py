# Fragrance concept with pyramid notes accords intensity and smell story.
# Grounded notes and sources show which Pyrfume materials were used.

from pydantic import BaseModel, Field, model_validator
from typing import List
from enum import Enum

class IntensityProfile(str, Enum):
    LIGHT = "light"
    MODERATE = "moderate"
    BOLD = "bold"

class NoteGuideEntry(BaseModel):
                                                              

    smells_like: str = Field(
        description="Everyday odor from Pyrfume descriptors, e.g. 'cool mint'"
    )
    chemical_name: str = Field(
        default="",
        description="Pyrfume molecules.csv name used for grounding",
    )
    ingredient: str = Field(
        default="",
        description="Alias of chemical_name (older clients / tests)",
    )

    @model_validator(mode="after")
    def _sync_chemical_fields(self) -> "NoteGuideEntry":
        name = (self.chemical_name or self.ingredient).strip()
        self.chemical_name = name
        self.ingredient = name
        return self

class FragranceConcept(BaseModel):
    top_notes: List[str]
    heart_notes: List[str]
    base_notes: List[str]
    dominant_accords: List[str]
    intensity_profile: IntensityProfile
    emotional_descriptors: List[str]
    smell_signature: str = Field(
        default="",
        description=(
            "2-4 sentence plain-English scent story combining the whole formula "
            "(opening, dry-down, real-world reference) for non-experts"
        ),
    )
    note_guide: List[NoteGuideEntry] = Field(
        default_factory=list,
        description="Per note: smells_like (odor) then chemical_name (molecule)",
    )
    grounded_notes: List[str] = Field(
        default_factory=list,
        description="Ingredient names selected from Pyrfume-retrieved materials",
    )
    pyrfume_sources: List[str] = Field(
        default_factory=list,
        description="Pyrfume datasets that contributed retrieved materials",
    )
