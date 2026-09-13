# First stage visual analysis of a brand image.
# Extracts subject colours objects mood energy temperature composition and textures.

from __future__ import annotations
import io
import json
import logging
import os
from pathlib import Path
import httpx
from src.config import Settings
from src.models.visual_analysis import VisualAnalysis, VisualReliability

logger = logging.getLogger(__name__)

# Prompt that asks the vision model for a fixed JSON shape.
# Dominant colours must come from the primary subject not the backdrop.

VISUAL_SYSTEM_PROMPT = """\
You are a visual analysis assistant for a brand development system.
Analyse the provided image and extract structured visual features.
Return ONLY a JSON object with these exact fields:

{
  "primary_subject": "main product or object",
  "dominant_colours": ["colour1", "colour2", ...],
  "objects": ["object1", "object2", ...],
  "mood_indicators": ["mood1", "mood2", ...],
  "energy": "very_low | low | moderate | high | very_high",
  "color_temperature": "cool | neutral | warm",
  "composition_style": "description of compositional approach",
  "textures": ["texture1", "texture2", ...]
}

Rules:
- primary_subject: REQUIRED short noun phrase for the main brandable item
  (e.g. "wristwatch", "skincare bottle", "running shoe", "logo wordmark").
  Identify what the product/object IS — not a scent family or music genre.
  If the image is only a logo, use "logo mark + its name" or the visible product category.
- dominant_colours: 1-10 free-form descriptive colour names of the PRIMARY SUBJECT only
  Prefer "Colour name (#RRGGBB)" when you can estimate a hex; count is not fixed at 5
  (e.g. "warm ivory", "deep forest green", "brushed champagne metal"). Invent precise
  colour language — do NOT restrict yourself to a fixed colour vocabulary.
  Include colours from the product itself, its packaging, labels, prints, and attached
  branding. Do NOT include colours that appear only in the background, studio backdrop,
  floor, scenery, lighting wash, or unrelated surrounding props/people. If a colour is
  on both the subject and the background, include it because it belongs to the subject.
  Do not list a backdrop colour (e.g. plain white/grey studio) unless the primary subject
  itself is that colour.
- objects: 1-10 salient visible objects, components, or entities in the image.
  Do not repeat the primary subject itself.(e.g. "ceramic vase", "linen fabric")
- mood_indicators: 1-5 free-form emotional/atmospheric qualities
  (e.g. "calm", "sophisticated", "hushed luxury")
- energy: REQUIRED — your judgement of the image's overall energy. Exactly one of:
  very_low, low, moderate, high, very_high
- color_temperature: REQUIRED — your judgement of the subject's overall temperature.
  Exactly one of: cool, neutral, warm
- composition_style: a single string describing the layout/arrangement approach
- textures: 1-5 textural qualities observed (e.g. "soft", "matte", "organic grain")

Return ONLY valid JSON, no markdown fencing, no explanation."""

VISUAL_USER_PROMPT = (
    "Analyse this brand cue image. First identify the primary "
    "product or object (primary_subject). Then list dominant_colours "
    "from that subject only — ignore colours that occur only in the "
    "background or unrelated surrounding elements. Judge energy and "
    "color_temperature from the image yourself. Then extract the "
    "remaining visual features."
)

_SYSTEM_PROMPT = VISUAL_SYSTEM_PROMPT
_USER_PROMPT = VISUAL_USER_PROMPT

# Default vision model version when settings omit an explicit version.
_QWEN_VERSION_FALLBACK = (
    "39e893666996acf464cff75688ad49ac95ef54e9f1c688fbc677330acc478e11"
)


# Loads fresh settings so environment changes are picked up between calls.
def _get_settings() -> Settings:
    return Settings()


# Resolves the Replicate API token from settings or environment.
def _replicate_token(settings: Settings) -> str:
    token = (
        settings.musicgen_api_key.strip()
        or os.getenv("REPLICATE_API_TOKEN", "").strip()
        or os.getenv("MUSICGEN_API_KEY", "").strip()
    )
    if not token:
        raise RuntimeError(
            "Replicate token required for Qwen vision — set MUSICGEN_API_KEY "
            "or REPLICATE_API_TOKEN in backend/.env"
        )
    return token.strip('"')


# Builds the full Replicate model identifier for vision analysis.
def _qwen_model_id(settings: Settings) -> str:
    model = settings.qwen_replicate_model.strip().strip('"')
    if ":" not in model:
        model = f"{model}:{_QWEN_VERSION_FALLBACK}"
    return model


# Removes chat end tokens and markdown fences before parsing JSON.
def _strip_model_json(content: str) -> str:
    cleaned = content.strip()
    for marker in ("<end_of_turn>", "<|im_end|>"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


# Scores raw vision model text for pipeline or comparison use.
# On failure analysis is empty and reliability carries the error.
def evaluate_model_text(content: str) -> tuple[VisualAnalysis | None, VisualReliability]:
    if not content or not str(content).strip():
        return None, VisualReliability(
            run_ok=True,
            parse_ok=False,
            schema_ok=False,
            error="empty response",
        )

    cleaned = _strip_model_json(str(content))
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, VisualReliability(
            run_ok=True,
            parse_ok=False,
            schema_ok=False,
            error=str(e),
        )

    if not isinstance(data, dict):
        return None, VisualReliability(
            run_ok=True,
            parse_ok=False,
            schema_ok=False,
            error="expected a JSON object",
        )

    try:
        visual = VisualAnalysis.model_validate(data)
    except Exception as e:
        return None, VisualReliability(
            run_ok=True,
            parse_ok=True,
            schema_ok=False,
            error=str(e),
        )

    return visual, VisualReliability(run_ok=True, parse_ok=True, schema_ok=True)


# Scores a comparison payload that may already include parse errors or nested analysis.
def evaluate_bakeoff_payload(
    payload: dict,
) -> tuple[VisualAnalysis | None, VisualReliability]:
    error = payload.get("error")
    if error:
        return None, VisualReliability(
            run_ok=False,
            parse_ok=False,
            schema_ok=False,
            error=str(error),
        )

    parse_error = payload.get("parse_error")
    visual = payload.get("visual_analysis")
    raw_unparsed = bool(payload.get("raw_text")) and not isinstance(visual, dict)
    if parse_error or raw_unparsed:
        return None, VisualReliability(
            run_ok=True,
            parse_ok=False,
            schema_ok=False,
            error=str(parse_error or "unparsed raw_text fallback"),
        )
    if not isinstance(visual, dict):
        return None, VisualReliability(
            run_ok=False,
            parse_ok=False,
            schema_ok=False,
            error="missing visual_analysis object",
        )

    try:
        model = VisualAnalysis.model_validate(visual)
    except Exception as e:
        return None, VisualReliability(
            run_ok=True,
            parse_ok=True,
            schema_ok=False,
            error=str(e),
        )

    return model, VisualReliability(run_ok=True, parse_ok=True, schema_ok=True)


# Raises an error if the model text cannot become a valid visual analysis.
def _parse_visual_analysis(content: str) -> VisualAnalysis:
    visual, reliability = evaluate_model_text(content)
    if visual is not None:
        return visual
    if not reliability.parse_ok:
        raise RuntimeError(
            f"Visual analysis returned invalid JSON: {reliability.error}"
        )
    raise RuntimeError(
        f"Visual analysis response does not match schema: {reliability.error}"
    )


# Runs the vision model on the image through Replicate.
def _run_qwen(client: object, model: str, media: object) -> str:
    output = client.run(
        model,
        input={
            "media": media,
            "prompt": f"{_SYSTEM_PROMPT}\n\n{_USER_PROMPT}",
            "max_new_tokens": 1024,
            "temperature": 0.2,
        },
    )
    if isinstance(output, list):
        return "".join(str(x) for x in output)
    return str(output)


# Runs vision analysis from a file path or raw image bytes.
def _call_qwen_vision(image_data: bytes | str, settings: Settings) -> VisualAnalysis:
    import replicate

    model = _qwen_model_id(settings)
    client = replicate.Client(
        api_token=_replicate_token(settings),
        timeout=httpx.Timeout(connect=60.0, read=None, write=None, pool=60.0),
    )

    try:
        if isinstance(image_data, str):
            path = Path(image_data).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Image not found: {path}")
            with open(path, "rb") as media:
                content = _run_qwen(client, model, media)
        else:
            if not image_data:
                raise ValueError("Image data is empty")
            media = io.BytesIO(image_data)
            media.name = "brand_image.jpg"
            content = _run_qwen(client, model, media)
    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:
        raise RuntimeError(f"Visual analysis LLM call failed: {e}") from e

    return _parse_visual_analysis(content)


# Public entry used by generation. Loads settings and returns visual analysis.
def analyse_image(image_data: bytes | str) -> VisualAnalysis:
    settings = _get_settings()
    logger.info("Calling Qwen vision model: %s", _qwen_model_id(settings))
    return _call_qwen_vision(image_data, settings)


# Command line helper that prints visual analysis JSON for an image path.
def _main() -> int:
    import sys

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None:
        backend_root = Path(__file__).resolve().parents[2]
        for env_path in (backend_root / ".env", backend_root.parent / ".env"):
            if env_path.is_file():
                load_dotenv(env_path, override=False)

    if len(sys.argv) < 2:
        print(
            "Usage: uv run python -m src.services.visual_analysis <image_path>",
            file=sys.stderr,
        )
        return 1

    image_path = Path(sys.argv[1]).expanduser().resolve()
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 1

    try:
        result = analyse_image(str(image_path))
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
