   

from __future__ import annotations

import json
import queue
import re
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from src.config import Settings
from src.models.execution import PipelineExecutionRecord
from src.services.audio_synthesis import audio_file_path, load_audio_bytes
from src.services.clip_proxies import persist_input_image
from src.services.congruence_scoring import run_specialist_congruence_loop
from src.services.descriptor_generation import generate_descriptor
from src.services.descriptor_validation import validate_descriptor_instance
from src.services.evaluation_logging import log_execution
from src.services.prompt_descriptor import build_descriptor_from_visual
from src.services.rationale_generation import generate_rationale
from src.services.refinement import run_refinement
from src.services.visual_analysis import analyse_image

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
UNTIL_STAGES = frozenset({"visual", "bad"})
PIPELINE_MODES = frozenset({"bad", "prompt"})
                                                                                      
MODE_LABELS = {
    "bad": "sensory_profile",
    "prompt": "prompt_only",
}
                                                                     
MODE_RUN_LABELS = {
    "bad": "BAD",
    "prompt": "Prompt Only",
}

def normalize_pipeline_mode(mode: str | None) -> str:
                                                                              
    raw = (mode or "bad").strip().lower().replace("-", "_")
    aliases = {
        "bad": "bad",
        "sensory_profile": "bad",
        "descriptor": "bad",
        "prompt": "prompt",
        "prompt_only": "prompt",
        "promptonly": "prompt",
        "direct": "prompt",
    }
    resolved = aliases.get(raw)
    if resolved is None:
        raise ValueError(
            f"Invalid pipeline mode: {mode!r}. Allowed: bad, prompt "
            "(aliases: sensory_profile, prompt_only)."
        )
    return resolved

_GENERATE_LOCKS: dict[str, str] = {}
_GENERATE_LOCKS_GUARD = threading.Lock()

def image_stem(image_ref: str) -> str:
    raw = Path(str(image_ref)).stem or "run"
    return re.sub(r"[^\w\-]+", "_", raw, flags=re.UNICODE).strip("_") or "run"

def format_run_id(stem: str, n: int, pipeline_mode: str) -> str:
                                                                                             
    mode = normalize_pipeline_mode(pipeline_mode)
    return f"{stem}_{n:03d} ({MODE_RUN_LABELS[mode]})"

def allocate_run_id(
    image_ref: str,
    pipeline_mode: str = "bad",
    settings: Settings | None = None,
) -> str:
           
    settings = settings or Settings()
    stem = image_stem(image_ref)
    mode = normalize_pipeline_mode(pipeline_mode)
    pattern = re.compile(
        rf"^{re.escape(stem)}_(\d+)(?: \((?:Prompt Only|BAD)\))?$",
        re.IGNORECASE,
    )

    used: set[int] = set()
    for directory in (
        Path(settings.execution_log_dir),
        Path(settings.fragrance_output_dir),
        Path(settings.musicgen_output_dir),
    ):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            match = pattern.match(path.stem)
            if match:
                used.add(int(match.group(1)))

    n = min(used) if used else 1
    return format_run_id(stem, n, mode)

def _acquire_generate_lock(image_ref: str) -> str:
                                                                       
    stem = image_stem(image_ref)
    with _GENERATE_LOCKS_GUARD:
        if stem in _GENERATE_LOCKS:
            raise RuntimeError(
                f"A generation for '{stem}' is already in progress "
                f"(run {_GENERATE_LOCKS[stem]}). Wait for it to finish — "
                "do not start a second pipeline for the same image."
            )
        token = f"{stem}:pending"
        _GENERATE_LOCKS[stem] = token
        return stem

def _release_generate_lock(stem: str) -> None:
    with _GENERATE_LOCKS_GUARD:
        _GENERATE_LOCKS.pop(stem, None)

def _bind_generate_lock(stem: str, execution_id: str) -> None:
    with _GENERATE_LOCKS_GUARD:
        if stem in _GENERATE_LOCKS:
            _GENERATE_LOCKS[stem] = execution_id

api = FastAPI(
    title="Brandbit",
    description="Multimodal AI orchestration for cross-sensory brand concept generation",
    version="0.1.0",
)

                                                
app = api

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _assert_modality_neutral(descriptor) -> None:
                                                                                 
    payload = descriptor.model_dump()
    leaked = [key for key in ("scent_family", "music_direction") if key in payload]
    if leaked:
        raise RuntimeError(
            f"BAD is not modality-neutral — unexpected fields: {leaked}. "
            "Fragrance and music must be invented by specialists, not pre-set on BAD."
        )

ProgressCallback = Callable[[str, str, str | None], None]

def _emit(
    on_progress: ProgressCallback | None,
    stage: str,
    status: str,
    message: str | None = None,
) -> None:
    if on_progress is None:
        return
    on_progress(stage, status, message)

def run_generation(
    image_data: bytes | str,
    *,
    brand_item: str | None = None,
    input_image_ref: str = "unknown",
    verbose: bool = False,
    until: str | None = None,
    mode: str = "bad",
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
           
    pipeline_mode = normalize_pipeline_mode(mode)
    mode_label = MODE_LABELS[pipeline_mode]

    if until is not None and until not in UNTIL_STAGES:
        raise ValueError(
            f"Invalid until stage: {until!r}. Allowed: {', '.join(sorted(UNTIL_STAGES))}"
        )
    if until == "bad" and pipeline_mode == "prompt":
        raise ValueError(
            "--until bad is not valid with mode=prompt (BAD LLM is skipped)."
        )

    lock_stem = _acquire_generate_lock(input_image_ref)
    try:
        return _run_generation_locked(
            image_data,
            brand_item=brand_item,
            input_image_ref=input_image_ref,
            verbose=verbose,
            until=until,
            pipeline_mode=pipeline_mode,
            mode_label=mode_label,
            on_progress=on_progress,
            lock_stem=lock_stem,
        )
    finally:
        _release_generate_lock(lock_stem)

def _run_generation_locked(
    image_data: bytes | str,
    *,
    brand_item: str | None,
    input_image_ref: str,
    verbose: bool,
    until: str | None,
    pipeline_mode: str,
    mode_label: str,
    on_progress: ProgressCallback | None,
    lock_stem: str,
) -> dict[str, Any]:
    normalized = brand_item.strip() if brand_item and brand_item.strip() else None
                                                                                         
    execution_id = allocate_run_id(input_image_ref, pipeline_mode)
    _bind_generate_lock(lock_stem, execution_id)

    # Persist uploaded bytes so refine/CLIP can reload the same image later.
    # CLI path strings stay as absolute paths when already on disk.
    settings = Settings()
    if isinstance(image_data, bytes):
        stored_image_ref = persist_input_image(image_data, execution_id, settings)
    else:
        path = Path(str(image_data)).expanduser()
        stored_image_ref = str(path.resolve()) if path.is_file() else input_image_ref

    if verbose:
        print(f"\nPipeline mode: {pipeline_mode} ({mode_label})")
        print(f"Run id (retained for this process): {execution_id}")
        print("\n[1/6] Visual Analysis...")
    _emit(on_progress, "visual", "started", "Running visual analysis on the product image")
    visual = analyse_image(image_data)
    if verbose:
        print(visual.model_dump_json(indent=2))
    _emit(on_progress, "visual", "done", "Visual analysis complete")

    if until == "visual":
        if verbose:
            print("\nStopped after visual analysis (--until visual).")
        return {
            "stopped_after": "visual",
            "mode": mode_label,
            "execution_id": execution_id,
            "visual_analysis": visual.model_dump(),
        }

    if pipeline_mode == "prompt":
        if verbose:
            print(
                "\n[2/6] Prompt-only hand-off "
                "(skip BAD LLM — map visual parse → specialist context)..."
            )
        _emit(
            on_progress,
            "descriptor",
            "started",
            "Routing image parse straight to specialist agents",
        )
        descriptor = build_descriptor_from_visual(visual, brand_item=normalized)
        _assert_modality_neutral(descriptor)
        if verbose:
            print(descriptor.model_dump_json(indent=2))
        if verbose:
            print("\n[3/6] Skip BAD validation (prompt-only parse contract).")
        _emit(on_progress, "descriptor", "done", "Parse hand-off ready")
    else:
        if verbose:
            print("\n[2/6] Brand Aesthetic Descriptor (modality-neutral)...")
        _emit(
            on_progress,
            "descriptor",
            "started",
            "Building the Brand Aesthetic Descriptor (BAD)",
        )
        descriptor = generate_descriptor(visual, brand_item=normalized)
        _assert_modality_neutral(descriptor)
        if verbose:
            print(descriptor.model_dump_json(indent=2))

        if verbose:
            print("\n[3/6] BAD validation...")
        validation = validate_descriptor_instance(descriptor)
        if not validation.is_valid:
            raise ValueError(f"BAD validation failed: {validation.errors}")
        if verbose:
            print("BAD valid (modality-neutral).")
        _emit(on_progress, "descriptor", "done", "BAD validated")

        if until == "bad":
            if verbose:
                print("\nStopped after BAD (--until bad).")
            return {
                "stopped_after": "bad",
                "mode": mode_label,
                "execution_id": execution_id,
                "visual_analysis": visual.model_dump(),
                "brand_aesthetic_descriptor": descriptor.model_dump(),
            }

    if verbose:
        print("\n[4/6] Specialist generation + congruence loop (fragrance/music)...")
        print(f"Run id: {execution_id}")
    _emit(
        on_progress,
        "specialists",
        "started",
        "Handing off to fragrance and music specialists",
    )
    fragrance, music, congruence = run_specialist_congruence_loop(
        descriptor,
        execution_id=execution_id,
        image_data=image_data,
        verbose=verbose,
        on_progress=on_progress,
    )
    _emit(on_progress, "specialists", "done", "Specialist concepts ready")
    if not music.audio_sample_ref:
        raise RuntimeError(
            "MusicGen audio is required and was not created. "
            "Check MUSICGEN_BACKEND=replicate and the Replicate token."
        )
    if verbose:
        print(
            f"Audio saved via {music.audio_sample_ref} → "
            f"<repo>/eval/outputs/music/{execution_id}.wav"
        )

    _emit(on_progress, "rationale", "started", "Writing the cross-modal rationale")
    rationale = generate_rationale(descriptor, fragrance, music)
    if verbose:
        print("Fragrance (specialist):", fragrance.model_dump_json(indent=2))
        print("Music (specialist):", music.model_dump_json(indent=2))
        print("Congruence:", congruence.model_dump_json(indent=2))
        print("Rationale:\n", rationale)

    if verbose:
        print("\n[5/6] Congruence summary...")
        print(
            f"accepted={congruence.accepted} regen_count={congruence.regen_count} "
            f"attempts={len(congruence.attempts)}"
        )
    _emit(on_progress, "rationale", "done", "Rationale ready")

    if verbose:
        print("\n[6/6] Saving execution record...")
    _emit(on_progress, "save", "started", "Filing the archive record")
    record = PipelineExecutionRecord(
        execution_id=execution_id,
        timestamp=datetime.now(timezone.utc),
        input_image_ref=stored_image_ref,
        brand_aesthetic_descriptor=descriptor,
        fragrance_concept=fragrance,
        music_direction=music,
        audio_sample_ref=music.audio_sample_ref,
        rationale=rationale,
        congruence_report=congruence,
        mode=mode_label,
    )
    path = log_execution(record)
    if verbose:
        print(f"Saved to: {path}")
    _emit(on_progress, "save", "done", "Archive filed")

    return {
        "execution_id": execution_id,
        "brand_aesthetic_descriptor": descriptor.model_dump(mode="json"),
        "fragrance_concept": fragrance.model_dump(mode="json"),
        "music_direction": music.model_dump(mode="json"),
        "audio_sample_ref": music.audio_sample_ref,
        "rationale": rationale,
        "congruence_report": congruence.model_dump(mode="json"),
        "congruence_accepted": congruence.accepted,
        "mode": mode_label,
        "refinement_history": [],
        "log_path": str(path),
    }

@api.get("/health")
def health():
    return {"status": "ok"}

@api.post("/api/generate")
async def generate_concept(
    image: UploadFile = File(...),
    brand_item: str | None = Form(default=None),
    mode: str = Form(default="bad"),
    stream: str = Form(default="0"),
):
           
    settings = Settings()
    normalized_brand_item = brand_item.strip() if brand_item and brand_item.strip() else None
    want_stream = str(stream).strip().lower() in {"1", "true", "yes"}

    try:
        pipeline_mode = normalize_pipeline_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if image.content_type not in settings.allowed_image_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {image.content_type}",
        )

    image_data = await image.read()
    if len(image_data) > settings.max_image_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.max_image_size_mb}MB limit",
        )

    filename = image.filename or "unknown"

    if not want_stream:
        try:
            result = run_generation(
                image_data,
                brand_item=normalized_brand_item,
                input_image_ref=filename,
                mode=pipeline_mode,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except RuntimeError as e:
            msg = str(e)
            code = 409 if "already in progress" in msg.lower() else 500
            raise HTTPException(status_code=code, detail=msg) from e

        result.pop("log_path", None)
        return result

    event_q: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def on_progress(stage: str, status: str, message: str | None = None) -> None:
        event_q.put(
            {
                "type": "stage",
                "stage": stage,
                "status": status,
                "message": message,
            }
        )

    def worker() -> None:
        try:
            result = run_generation(
                image_data,
                brand_item=normalized_brand_item,
                input_image_ref=filename,
                mode=pipeline_mode,
                on_progress=on_progress,
            )
            result.pop("log_path", None)
            event_q.put({"type": "result", "result": result})
        except ValueError as e:
            event_q.put({"type": "error", "detail": str(e)})
        except RuntimeError as e:
            event_q.put({"type": "error", "detail": str(e)})
        except Exception as e:                                                            
            event_q.put({"type": "error", "detail": str(e)})
        finally:
            event_q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        while True:
            item = event_q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@api.get("/api/audio/{execution_id:path}")
def get_audio_sample(execution_id: str):
                                                                     
    settings = Settings()
    try:
        path = audio_file_path(execution_id, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if load_audio_bytes(execution_id, settings) is None:
        raise HTTPException(status_code=404, detail="Audio sample not found")

    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{Path(path).name}",
    )

@api.post("/api/refine")
async def refine_concept(
    execution_id: str = Form(...),
    feedback: str = Form(...),
):
                                                                                     
    try:
        result = run_refinement(execution_id.strip(), feedback)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    result.pop("log_path", None)
    return result

@api.get("/api/executions/{execution_id:path}")
def get_execution_record(execution_id: str):
                                                     
    from src.services.evaluation_logging import get_execution

    record = get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return record

def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    backend_root = Path(__file__).resolve().parent.parent
    repo_root = backend_root.parent
    for path in (backend_root / ".env", repo_root / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)

def _resolve_image_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Image not found: {path}\n"
            "Place your brand image at that path, e.g.:\n"
            "  uv run python run_pipeline.py test_image.jpg"
        )
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(
            f"Unsupported image format: {path.suffix}\n"
            f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )
    return path

def _parse_cli_args(args: list[str]) -> tuple[str, str | None, str | None, str]:
           
    until: str | None = None
    mode = "bad"
    positionals: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--until":
            if i + 1 >= len(args):
                raise ValueError("--until requires a stage: visual or bad")
            until = args[i + 1].strip().lower()
            if until not in UNTIL_STAGES:
                raise ValueError(
                    f"Invalid --until stage: {until!r}. "
                    f"Allowed: {', '.join(sorted(UNTIL_STAGES))}"
                )
            i += 2
            continue
        if args[i] == "--mode":
            if i + 1 >= len(args):
                raise ValueError("--mode requires a value: bad or prompt")
            mode = normalize_pipeline_mode(args[i + 1])
            i += 2
            continue
        if args[i].startswith("--"):
            raise ValueError(f"Unknown option: {args[i]}")
        positionals.append(args[i])
        i += 1

    if not positionals:
        raise ValueError("Missing image path")
    image_path = positionals[0]
    brand_item = positionals[1].strip() if len(positionals) > 1 else None
    if len(positionals) > 2:
        raise ValueError(
            f"Unexpected extra arguments: {positionals[2:]}. "
            "Usage: brandbit <image_path> [--mode bad|prompt] "
            "[--until visual|bad] [brand_item]"
        )
    return image_path, brand_item or None, until, mode

def cli(argv: list[str] | None = None) -> int:
                                                                                 
    _load_env()
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        print(
            "Usage: uv run brandbit <image_path> [--mode bad|prompt] "
            "[--until visual|bad] [brand_item]"
        )
        print(
            "   or: uv run python run_pipeline.py <image_path> "
            "[--mode bad|prompt] [--until visual|bad] [brand_item]"
        )
        print("Example: uv run brandbit test_image.jpg")
        print("         uv run brandbit test_image.jpg --mode prompt")
        print("         uv run brandbit test_image.jpg --until bad")
        return 1

    try:
        raw_path, brand_item, until, mode = _parse_cli_args(args)
        resolved = _resolve_image_path(raw_path)
        print(f"Input image: {resolved}")
        print(f"Pipeline mode: {mode}")
        if until:
            print(f"Stopping after: {until}")
        run_generation(
            str(resolved),
            brand_item=brand_item,
            input_image_ref=str(resolved),
            verbose=True,
            until=until,
            mode=mode,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0
