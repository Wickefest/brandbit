# Builds a brand descriptor directly from visual analysis without a language model.

from __future__ import annotations

from src.models.descriptor import BrandAestheticDescriptor
from src.models.visual_analysis import VisualAnalysis


# Deduplicates trims and caps a string list with an optional fallback.
def _clip_list(values: list[str], *, fallback: str | None = None, limit: int = 10) -> list[str]:
    cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for item in cleaned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    if not out and fallback:
        return [fallback]
    return out


# Maps vision fields onto a brand descriptor with a short template narrative.
def build_descriptor_from_visual(
    visual: VisualAnalysis,
    *,
    brand_item: str | None = None,
) -> BrandAestheticDescriptor:
    item = (brand_item or visual.primary_subject or "").strip() or "brand object"
    moods = _clip_list(list(visual.mood_indicators), fallback="neutral", limit=5)
    textures = _clip_list(list(visual.textures), fallback="unspecified", limit=5)
    colours = _clip_list(list(visual.dominant_colours), fallback="unspecified", limit=10)

    # Start visual style with composition then add non subject objects.
    styles: list[str] = []
    if visual.composition_style and visual.composition_style.strip():
        styles.append(visual.composition_style.strip())
    for obj in visual.objects:
        token = obj.strip()
        if not token or token.lower() == item.lower():
            continue
        if token.lower() in {s.lower() for s in styles}:
            continue
        styles.append(token)
        if len(styles) >= 5:
            break
    if not styles:
        styles = ["photographic"]

    narrative = (
        f"Direct image parse of {item}. "
        f"Colours: {', '.join(colours)}. "
        f"Composition: {visual.composition_style.strip() or 'unspecified'}. "
        f"Atmosphere: {', '.join(moods)}. "
        f"Surface cues: {', '.join(textures)}."
    )

    return BrandAestheticDescriptor(
        brand_item=item,
        mood=moods,
        energy=visual.energy,
        color_temperature=visual.color_temperature,
        colours=colours,
        texture=textures,
        visual_style=styles[:5],
        sensory_metaphors=[],
        narrative=narrative,
    )
