# Turns visual analysis into a modality neutral brand aesthetic descriptor.
# Must not invent scent families or music directions.
from __future__ import annotations
import json
import logging
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor
from src.models.visual_analysis import VisualAnalysis

logger = logging.getLogger(__name__)

# Prompt for producing brand descriptor JSON without scent or music answers.
_SYSTEM_PROMPT = """\
You are a brand aesthetics analyst. Given structured visual features extracted from\
a brand image, produce a modality-neutral Brand Aesthetic Descriptor (BAD) as JSON.

The BAD is a shared brand identity — NOT a fragrance brief and NOT a music brief.
Do NOT invent scent families, perfume notes, tempo, instrumentation, genre, or other
modality-specific answers. Downstream specialists derive those independently.

Return ONLY a valid JSON object with these exact fields:

{
  "brand_item": "...",
  "mood": ["...", "..."],
  "energy": "...",
  "color_temperature": "...",
  "colours": ["...", "..."],
  "texture": ["...", "..."],
  "visual_style": ["...", "..."],
  "sensory_metaphors": ["...", "..."],
  "narrative": "..."
}

FIELD CONSTRAINTS:

0. brand_item (string) — what the product/object IS (e.g. "wristwatch", "skincare bottle",
   "sneaker", "logo mark", "bottled water"). Prefer visual_analysis.primary_subject; refine only for clarity.
   Do NOT use perfume categories (eau de parfum, cologne) unless the image literally shows
   that product. Do not invent a brand company name.
1. mood (array of 1-5 strings) — vivid, specific emotional language.
   Invent precise terms when needed (e.g. "hushed luxury", "frosted calm").
2. energy (string) — MUST be one of: very_low, low, moderate, high, very_high
   Use the vision model's energy judgement as a strong prior; refine only if the overall
   brand reading clearly differs.
3. color_temperature (string) — MUST be one of: cool, neutral, warm
   Use the vision model's color_temperature judgement as a strong prior.
4. colours (array of 1-10 strings) — free-form dominant colour names of the brand object.
   Prefer visual_analysis.dominant_colours; refine wording only for clarity.
   Prefer the form "Colour name (#RRGGBB)" when a hex is known (count may be 1–10, not fixed).
   Do NOT constrain colours to a fixed palette vocabulary.
5. texture (array of 1-5 strings) — tactile or surface qualities; free-form.
6. visual_style (array of 1-5 strings) — aesthetic tags; free-form.
7. sensory_metaphors (array of 0-5 strings) — cross-modal bridges that suggest feeling
   without prescribing a scent family or music direction
   (e.g. "velvet dusk", "glassine brightness", "mountain mist").
8. narrative (string) — 2-3 sentences capturing the brand's overall feeling in
   modality-neutral language. Do not name perfume families or musical genres.
   Mention the brand_item and key colours naturally.

Prefer specificity over generic tags. Return ONLY valid JSON, no markdown fencing, no explanation."""

# Public alias of the descriptor system prompt for evaluation scripts.
BAD_SYSTEM_PROMPT = _SYSTEM_PROMPT


# Builds the descriptor user message from visual analysis and optional brand item.
def build_bad_user_message(
    visual_analysis: VisualAnalysis,
    brand_item: str | None = None,
) -> str:
    va_json = visual_analysis.model_dump_json(indent=2)
    user_message = (
        "Based on the following visual analysis of a brand image, "
        "generate a Brand Aesthetic Descriptor.\n\n"
        f"Detected primary_subject (use as brand_item unless a known override is given): "
        f"{visual_analysis.primary_subject}\n\n"
    )
    if brand_item:
        user_message += f"Known brand_item (use exactly): {brand_item}\n\n"
    user_message += f"Visual Analysis:\n{va_json}"
    return user_message


# Parses model JSON into a brand descriptor and backfills missing vision fields.
def parse_bad_response(
    content: str,
    visual_analysis: VisualAnalysis,
    brand_item: str | None = None,
) -> BrandAestheticDescriptor:
    if not content or not str(content).strip():
        raise RuntimeError("Descriptor generation returned empty response")

    cleaned = str(content).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Descriptor generation returned invalid JSON: {str(content)[:200]}"
        ) from e

    if not isinstance(data, dict):
        raise RuntimeError("Descriptor generation returned a non-object JSON value")

    # Drop modality specific leaks and normalize field aliases.
    data.pop("scent_family", None)
    data.pop("music_direction", None)
    if "brand_item" not in data and data.get("brand_name"):
        data["brand_item"] = data.pop("brand_name")
    else:
        data.pop("brand_name", None)

    if not data.get("colours") and data.get("colors"):
        data["colours"] = data.get("colors")
    if not data.get("colours") and visual_analysis.dominant_colours:
        data["colours"] = list(visual_analysis.dominant_colours)
    if not data.get("energy"):
        data["energy"] = visual_analysis.energy.value
    if not data.get("color_temperature"):
        data["color_temperature"] = visual_analysis.color_temperature.value

    try:
        descriptor = BrandAestheticDescriptor(**data)
    except Exception as e:
        raise RuntimeError(f"Descriptor does not match schema: {e}") from e

    if brand_item:
        descriptor = descriptor.model_copy(update={"brand_item": brand_item.strip()})
    elif not (descriptor.brand_item and descriptor.brand_item.strip()):
        descriptor = descriptor.model_copy(
            update={"brand_item": visual_analysis.primary_subject.strip()}
        )
    return descriptor


def _get_settings() -> Settings:
    return Settings()


def _require_credentials(settings: Settings) -> None:
    from src.services.llm_chat import TextRole, require_role_credentials

    require_role_credentials(TextRole.DESCRIPTOR, settings)


# Makes one descriptor model call and parses the response.
def _call_llm(
    visual_analysis: VisualAnalysis,
    settings: Settings,
    temperature: float = 0.0,
    brand_item: str | None = None,
) -> BrandAestheticDescriptor:
    from src.services.llm_chat import TextRole, chat_completion

    user_message = build_bad_user_message(visual_analysis, brand_item=brand_item)
    try:
        content = chat_completion(
            TextRole.DESCRIPTOR,
            system=_SYSTEM_PROMPT,
            user=user_message,
            temperature=temperature,
            max_tokens=1500,
            settings=settings,
        )
    except Exception as e:
        raise RuntimeError(f"Descriptor generation failed: {e}") from e

    return parse_bad_response(content or "", visual_analysis, brand_item=brand_item)


# Retries descriptor generation until schema validation passes.
def generate_descriptor(
    visual_analysis: VisualAnalysis,
    brand_item: str | None = None,
) -> BrandAestheticDescriptor:
    settings = _get_settings()
    _require_credentials(settings)

    max_retries = settings.descriptor_generation_max_retries
    last_error = None
    temperatures = [0.3, 0.5, 0.7]

    for attempt in range(1, max_retries + 1):
        temperature = temperatures[min(attempt - 1, len(temperatures) - 1)]
        try:
            logger.info(
                "Descriptor generation (GPT-4o) attempt %d/%d (temperature=%.1f)",
                attempt,
                max_retries,
                temperature,
            )
            descriptor = _call_llm(
                visual_analysis,
                settings,
                temperature=temperature,
                brand_item=brand_item,
            )

            from src.services.descriptor_validation import validate_descriptor_instance

            validation = validate_descriptor_instance(descriptor)

            if validation.is_valid:
                return descriptor

            invalid_details = "; ".join(
                f"{e.field}: {e.reason}" for e in validation.errors
            )
            logger.warning("Attempt %d schema invalid: %s", attempt, invalid_details)
            last_error = RuntimeError(f"Schema validation failed: {invalid_details}")

        except RuntimeError as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)

    raise RuntimeError(
        f"Descriptor generation failed after {max_retries} attempts: {last_error}"
    )


# Command line helper to generate a brand descriptor from vision JSON or an image.
def _main() -> int:
    import argparse
    from pathlib import Path

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None:
        backend_root = Path(__file__).resolve().parents[2]
        for env_path in (backend_root / ".env", backend_root.parent / ".env"):
            if env_path.is_file():
                load_dotenv(env_path, override=False)

    parser = argparse.ArgumentParser(
        description="Generate Brand Aesthetic Descriptor (BAD) from vision JSON or image"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--from-json",
        type=Path,
        help="Frozen visual JSON (../eval/comparison/vlm/qwen/*.json or bare visual object)",
    )
    src.add_argument(
        "--image",
        type=Path,
        help="Live image — runs Qwen vision first, then BAD (not for text bake-off)",
    )
    parser.add_argument(
        "brand_item",
        nargs="?",
        default=None,
        help="Optional brand_item override",
    )
    args = parser.parse_args()
    brand_item = args.brand_item.strip() if args.brand_item else None

    try:
        if args.from_json is not None:
            json_path = args.from_json.expanduser().resolve()
            print(f"Loading frozen visual analysis: {json_path}")
            visual = VisualAnalysis.from_json_file(json_path)
        else:
            from src.services.visual_analysis import analyse_image

            image_path = args.image.expanduser().resolve()
            if not image_path.is_file():
                print(f"Image not found: {image_path}", file=__import__("sys").stderr)
                return 1
            print("Running live visual analysis (Qwen)...")
            visual = analyse_image(str(image_path))

        print(visual.model_dump_json(indent=2))
        print("\nBrand Aesthetic Descriptor...")
        descriptor = generate_descriptor(visual, brand_item=brand_item)
        print(descriptor.model_dump_json(indent=2))
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
