# Synthesizes music audio from a music direction and optional brand cues.
# Writes the sound file under the configured music output directory.
from __future__ import annotations
import io
import logging
import os
from pathlib import Path
from urllib.parse import quote
import httpx
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor
from src.models.music import MusicDirection
from src.services.path_safety import contained_path

logger = logging.getLogger(__name__)

REPLICATE_MODEL_DEFAULT = (
    "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"
)

# Builds one MusicGen prompt from the music direction and optional brand cues.
def build_musicgen_prompt(
    direction: MusicDirection,
    bad: BrandAestheticDescriptor | None = None,
) -> str:
    parts = [
        f"{direction.style} instrumental",
        direction.mood,
        f"{direction.tempo} tempo",
        f"{direction.bpm} BPM",
        ", ".join(direction.instrumentation),
        ", ".join(direction.timbre),
        "brand ambient music, no vocals",
    ]
    if direction.music_signature.strip():
        parts.append(direction.music_signature.strip())
    if bad:
        if bad.brand_item:
            parts.append(f"for {bad.brand_item}")
        if bad.mood:
            parts.append(", ".join(bad.mood[:3]))
        if bad.colours:
            parts.append(", ".join(bad.colours[:4]))
        parts.append(f"{bad.color_temperature.value} tone")
    return ", ".join(part.strip() for part in parts if part and part.strip())


# Chooses the MusicGen backend from settings.
def resolve_backend(settings: Settings) -> str:
    backend = settings.musicgen_backend.lower()
    if backend != "auto":
        return backend

    if settings.musicgen_remote_url.strip():
        return "remote"
    if settings.musicgen_api_key.strip() or os.getenv("REPLICATE_API_TOKEN"):
        return "replicate"
    return "off"


def audio_api_path(execution_id: str) -> str:
    return f"/api/audio/{quote(execution_id, safe='')}"


def audio_file_path(execution_id: str, settings: Settings) -> Path:
    # Resolve the WAV path under the music output directory.
    return contained_path(settings.musicgen_output_dir, execution_id, suffix=".wav")


# Synthesizes audio for this execution or returns nothing when synthesis is off.
def synthesize_audio(
    direction: MusicDirection,
    execution_id: str,
    bad: BrandAestheticDescriptor | None = None,
    settings: Settings | None = None,
) -> str | None:
    settings = settings or Settings()
    backend = resolve_backend(settings)

    if backend == "off":
        logger.info("MusicGen disabled (backend=off)")
        return None

    prompt = build_musicgen_prompt(direction, bad)
    logger.info("MusicGen prompt: %s", prompt)

    synthesizers = {
        "replicate": _synthesize_replicate,
        "remote": _synthesize_remote,
        "local": _synthesize_local,
    }
    synthesize_fn = synthesizers.get(backend)
    if synthesize_fn is None:
        raise RuntimeError(f"Unknown musicgen_backend: {backend}")

    wav_bytes = synthesize_fn(prompt, settings)
    # Always overwrite the same path so refinement reuses the execution_id.
    output_path = audio_file_path(execution_id, settings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wav_bytes)
    logger.info("Saved/overwrote audio to %s", output_path)
    return audio_api_path(execution_id)


def load_audio_bytes(execution_id: str, settings: Settings | None = None) -> bytes | None:
    settings = settings or Settings()
    try:
        path = audio_file_path(execution_id, settings)
    except ValueError:
        return None
    if not path.exists():
        return None
    return path.read_bytes()


def _synthesize_replicate(prompt: str, settings: Settings) -> bytes:
    import httpx
    import replicate

    token = (
        settings.musicgen_api_key.strip().strip('"')
        or os.getenv("REPLICATE_API_TOKEN", "").strip().strip('"')
    )
    if not token:
        raise RuntimeError(
            "Replicate token required — set MUSICGEN_API_KEY or REPLICATE_API_TOKEN"
        )

    timeout_s = max(60, int(settings.audio_generation_timeout_seconds))
    client = replicate.Client(
        api_token=token,
        timeout=httpx.Timeout(timeout_s, connect=30.0),
    )
    try:
        output = client.run(
            settings.musicgen_replicate_model,
            input={
                "prompt": prompt,
                "duration": settings.musicgen_duration_seconds,
                "model_version": settings.musicgen_replicate_version,
                "output_format": "wav",
                "temperature": 1.0,
                "classifier_free_guidance": 3,
            },
        )
    except Exception as e:
        raise RuntimeError(f"Replicate MusicGen failed: {e}") from e

    return _read_replicate_output(output)


# Normalizes Replicate output into WAV bytes.
def _read_replicate_output(output: object) -> bytes:
    if output is None:
        raise RuntimeError("Replicate MusicGen returned no output")

    if isinstance(output, (bytes, bytearray)):
        return bytes(output)

    if isinstance(output, str):
        if output.startswith("http"):
            return _download_url(output, timeout=600)
        path = Path(output)
        if path.exists():
            return path.read_bytes()
        raise RuntimeError(f"Unexpected Replicate output string: {output[:120]}")

    read_fn = getattr(output, "read", None)
    if callable(read_fn):
        data = read_fn()
        if isinstance(data, str):
            return data.encode()
        return bytes(data)

    url = getattr(output, "url", None)
    if url:
        return _download_url(str(url), timeout=600)

    if isinstance(output, (list, tuple)) and output:
        return _read_replicate_output(output[0])

    raise RuntimeError(f"Unsupported Replicate output type: {type(output)}")


def _synthesize_remote(prompt: str, settings: Settings) -> bytes:
    url = settings.musicgen_remote_url.strip()
    if not url:
        raise RuntimeError("musicgen_remote_url is not configured")

    headers = {"Content-Type": "application/json"}
    if settings.musicgen_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.musicgen_api_key.strip()}"

    payload = {
        "prompt": prompt,
        "duration": settings.musicgen_duration_seconds,
        "model": settings.musicgen_local_model,
    }

    try:
        with httpx.Client(timeout=settings.audio_generation_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Remote MusicGen worker failed: {e}") from e

    content_type = response.headers.get("content-type", "")
    if "audio" in content_type:
        return response.content

    data = response.json()
    if "audio_url" in data:
        return _download_url(data["audio_url"], timeout=180)
    if "audio_base64" in data:
        import base64

        return base64.b64decode(data["audio_base64"])

    raise RuntimeError("Remote worker response missing audio payload")


def _synthesize_local(prompt: str, settings: Settings) -> bytes:
    try:
        import scipy.io.wavfile
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
    except ImportError as e:
        raise RuntimeError(
            "Local MusicGen requires optional audio deps: uv sync --group audio"
        ) from e

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading MusicGen model %s on %s", settings.musicgen_local_model, device)

    processor = AutoProcessor.from_pretrained(settings.musicgen_local_model)
    model = MusicgenForConditionalGeneration.from_pretrained(settings.musicgen_local_model)
    model.to(device)

    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    ).to(device)

    max_new_tokens = int(settings.musicgen_duration_seconds * 50)
    with torch.no_grad():
        audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)

    sampling_rate = model.config.audio_encoder.sampling_rate
    audio = audio_values[0, 0].cpu().numpy()

    buffer = io.BytesIO()
    scipy.io.wavfile.write(buffer, rate=sampling_rate, data=audio)
    return buffer.getvalue()


def _download_url(url: str, timeout: int) -> bytes:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content
