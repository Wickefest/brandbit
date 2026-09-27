# One complete pipeline run saved as a JSON execution record.
# Holds the brand descriptor fragrance music rationale congruence and refinement history.

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

from src.models.descriptor import BrandAestheticDescriptor
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection
from src.models.congruence import CongruenceReport

class PipelineExecutionRecord(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    input_image_ref: str
    brand_aesthetic_descriptor: BrandAestheticDescriptor
    fragrance_concept: FragranceConcept
    music_direction: MusicDirection
    audio_sample_ref: Optional[str] = None
    rationale: str
    congruence_report: CongruenceReport
    mode: str = "sensory_profile"
    refinement_history: List[dict] = Field(default_factory=list)