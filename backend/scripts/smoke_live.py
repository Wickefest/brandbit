# Live smoke tests for Brandbit pipeline stages against real APIs.
# Use flags to run vision BAD fragrance music judge CLIP or a full generation.
# Needs API keys in backend/.env. Defaults to judge and CLIP when no stage is chosen.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Put the backend package root on sys.path so src imports resolve when run as a script.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Load environment from backend/.env or the repo root .env when available.
try:
    from dotenv import load_dotenv

    for env_path in (_BACKEND / ".env", _BACKEND.parent / ".env"):
        if env_path.is_file():
            load_dotenv(env_path, override=False)
            break
except ImportError:
    pass

from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor, ColorTemperature, EnergyLevel
from src.models.fragrance import FragranceConcept, IntensityProfile
from src.models.music import MusicDirection
from src.services.clip_proxies import compute_clip_proxies, resolve_clip_backend
from src.services.congruence_scoring import compute_congruence
from src.services.descriptor_generation import generate_descriptor
from src.services.fragrance_generation import generate_fragrance
from src.services.music_generation import generate_music
from src.services.visual_analysis import analyse_image


# Fixed demo brand descriptor for stages that do not need a live image.
def _demo_bad() -> BrandAestheticDescriptor:
    return BrandAestheticDescriptor(
        brand_item="linen home fragrance bottle",
        mood=["hushed luxury", "intimate warmth"],
        energy=EnergyLevel.LOW,
        color_temperature=ColorTemperature.WARM,
        colours=["warm ivory", "soft amber"],
        texture=["soft matte linen", "polished stone"],
        visual_style=["minimal luxury"],
        sensory_metaphors=["velvet dusk", "warm amber glow"],
        narrative="A restrained luxury brand with soft warm florals.",
    )


# Fixed demo fragrance used when smoking the judge or CLIP without a live specialist run.
def _demo_fragrance() -> FragranceConcept:
    return FragranceConcept(
        top_notes=["bergamot"],
        heart_notes=["jasmine"],
        base_notes=["sandalwood"],
        dominant_accords=["floral", "woody"],
        intensity_profile=IntensityProfile.MODERATE,
        emotional_descriptors=["intimate", "elegant"],
        grounded_notes=["bergamot", "jasmine", "sandalwood"],
        pyrfume_sources=["goodscents"],
    )


# Fixed demo music direction used when smoking the judge or CLIP without a live specialist run.
def _demo_music() -> MusicDirection:
    return MusicDirection(
        tempo="slow",
        bpm=72,
        timbre=["warm pads", "soft strings"],
        instrumentation=["piano", "synth pads"],
        mood="contemplative",
        style="ambient",
        music_signature="Quiet linen-room pads; intimate, not lobby sparkle.",
    )


def _ok(name: str, detail: str = "") -> bool:
    suffix = f" — {detail}" if detail else ""
    print(f"  PASS  {name}{suffix}")
    return True


def _fail(name: str, detail: str) -> bool:
    print(f"  FAIL  {name} — {detail}")
    return False


# Smoke the vision model on a real brand image.
def smoke_vision(image: Path) -> bool:
    print("\n[vision] Qwen3-VL via Replicate")
    try:
        visual = analyse_image(str(image))
        return _ok("visual_analysis", f"primary_subject={visual.primary_subject!r}")
    except Exception as e:
        return _fail("visual_analysis", str(e))


# Smoke vision then brand descriptor generation on a real brand image.
def smoke_bad(image: Path) -> bool:
    print("\n[bad] GPT-4o descriptor")
    try:
        visual = analyse_image(str(image))
        bad = generate_descriptor(visual)
        return _ok("descriptor", f"brand_item={bad.brand_item!r}, energy={bad.energy.value}")
    except Exception as e:
        return _fail("descriptor", str(e))


# Smoke fragrance specialist with Pyrfume retrieval using a live or demo brand descriptor.
def smoke_fragrance(bad: BrandAestheticDescriptor | None = None) -> bool:
    print("\n[fragrance] Kimi + Pyrfume RAG")
    bad = bad or _demo_bad()
    try:
        concept = generate_fragrance(bad)
        notes = concept.top_notes[:2] + concept.heart_notes[:1]
        return _ok("fragrance", f"notes={notes}, grounded={len(concept.grounded_notes)}")
    except Exception as e:
        return _fail("fragrance", str(e))


# Smoke music specialist text only. Does not call MusicGen.
def smoke_music(bad: BrandAestheticDescriptor | None = None) -> bool:
    print("\n[music] Kimi text brief (no MusicGen)")
    bad = bad or _demo_bad()
    try:
        direction = generate_music(bad, execution_id=None)
        return _ok(
            "music_direction",
            f"style={direction.style!r}, tempo={direction.tempo!r}, mood={direction.mood!r}",
        )
    except Exception as e:
        return _fail("music_direction", str(e))


# Smoke congruence rules and the judge model on live or demo outputs.
def smoke_judge(
    bad: BrandAestheticDescriptor | None = None,
    fragrance: FragranceConcept | None = None,
    music: MusicDirection | None = None,
) -> bool:
    print("\n[judge] DeepSeek congruence (rules + LLM rubric)")
    bad = bad or _demo_bad()
    fragrance = fragrance or _demo_fragrance()
    music = music or _demo_music()
    try:
        report = compute_congruence(bad, fragrance, music)
        c = report.descriptor_consistency
        detail = (
            f"accepted={report.accepted}, "
            f"frag={c.fragrance_aligns_descriptor} ({c.fragrance_score}/5), "
            f"music={c.music_aligns_descriptor} ({c.music_score}/5)"
        )
        print(f"        summary: {report.summary[:120]}...")
        if c.fragrance_issues:
            print(f"        fragrance_issues: {c.fragrance_issues[:2]}")
        if c.music_issues:
            print(f"        music_issues: {c.music_issues[:2]}")
        return _ok("congruence_judge", detail)
    except Exception as e:
        return _fail("congruence_judge", str(e))


# Smoke CLIP image text proxies using a real image or a small synthetic image.
def smoke_clip(image: Path | None = None) -> bool:
    settings = Settings()
    backend = resolve_clip_backend(settings)
    print(f"\n[clip] openai/clip via {backend}")
    if backend == "off":
        return _fail(
            "clip_proxies",
            "CLIP backend is off — set CLIP_BACKEND=replicate and REPLICATE_API_TOKEN",
        )

    bad = _demo_bad()
    fragrance = _demo_fragrance()
    music = _demo_music()

    if image is None:
        # No brand image provided so build a tiny placeholder image for the CLIP call.
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=(30, 90, 160)).save(buf, format="PNG")
        image_bytes: bytes | str = buf.getvalue()
        print("        (using synthetic test image — pass --full <jpg> for real brand image)")
    else:
        image_bytes = str(image)

    try:
        proxies = compute_clip_proxies(image_bytes, fragrance, music, settings=settings)
        f = proxies.clip_score_image_fragrance_text
        m = proxies.clip_score_image_music_text
        if f is None and m is None:
            return _fail("clip_proxies", "scores are null — check Replicate token / model slug")
        return _ok("clip_proxies", f"fragrance={f}, music={m}")
    except Exception as e:
        return _fail("clip_proxies", str(e))


# Smoke the full generation path used by the API including congruence and CLIP.
def smoke_full(image: Path) -> bool:
    print("\n[full] end-to-end pipeline (verbose)")
    from src.main import run_generation

    try:
        result = run_generation(str(image), input_image_ref=str(image), verbose=True)
    except Exception as e:
        return _fail("full_pipeline", str(e))

    cr = result.get("congruence_report") or {}
    proxies = cr.get("automated_proxies") or {}
    detail = (
        f"execution_id={result.get('execution_id')}, "
        f"accepted={cr.get('accepted')}, "
        f"clip_frag={proxies.get('clip_score_image_fragrance_text')}, "
        f"clip_music={proxies.get('clip_score_image_music_text')}"
    )
    print("\n--- result summary ---")
    print(json.dumps(
        {
            "execution_id": result.get("execution_id"),
            "audio_sample_ref": result.get("audio_sample_ref"),
            "congruence_accepted": cr.get("accepted"),
            "regen_count": cr.get("regen_count"),
            "clip_scores": proxies,
        },
        indent=2,
    ))
    return _ok("full_pipeline", detail)


# Resolve an optional image path and exit if the file is missing.
def _resolve_image(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"Image not found: {p}")
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="Live smoke tests for Brandbit")
    parser.add_argument("image", nargs="?", help="Brand image (required for --full/--vision/--bad)")
    parser.add_argument("--list", action="store_true", help="List stages and exit")
    parser.add_argument("--all", action="store_true", help="Run judge + clip + fragrance + music")
    parser.add_argument("--vision", action="store_true")
    parser.add_argument("--bad", action="store_true")
    parser.add_argument("--fragrance", action="store_true")
    parser.add_argument("--music", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--clip", action="store_true")
    parser.add_argument("--full", action="store_true", help="Full pipeline including judge + CLIP")
    args = parser.parse_args()

    if args.list:
        print("Stages: vision, bad, fragrance, music, judge, clip, full")
        print("Examples:")
        print("  uv run python scripts/smoke_live.py --judge --clip")
        print("  uv run python scripts/smoke_live.py --full data/Picture/2.jpg")
        return 0

    # Build the stage set from flags. Default to judge and CLIP when nothing is selected.
    selected = {
        "vision": args.vision,
        "bad": args.bad,
        "fragrance": args.fragrance or args.all,
        "music": args.music or args.all,
        "judge": args.judge or args.all,
        "clip": args.clip or args.all,
        "full": args.full,
    }
    if not any(selected.values()):
        selected = {"judge": True, "clip": True}

    image = _resolve_image(args.image)
    if (args.vision or args.bad or args.full) and image is None:
        raise SystemExit("Provide an image path for --vision, --bad, or --full")

    print("Brandbit live smoke test")
    print(f"  CLIP_BACKEND={Settings().clip_backend} → {resolve_clip_backend(Settings())}")

    results: list[bool] = []
    bad: BrandAestheticDescriptor | None = None

    if selected["vision"] and image:
        results.append(smoke_vision(image))
    if selected["bad"] and image:
        # Keep the live BAD so later fragrance and music stages can reuse it.
        try:
            visual = analyse_image(str(image))
            bad = generate_descriptor(visual)
            results.append(_ok("descriptor", f"brand_item={bad.brand_item!r}"))
        except Exception as e:
            results.append(_fail("descriptor", str(e)))

    if selected["fragrance"]:
        results.append(smoke_fragrance(bad))
    if selected["music"]:
        results.append(smoke_music(bad))
    if selected["judge"]:
        results.append(smoke_judge(bad))
    if selected["clip"]:
        results.append(smoke_clip(image))
    if selected["full"] and image:
        results.append(smoke_full(image))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}\n  {passed}/{total} stages passed\n{'=' * 40}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
