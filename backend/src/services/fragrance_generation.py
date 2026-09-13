# Builds a grounded fragrance concept from Pyrfume retrieval and the specialist model.

from __future__ import annotations
import json
import logging
import re
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor
from src.models.fragrance import FragranceConcept, IntensityProfile, NoteGuideEntry
from src.services.pyrfume_catalog import (
    IngredientRecord,
    format_retrieval_context,
    is_selectable_ingredient,
    retrieve_ingredients,
)

logger = logging.getLogger(__name__)

# Generic odor words preferred less than specific Pyrfume smell phrases.
_GENERIC_SMELL_WORDS = frozenset(
    {
        "floral",
        "woody",
        "fresh",
        "green",
        "sweet",
        "fruity",
        "warm",
        "soft",
        "spicy",
        "aromatic",
        "balsamic",
        "earthy",
        "musky",
        "clean",
        "dry",
        "odor",
        "odour",
        "scent",
        "fragrance",
    }
)

# Prompt that requires pyramid notes to come from the retrieval list only.
_SYSTEM_PROMPT = """\
You are a professional perfumer designing a brand fragrance concept.
You MUST ground the formula in the provided Pyrfume-retrieved materials.

Return ONLY a valid JSON object:

{
  "top_notes": ["note1", "note2"],
  "heart_notes": ["note1", "note2"],
  "base_notes": ["note1", "note2"],
  "dominant_accords": ["accord1", "accord2"],
  "intensity_profile": "light | moderate | bold",
  "emotional_descriptors": ["descriptor1", "descriptor2"],
  "smell_signature": "2-4 sentence plain-English scent story for non-experts",
  "note_guide": [
    {"smells_like": "everyday odor", "chemical_name": "molecule name from the list"}
  ],
  "grounded_notes": ["note1", "note2"]
}

RULES:
- Use ONLY materials from the Pyrfume retrieval list for top_notes, heart_notes, and base_notes.
- Copy the chemical name after "chemical:" into top_notes / heart_notes / base_notes exactly.
- Do not put odor words (woody, marine, cool, minty) in the pyramid — those belong in smells_like.
- note_guide: one entry per pyramid note. smells_like = the odor line (2-6 everyday words).
  chemical_name = the same molecule name used in the pyramid.
- Never put raw chemistry jargon in smell_signature or smells_like.
- Never put raw chemistry jargon (CAS-like names, acetate/oxide/formate spellings) in smell_signature or smells_like.
- Every note in top/heart/base MUST appear in grounded_notes.
- grounded_notes MUST match display names or canonical names from the retrieval list exactly.
- Assign notes to top/heart/base using standard perfumery volatility:
  top = citrus, aldehydes, light herbs; heart = florals, spices; base = woods, resins, musks, vanillas.
- dominant_accords: 1-5 overall scent impressions drawn from retrieved descriptors.
- intensity_profile: exactly one of light, moderate, bold — align with brand energy.
- emotional_descriptors: 1-5 qualities linking brand mood to the formula.
- smell_signature: a short creative brief (2-4 sentences) that COMBINES the whole formula into one
  imagined smell. Cover opening → dry-down, overall character, and a real-world reference
  (spa product, cafe, botanical perfume, etc.). Write for a normal person, not a chemist.
  Example tone: "Combined together, these ingredients will smell like a frosty, medicinal
  citrus-mint blend with a heavy, sweet floral undertone. Think of an upscale therapeutic
  spa product that opens with icy freshness and dries down into a rich floral scent."
- note_guide: one entry for EVERY top/heart/base ingredient. smells_like must be 2-6 everyday words
  (e.g. "cool mint", "sweet jasmine", "warm amber resin") — never the chemical name alone.
  chemical_name must repeat the pyramid molecule name.
- Return ONLY valid JSON, no markdown fencing, no explanation."""

FRAGRANCE_SYSTEM_PROMPT = _SYSTEM_PROMPT


# Builds the fragrance user message from the brand descriptor and retrieval list.
def build_fragrance_user_message(
    bad: BrandAestheticDescriptor,
    retrieval_context: str,
    judge_feedback: str | None = None,
) -> str:
    profile = bad.to_generation_context()
    user_message = (
        "Create a grounded fragrance concept for this modality-neutral brand aesthetic "
        "descriptor. Infer accords and intensity from mood/energy/colours/texture/narrative — "
        "the profile does not prescribe a scent family.\n\n"
        f"Brand Aesthetic Descriptor:\n{json.dumps(profile, indent=2)}\n\n"
        f"{retrieval_context}\n\n"
        "Select the best-fitting materials from the retrieval list and structure them "
        "into a professional top/heart/base formula. Also write smell_signature as a 2-4 "
        "sentence combined scent story (opening → dry-down + real-world reference), and "
        "note_guide with short everyday analogies per ingredient."
    )
    if judge_feedback and judge_feedback.strip():
        user_message += (
            "\n\nA congruence judge rejected the previous fragrance concept. "
            "Revise so the formula better fits the descriptor. Judge feedback:\n"
            f"{judge_feedback.strip()}"
        )
    return user_message


# Finds pyramid notes that are not in the allowed Pyrfume name map.
def ungrounded_notes(
    concept: FragranceConcept,
    allowed_map: dict[str, str],
) -> list[str]:
    missing: list[str] = []
    for note in [*concept.top_notes, *concept.heart_notes, *concept.base_notes]:
        if allowed_map.get(_normalize_note(note)) is None:
            missing.append(note)
    return missing


def _get_settings() -> Settings:
    return Settings()


# Detects names that look like chemistry jargon rather than everyday smell words.
def _looks_chemical(name: str) -> bool:
    lowered = name.strip().lower()
    if re.search(r"\d", lowered) and ("-" in lowered or "(" in lowered):
        return True
    if any(
        token in lowered
        for token in (
            "acetate",
            "oxide",
            "formate",
            "alcohol",
            "aldehyde",
            "ketone",
            "lactone",
            "ester",
        )
    ):
        return True
    if len(lowered) > 28 and " " not in lowered.strip():
        return True
    return False


# Chooses a readable smell phrase for a retrieved ingredient.
def _pick_smell_phrase(record: IngredientRecord | None, fallback_name: str) -> str:
    if record is None:
        return fallback_name.strip().lower() or "a soft scent"

    specific = [
        d.strip().lower()
        for d in record.descriptors
        if d.strip() and d.strip().lower() not in _GENERIC_SMELL_WORDS and len(d.strip()) <= 40
    ]
    generic = [
        d.strip().lower()
        for d in record.descriptors
        if d.strip() and d.strip().lower() in _GENERIC_SMELL_WORDS
    ]

    if specific:
        phrase = ", ".join(specific[:2])
    elif generic:
        phrase = ", ".join(generic[:2])
    elif not _looks_chemical(record.display_name):
        phrase = record.display_name.strip().lower()
    else:
        phrase = "a soft scent"

    return phrase


def _record_lookup(records: list[IngredientRecord]) -> dict[str, IngredientRecord]:
    mapping: dict[str, IngredientRecord] = {}
    for record in records:
        for label in (record.display_name, record.name):
            mapping[_normalize_note(label)] = record
    return mapping


# Normalizes notes rebuilds the note guide and fills a readable smell signature.
def _enrich_readability(
    concept: FragranceConcept,
    records: list[IngredientRecord],
) -> FragranceConcept:
    by_name = _record_lookup(records)
    selected = list(
        dict.fromkeys([*concept.top_notes, *concept.heart_notes, *concept.base_notes])
    )

    def material_label(note: str) -> str:
        record = by_name.get(_normalize_note(note))
        if record is None:
            return note
        return record.display_name

    concept.top_notes = [material_label(n) for n in concept.top_notes]
    concept.heart_notes = [material_label(n) for n in concept.heart_notes]
    concept.base_notes = [material_label(n) for n in concept.base_notes]
    concept.grounded_notes = [material_label(n) for n in selected]

    # Keep model smell phrases when readable otherwise prefer Pyrfume descriptors.
    guide_by_ingredient: dict[str, NoteGuideEntry] = {}
    for entry in concept.note_guide:
        key = _normalize_note(entry.chemical_name or entry.ingredient)
        smells = entry.smells_like.strip()
        if smells and not _looks_chemical(smells):
            guide_by_ingredient[key] = NoteGuideEntry(
                smells_like=smells.lower(),
                chemical_name=material_label(entry.ingredient or entry.chemical_name),
            )

    ordered_notes = list(
        dict.fromkeys([*concept.top_notes, *concept.heart_notes, *concept.base_notes])
    )
    enriched_guide: list[NoteGuideEntry] = []
    for note in ordered_notes:
        key = _normalize_note(note)
        existing = guide_by_ingredient.get(key)
        record = by_name.get(key)
        if record is None:
            for original in selected:
                if material_label(original) == note:
                    record = by_name.get(_normalize_note(original))
                    break
        pyrfume_smell = _pick_smell_phrase(record, note)
        smells = pyrfume_smell
        if (
            (not smells or smells == "a soft scent")
            and existing
            and existing.smells_like
        ):
            smells = existing.smells_like
        enriched_guide.append(
            NoteGuideEntry(smells_like=smells, chemical_name=note)
        )
    concept.note_guide = enriched_guide

    signature = (concept.smell_signature or "").strip()
    if not signature or _looks_chemical(signature):
        analogies = [entry.smells_like for entry in enriched_guide[:3] if entry.smells_like]
        accords = [a.strip().lower() for a in concept.dominant_accords[:3] if a.strip()]
        intensity = concept.intensity_profile.value
        if analogies:
            opening = analogies[0]
            mid = analogies[1] if len(analogies) > 1 else None
            base = analogies[2] if len(analogies) > 2 else None
            character = ", ".join(accords) if accords else "balanced"
            dry = f" and dries down into {base}" if base else ""
            mid_bit = f" with {mid}" if mid else ""
            signature = (
                f"Combined together, these ingredients will smell like a {character} blend "
                f"that opens with {opening}{mid_bit}{dry}. "
                f"Think of a {intensity}-intensity scent concept a creative team could brief "
                f"to a perfumer — evocative, wearable, and brand-led."
            )
        elif accords:
            signature = (
                f"Combined together, these ingredients will smell like a {accords[0]} fragrance "
                f"with a {intensity} presence. Think of an early-stage brand scent brief rather "
                f"than a finished bottle."
            )
        else:
            signature = (
                "Combined together, these ingredients will smell like a soft, balanced brand scent. "
                "Think of an early creative perfume brief for the visual identity."
            )

    concept.smell_signature = signature
    return concept


# Builds a fallback fragrance concept from retrieved materials only.
def _fallback_accords_and_emotions(
    retrieval_names: list[str],
    *,
    ingredients: list[IngredientRecord] | None = None,
    mood: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    counts: dict[str, int] = {}
    if ingredients:
        wanted = {_normalize_note(n) for n in retrieval_names}
        for record in ingredients:
            labels = {_normalize_note(record.display_name), _normalize_note(record.name)}
            if wanted.isdisjoint(labels):
                continue
            for descriptor in record.descriptors:
                token = descriptor.strip().lower()
                if not token or token in _GENERIC_SMELL_WORDS:
                    continue
                counts[token] = counts.get(token, 0) + 1

    accords = [token for token, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
    emotions = [m.strip() for m in (mood or []) if m and m.strip()][:3]
    return accords, emotions


def _concept_from_retrieval(
    retrieval_names: list[str],
    *,
    ingredients: list[IngredientRecord] | None = None,
    mood: list[str] | None = None,
) -> FragranceConcept:
    names = retrieval_names or []
    if len(names) < 3:
        raise RuntimeError(
            "Fragrance grounding failed: not enough retrieved Pyrfume materials to fall back on."
        )
    top = names[:2]
    heart = names[2:4] if len(names) > 2 else names[:1]
    base = names[4:6] if len(names) > 4 else names[-2:]
    grounded = list(dict.fromkeys([*top, *heart, *base]))
    accords, emotions = _fallback_accords_and_emotions(
        grounded,
        ingredients=ingredients,
        mood=mood,
    )

    return FragranceConcept(
        top_notes=top,
        heart_notes=heart,
        base_notes=base,
        dominant_accords=accords,
        intensity_profile=IntensityProfile.MODERATE,
        emotional_descriptors=emotions,
        smell_signature="",
        note_guide=[],
        grounded_notes=grounded,
        pyrfume_sources=["goodscents", "leffingwell", "ifra_2019"],
    )


def _require_api_key(settings: Settings) -> None:
    from src.services.llm_chat import TextRole, require_role_credentials

    require_role_credentials(TextRole.SPECIALIST, settings)


# Maps normalized labels to display names for selectable retrieved materials.
def _allowed_name_map(records) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for record in records:
        if not is_selectable_ingredient(record):
            continue
        for label in (record.display_name, record.name):
            mapping[_normalize_note(label)] = record.display_name
    return mapping


def _fill_from_retrieval(resolved: list[str], unused: list[str], minimum: int = 1) -> list[str]:
    filled = list(dict.fromkeys(resolved))
    for name in unused:
        if len(filled) >= minimum:
            break
        if name not in filled:
            filled.append(name)
    return filled or unused[:minimum]


# Remaps model notes onto retrieval display names.
# Every pyramid note must come from the allowed material list.
def _validate_grounding(
    concept: FragranceConcept,
    allowed_map: dict[str, str],
    *,
    ingredients: list[IngredientRecord] | None = None,
    mood: list[str] | None = None,
) -> FragranceConcept:
    def resolve_note(note: str) -> str | None:
        return allowed_map.get(_normalize_note(note))

    pool = list(dict.fromkeys(allowed_map.values()))
    selected_notes = [*concept.top_notes, *concept.heart_notes, *concept.base_notes]
    grounded: list[str] = []
    for note in selected_notes:
        resolved = resolve_note(note)
        if resolved and resolved not in grounded:
            grounded.append(resolved)

    if not grounded:
        # If notes are ungrounded discard them and rebuild from retrieval.
        fallback = pool[:6]
        logger.warning("LLM notes not grounded — falling back to top retrieved materials")
        concept = _concept_from_retrieval(
            fallback,
            ingredients=ingredients,
            mood=mood,
        )
        concept.grounded_notes = fallback[: len(concept.grounded_notes) or len(fallback)]
        return concept

    unused = [name for name in pool if name not in grounded]
    top = _fill_from_retrieval(
        [resolve_note(note) for note in concept.top_notes if resolve_note(note)],
        unused,
        minimum=1,
    )
    used = set(top)
    unused = [name for name in pool if name not in used]
    heart = _fill_from_retrieval(
        [resolve_note(note) for note in concept.heart_notes if resolve_note(note)],
        unused,
        minimum=1,
    )
    used.update(heart)
    unused = [name for name in pool if name not in used]
    base = _fill_from_retrieval(
        [resolve_note(note) for note in concept.base_notes if resolve_note(note)],
        unused,
        minimum=1,
    )

    concept.top_notes = top
    concept.heart_notes = heart
    concept.base_notes = base
    concept.grounded_notes = list(dict.fromkeys([*top, *heart, *base]))
    return concept


def _normalize_note(note: str) -> str:
    return " ".join(note.strip().lower().split())


# Retrieves materials calls the model grounds notes and returns a fragrance concept.
def generate_fragrance(
    bad: BrandAestheticDescriptor,
    judge_feedback: str | None = None,
) -> FragranceConcept:
    settings = _get_settings()

    try:
        retrieval = retrieve_ingredients(bad, settings)
    except Exception as e:
        logger.error("Pyrfume retrieval failed: %s", e)
        raise RuntimeError(f"Pyrfume retrieval failed: {e}") from e

    allowed_map = _allowed_name_map(retrieval.ingredients)
    retrieval_context = format_retrieval_context(retrieval)
    _require_api_key(settings)

    from src.services.llm_chat import TextRole, chat_completion

    user_message = build_fragrance_user_message(
        bad, retrieval_context, judge_feedback=judge_feedback
    )

    try:
        content = chat_completion(
            TextRole.SPECIALIST,
            system=_SYSTEM_PROMPT,
            user=user_message,
            temperature=0.4,
            max_tokens=2400,
            settings=settings,
        )
    except Exception as e:
        raise RuntimeError(f"Fragrance generation failed: {e}") from e

    if not content:
        raise RuntimeError("Fragrance generation returned empty response")

    cleaned = content.strip().strip("```").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Fragrance generation returned invalid JSON: {content[:200]}") from e

    try:
        concept = FragranceConcept(**data)
    except Exception as e:
        raise RuntimeError(f"Fragrance response does not match schema: {e}") from e

    concept = _validate_grounding(
        concept,
        allowed_map,
        ingredients=retrieval.ingredients,
        mood=list(bad.mood or []),
    )
    concept = _enrich_readability(concept, retrieval.ingredients)
    concept.pyrfume_sources = retrieval.datasets
    return concept
