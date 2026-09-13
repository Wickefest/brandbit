# Generates a three section rationale linking vision brand fragrance and music.
from __future__ import annotations
import logging
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection

logger = logging.getLogger(__name__)

# Prompt used to generate the rationale.
_SYSTEM_PROMPT = """\
You are a brand strategist writing a cross-modal rationale for a multisensory brand system.
Given a Brand Aesthetic Descriptor, FragranceConcept, and MusicDirection, write a narrative 
explanation with EXACTLY three sections using markdown ## headers:

## Visual to Descriptor
Explain how visual features led to specific BAD field values.
Reference at least one BAD field by exact name.

## Descriptor to Fragrance
Explain how BAD field values guided fragrance choices.
Reference at least one BAD field by exact name.

## Descriptor to Music
Explain how BAD field values guided music direction choices.
Reference at least one BAD field by exact name.

RULES:
- Plain prose only — no JSON
- Do NOT use markdown emphasis: no **, no __, no *italic*, no _italic_
- Do NOT use bullet lists or numbered lists
- Section headers must be exactly the three ## titles above — nowhere else
- Each section: 2-4 sentences of normal readable text
- Reference actual values from the provided data
- Do NOT add extra sections"""


def _get_settings() -> Settings:
    return Settings()


def _require_api_key(settings: Settings) -> None:
    from src.services.llm_chat import TextRole, require_role_credentials

    require_role_credentials(TextRole.SPECIALIST, settings)


# Calls the specialist model and sanitizes the narrative for display.
def generate_rationale(
    bad: BrandAestheticDescriptor,
    fragrance: FragranceConcept,
    music_direction: MusicDirection,
) -> str:
    settings = _get_settings()
    _require_api_key(settings)

    from src.services.llm_chat import TextRole, chat_completion

    user_message = (
        "Write a cross-modal rationale for the following brand concept.\n\n"
        f"## Brand Sensory Profile\n{bad.model_dump_json(indent=2)}\n\n"
        f"## Fragrance Concept\n{fragrance.model_dump_json(indent=2)}\n\n"
        f"## Music Direction\n{music_direction.model_dump_json(indent=2)}"
    )

    try:
        content = chat_completion(
            TextRole.SPECIALIST,
            system=_SYSTEM_PROMPT,
            user=user_message,
            temperature=0.6,
            max_tokens=1024,
            settings=settings,
        )
    except Exception as e:
        raise RuntimeError(f"Rationale generation failed: {e}") from e

    if not content:
        raise RuntimeError("Rationale generation returned empty response")

    from src.services.text_sanitize import plain_narrative

    # Strip markdown emphasis so the results page shows plain prose.
    return plain_narrative(content)
