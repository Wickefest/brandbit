# Computes CLIP similarity between the image and fragrance or music text.
# Used as supportive scores and does not decide congruence acceptance.
from __future__ import annotations
import io
import logging
import math
import os
from pathlib import Path
from PIL import Image
from src.config import Settings
from src.models.congruence import AutomatedProxySignals
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection
from src.services.path_safety import contained_path

logger = logging.getLogger(__name__)

# Cache for loaded local CLIP models.
_CLIP_CACHE: dict[str, tuple[object, object, str]] = {}

# Turns image bytes or a file path into readable image bytes.
def resolve_image_bytes(image_data: bytes | str | None) -> bytes | None:
    if image_data is None:
        return None
    if isinstance(image_data, bytes):
        return image_data if image_data else None
    path = Path(str(image_data)).expanduser()
    if path.is_file():
        return path.read_bytes()
    return None


def _image_extension(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


# Saves the input image under the configured image directory for later use.
def persist_input_image(
    image_bytes: bytes,
    execution_id: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or Settings()
    if not image_bytes:
        raise ValueError("empty image bytes")
    out_dir = Path(settings.input_image_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = contained_path(
        out_dir,
        execution_id,
        suffix=_image_extension(image_bytes),
    )
    path.write_bytes(image_bytes)
    return str(path)

# Builds a short text caption for fragrance CLIP scoring.
def fragrance_caption(fragrance: FragranceConcept) -> str:
    guide_smells = [
        (g.smells_like or "").strip()
        for g in (fragrance.note_guide or [])
        if (g.smells_like or "").strip()
    ]
    note_bits = guide_smells[:6] or [
        *fragrance.top_notes[:2],
        *fragrance.heart_notes[:2],
        *fragrance.base_notes[:2],
    ]
    # Drop long chemical names that hurt CLIP text quality.
    note_bits = [n for n in note_bits if n and len(n) <= 40][:6]

    parts = [
        ", ".join(fragrance.dominant_accords[:3]),
        ", ".join(note_bits),
        ", ".join(fragrance.emotional_descriptors[:3]),
        f"{fragrance.intensity_profile.value} fragrance",
    ]
    return _clip_truncate(
        ". ".join(part.strip() for part in parts if part and part.strip())
    )

# Builds a short text caption for music CLIP scoring.
def music_caption(music: MusicDirection) -> str:
    parts = [
        f"{music.style} ambient music",
        f"{music.tempo} tempo",
        f"{music.bpm} BPM" if music.bpm is not None else "",
        music.mood,
        ", ".join(music.timbre[:3]),
        ", ".join(music.instrumentation[:3]),
    ]
    return _clip_truncate(
        ", ".join(part.strip() for part in parts if part and part.strip())
    )

# Character limit so CLIP text stays within context.
_CLIP_MAX_CHARS = 200

def _clip_truncate(text: str, max_chars: int = _CLIP_MAX_CHARS) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[: max_chars - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut}…"


def _replicate_token(settings: Settings) -> str:
    token = (
        settings.musicgen_api_key.strip()
        or os.getenv("REPLICATE_API_TOKEN", "").strip()
        or os.getenv("MUSICGEN_API_KEY", "").strip()
    )
    token = token.strip().strip('"')
    if not token:
        raise RuntimeError(
            "Replicate token required for CLIP — set MUSICGEN_API_KEY or "
            "REPLICATE_API_TOKEN in backend/.env"
        )
    return token


def _has_replicate_token(settings: Settings) -> bool:
    token = (
        settings.musicgen_api_key.strip()
        or os.getenv("REPLICATE_API_TOKEN", "").strip()
        or os.getenv("MUSICGEN_API_KEY", "").strip()
    )
    return bool(token.strip().strip('"'))


# Chooses which CLIP backend to use from settings.
def resolve_clip_backend(settings: Settings) -> str:
    backend = (settings.clip_backend or "auto").lower()
    if backend == "off":
        return "off"
    if backend == "replicate":
        return "replicate"
    if backend == "local":
        return "local"
    # Prefer Replicate when a token exists otherwise try local otherwise turn off.
    if _has_replicate_token(settings):
        return "replicate"
    try:
        import torch
        from transformers import CLIPModel

        return "local"
    except ImportError:
        return "off"


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# Scales cosine similarity into the positive CLIP score range used in reports.
# Keep the same scaling formula across backends.
def _clipscore(cosine: float) -> float:
    return round(max(0.0, float(cosine)) * 2.5, 4)


# Normalizes Replicate embedding output into a float list.
def _extract_embedding(output: object) -> list[float]:
    if output is None:
        raise RuntimeError("CLIP returned no embedding")

    if isinstance(output, dict):
        for key in ("embedding", "embeddings", "output"):
            if key in output and isinstance(output[key], list):
                return [float(x) for x in output[key]]
        raise RuntimeError(f"Unexpected CLIP dict output keys: {list(output)}")

    if isinstance(output, list):
        if output and isinstance(output[0], dict):
            first = output[0]
            if "embedding" in first:
                return [float(x) for x in first["embedding"]]
        if output and isinstance(output[0], (int, float)):
            return [float(x) for x in output]

    raise RuntimeError(f"Unexpected CLIP output type: {type(output).__name__}")


# Converts image bytes into an RGB JPEG buffer for upload.
def _as_clip_image_file(image_bytes: bytes) -> io.BytesIO:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Upscale very small images so remote CLIP handles them reliably.
    if min(image.size) < 32:
        image = image.resize((224, 224))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    buf.name = "brand_image.jpg"
    return buf


# Fetches one CLIP embedding for either text or image from Replicate.
def _replicate_embedding(
    settings: Settings,
    *,
    text: str | None = None,
    image_bytes: bytes | None = None,
) -> list[float]:
    import replicate

    model = settings.clip_replicate_model.strip().strip('"')
    client = replicate.Client(api_token=_replicate_token(settings))

    if image_bytes is not None:
        output = client.run(model, input={"image": _as_clip_image_file(image_bytes)})
    elif text is not None:
        output = client.run(model, input={"text": _clip_truncate(text)})
    else:
        raise ValueError("CLIP replicate call requires text or image_bytes")

    return _extract_embedding(output)


def _similarity_replicate(image_bytes: bytes, text: str, settings: Settings) -> float:
    safe_text = _clip_truncate(text)
    img_emb = _replicate_embedding(settings, image_bytes=image_bytes)
    txt_emb = _replicate_embedding(settings, text=safe_text)
    return _clipscore(_cosine(img_emb, txt_emb))


def _load_clip_local(settings: Settings) -> tuple[object, object, str]:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model_name = settings.clip_model_name
    if model_name not in _CLIP_CACHE:
        logger.info("Loading local CLIP model %s", model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        model = CLIPModel.from_pretrained(model_name)
        model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        _CLIP_CACHE[model_name] = (processor, model, device)
    return _CLIP_CACHE[model_name]


def _similarity_local(image_bytes: bytes, text: str, settings: Settings) -> float:
    import torch

    processor, model, device = _load_clip_local(settings)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    with torch.no_grad():
        inputs = processor(
            text=[text],
            images=image,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        inputs = {key: value.to(device) for key, value in inputs.items()}
        outputs = model(**inputs)
        image_embeds = outputs.image_embeds / outputs.image_embeds.norm(
            dim=-1, keepdim=True
        )
        text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)
        cosine = (image_embeds @ text_embeds.T).squeeze().item()

    return _clipscore(cosine)


def _similarity(image_bytes: bytes, text: str, settings: Settings) -> float:
    backend = resolve_clip_backend(settings)
    if backend == "replicate":
        return _similarity_replicate(image_bytes, text, settings)
    return _similarity_local(image_bytes, text, settings)


# Computes fragrance and music CLIP scores or returns empty signals on failure.
def compute_clip_proxies(
    image_data: bytes | str | None,
    fragrance: FragranceConcept,
    music: MusicDirection,
    *,
    settings: Settings | None = None,
) -> AutomatedProxySignals:
    settings = settings or Settings()
    backend = resolve_clip_backend(settings)
    if backend == "off":
        return AutomatedProxySignals()

    raw = resolve_image_bytes(image_data)
    if raw is None:
        logger.debug("CLIP skipped: no image bytes available")
        return AutomatedProxySignals()

    try:
        frag_text = fragrance_caption(fragrance)
        music_text = music_caption(music)
        logger.info("Computing CLIP proxies via %s backend", backend)
        frag_score = _similarity(raw, frag_text, settings)
        music_score = _similarity(raw, music_text, settings)
        logger.info(
            "CLIP proxies (%s): fragrance=%.3f music=%.3f",
            backend,
            frag_score,
            music_score,
        )
        return AutomatedProxySignals(
            clip_score_image_fragrance_text=frag_score,
            clip_score_image_music_text=music_score,
            imagebind_score_image_audio=None,
        )
    except Exception as e:
        logger.warning("CLIP proxy scoring failed (continuing without proxies): %s", e)
        return AutomatedProxySignals()
