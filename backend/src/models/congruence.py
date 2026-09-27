# Results of congruence judging including scores attempts and optional CLIP proxies.
# Accepted means both fragrance and music were judged as fitting the brand descriptor.

from pydantic import BaseModel, Field

class AutomatedProxySignals(BaseModel):
    clip_score_image_fragrance_text: float | None = None
    clip_score_image_music_text: float | None = None
    imagebind_score_image_audio: float | None = None

class DescriptorConsistency(BaseModel):
    fragrance_aligns_descriptor: bool
    music_aligns_descriptor: bool
    details: str
    fragrance_score: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Judge 1-5 fit of fragrance vs BAD (4+ = pass)",
    )
    music_score: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Judge 1-5 fit of music vs BAD (4+ = pass)",
    )
    fragrance_issues: list[str] = Field(default_factory=list)
    music_issues: list[str] = Field(default_factory=list)

class CongruenceAttempt(BaseModel):
                                                          

    attempt: int
    fragrance_aligns_descriptor: bool
    music_aligns_descriptor: bool
    details: str
    summary: str
    regenerated: list[str] = Field(default_factory=list)

class CongruenceReport(BaseModel):
    automated_proxies: AutomatedProxySignals
    descriptor_consistency: DescriptorConsistency
    human_ratings: dict | None = None
    summary: str
    attempts: list[CongruenceAttempt] = Field(default_factory=list)
    regen_count: int = 0
    accepted: bool = True
