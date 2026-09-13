# Judges whether fragrance and music fit the brand descriptor.
# Can regenerate failing specialists and optionally attach CLIP scores.
from __future__ import annotations
import json
import logging
from collections.abc import Callable
from src.config import Settings
from src.models.congruence import (
    AutomatedProxySignals,
    CongruenceAttempt,
    CongruenceReport,
    DescriptorConsistency,
)
from src.models.descriptor import BrandAestheticDescriptor
from src.models.fragrance import FragranceConcept
from src.models.music import MusicDirection
from src.services.congruence_rules import RuleCheckResult, run_rule_checks

logger = logging.getLogger(__name__)

# Lowest judge score that counts as a pass for a modality.
# Soft fails still return the latest fragrance and music outputs.
_PASS_SCORE = 4

# Prompt for the judge model that scores fragrance and music against the brand descriptor.
_JUDGE_PROMPT = """\
You are a strict, impartial cross-modal congruence evaluator for a multisensory brand system.

You receive:
1) A modality-neutral Brand Aesthetic Descriptor (BAD) — shared visual/aesthetic evidence
2) A FragranceConcept — invented independently by a fragrance specialist
3) A MusicDirection — invented independently by a music specialist

The BAD intentionally has NO scent_family or music_direction. Judge whether each specialist
output is a credible, independent translation of the SAME brand identity — not prompt copying.

Evaluate FRAGRANCE and MUSIC separately. Apply real scrutiny; do not default to pass.

## Fragrance rubric (vs BAD)
- Mood/emotional fit: accords + emotional_descriptors vs BAD.mood, narrative
- Energy/intensity fit: intensity_profile vs BAD.energy (light↔low, bold↔high)
- Temperature/texture fit: note character vs BAD.color_temperature + texture
- Brand plausibility: would this scent direction suit BAD.brand_item?

## Music rubric (vs BAD)
- Energy/tempo fit: tempo vs BAD.energy (slow to low, uptempo to high)
- Mood fit: mood/style vs BAD.mood + narrative
- Timbre/instrumentation fit: warm/cool, soft/harsh vs BAD.color_temperature + texture
- Sound-world fit: instruments/style should belong to BAD.brand_item's object, place,
  or craft — not a generic luxury lobby / European salon unless that is the object
- music_signature: does the story justify those instruments for this brand_item?

## Scoring
- fragrance_score / music_score: integer 1-5 (1=clear mismatch, 5=excellent fit)
- Set *_aligns_descriptor true ONLY when score >= 4 AND no major rubric violation
- Cite specific BAD fields and output fields in issues (e.g. "BAD.energy=high vs tempo=slow")

Return ONLY valid JSON:

{
  "fragrance_score": 1-5,
  "music_score": 1-5,
  "fragrance_aligns_descriptor": true or false,
  "music_aligns_descriptor": true or false,
  "fragrance_issues": ["specific mismatch 1", "..."],
  "music_issues": ["specific mismatch 1", "..."],
  "details": "consolidated explanation referencing BAD fields and outputs",
  "summary": "1-2 sentence overall assessment"
}

If pre-screening rule flags are provided, verify them — do not ignore obvious clashes.
Return ONLY valid JSON, no markdown fencing, no explanation."""


def _get_settings() -> Settings:
    return Settings()


def _require_api_key(settings: Settings) -> None:
    from src.services.llm_chat import TextRole, require_role_credentials

    require_role_credentials(TextRole.JUDGE, settings)


def _parse_judge_payload(content: str) -> dict:
    cleaned = content.strip().strip("```").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Congruence scoring returned invalid JSON: {content[:200]}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Congruence judge response must be a JSON object")
    return data


def _clamp_score(value: object) -> int | None:
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(5, score))


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _merge_issues(*sources: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for source in sources:
        for item in source:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


# Applies the pass threshold to alignment flags and scores.
def _apply_pass_threshold(
    aligns: bool,
    score: int | None,
    issues: list[str],
) -> tuple[bool, int | None]:
    if score is not None and score < _PASS_SCORE:
        return False, score
    if aligns and score is None and issues:
        return False, score
    if aligns and score is not None and score >= _PASS_SCORE:
        return True, score
    if aligns and score is None:
        return True, score
    return aligns, score


# Combines rule flags with judge output into one consistency result.
def _build_consistency(
    data: dict,
    rules: RuleCheckResult,
) -> DescriptorConsistency:
    frag_score = _clamp_score(data.get("fragrance_score"))
    music_score = _clamp_score(data.get("music_score"))

    frag_issues = _merge_issues(
        rules.fragrance_issues,
        _as_str_list(data.get("fragrance_issues")),
    )
    music_issues = _merge_issues(
        rules.music_issues,
        _as_str_list(data.get("music_issues")),
    )

    frag_ok, frag_score = _apply_pass_threshold(
        bool(data.get("fragrance_aligns_descriptor", False)),
        frag_score,
        frag_issues,
    )
    music_ok, music_score = _apply_pass_threshold(
        bool(data.get("music_aligns_descriptor", False)),
        music_score,
        music_issues,
    )

    # Hard rule fails always reject that modality and lower the score
    # even if the judge was lenient.
    if rules.critical_fragrance_fail:
        frag_ok = False
        if frag_score is None or frag_score > 2:
            frag_score = min(frag_score or 2, 2)
    if rules.critical_music_fail:
        music_ok = False
        if music_score is None or music_score > 2:
            music_score = min(music_score or 2, 2)

    details = str(data.get("details") or "").strip()
    if not details:
        parts: list[str] = []
        if frag_issues:
            parts.append("Fragrance: " + "; ".join(frag_issues[:3]))
        if music_issues:
            parts.append("Music: " + "; ".join(music_issues[:3]))
        details = " | ".join(parts) if parts else "No detailed judge notes."

    return DescriptorConsistency(
        fragrance_aligns_descriptor=frag_ok,
        music_aligns_descriptor=music_ok,
        details=details,
        fragrance_score=frag_score,
        music_score=music_score,
        fragrance_issues=frag_issues,
        music_issues=music_issues,
    )


# Turns rejection issues into feedback text for specialist regeneration.
def build_regen_feedback(consistency: DescriptorConsistency, summary: str) -> str:
    parts: list[str] = []
    if not consistency.fragrance_aligns_descriptor:
        parts.append("FRAGRANCE REJECTED:")
        if consistency.fragrance_issues:
            parts.extend(f"- {i}" for i in consistency.fragrance_issues[:5])
        else:
            parts.append(f"- {consistency.details}")
        if consistency.fragrance_score is not None:
            parts.append(f"- Score {consistency.fragrance_score}/5 (need {_PASS_SCORE}+)")
    if not consistency.music_aligns_descriptor:
        parts.append("MUSIC REJECTED:")
        if consistency.music_issues:
            parts.extend(f"- {i}" for i in consistency.music_issues[:5])
        else:
            parts.append(f"- {consistency.details}")
        if consistency.music_score is not None:
            parts.append(f"- Score {consistency.music_score}/5 (need {_PASS_SCORE}+)")
    if parts:
        return "\n".join(parts)
    return summary or consistency.details


# Calls the judge model with the brand descriptor outputs and rule flags.
def _llm_judge(
    bad: BrandAestheticDescriptor,
    fragrance: FragranceConcept,
    music: MusicDirection,
    rules: RuleCheckResult,
    settings: Settings,
) -> tuple[DescriptorConsistency, str]:
    from src.services.llm_chat import TextRole, chat_completion

    user_message = (
        f"Brand Aesthetic Descriptor:\n{bad.model_dump_json(indent=2)}\n\n"
        f"Fragrance Concept:\n{fragrance.model_dump_json(indent=2)}\n\n"
        f"Music Direction:\n{music.model_dump_json(indent=2)}\n\n"
        f"Pre-screening rule flags (verify; override if wrong):\n{rules.summary_for_judge()}\n\n"
        "Score each modality 1-5 and set aligns true only for score >= 4 with no major violation."
    )

    try:
        content = chat_completion(
            TextRole.JUDGE,
            system=_JUDGE_PROMPT,
            user=user_message,
            temperature=0.1,
            max_tokens=768,
            settings=settings,
        )
    except Exception as e:
        raise RuntimeError(f"Congruence scoring failed: {e}") from e

    if not content:
        raise RuntimeError("Congruence scoring returned empty response")

    data = _parse_judge_payload(content)
    consistency = _build_consistency(data, rules)
    summary = str(data.get("summary") or consistency.details)
    return consistency, summary


# Builds one congruence report from rules and the judge and may attach CLIP scores.
def compute_congruence(
    bad: BrandAestheticDescriptor,
    fragrance: FragranceConcept,
    music: MusicDirection,
    *,
    image_data: bytes | str | None = None,
    include_clip: bool = False,
) -> CongruenceReport:
    settings = _get_settings()
    _require_api_key(settings)

    rules = run_rule_checks(bad, fragrance, music)
    if rules.fragrance_issues or rules.music_issues:
        logger.info(
            "Rule pre-check: fragrance_issues=%s music_issues=%s",
            len(rules.fragrance_issues),
            len(rules.music_issues),
        )

    logger.info("Running DeepSeek LLM congruence judge")
    consistency, summary = _llm_judge(bad, fragrance, music, rules, settings)
    accepted = (
        consistency.fragrance_aligns_descriptor and consistency.music_aligns_descriptor
    )

    proxies = AutomatedProxySignals()
    if include_clip and image_data is not None:
        from src.services.clip_proxies import compute_clip_proxies

        proxies = compute_clip_proxies(image_data, fragrance, music, settings=settings)

    return CongruenceReport(
        automated_proxies=proxies,
        descriptor_consistency=consistency,
        summary=summary,
        attempts=[
            CongruenceAttempt(
                attempt=1,
                fragrance_aligns_descriptor=consistency.fragrance_aligns_descriptor,
                music_aligns_descriptor=consistency.music_aligns_descriptor,
                details=consistency.details,
                summary=summary,
                regenerated=[],
            )
        ],
        regen_count=0,
        accepted=accepted,
    )


# Generates specialists judges them regenerates failures then synthesizes audio.
def run_specialist_congruence_loop(
    bad: BrandAestheticDescriptor,
    *,
    execution_id: str | None = None,
    image_data: bytes | str | None = None,
    verbose: bool = False,
    on_progress: Callable[[str, str, str | None], None] | None = None,
    existing_fragrance: FragranceConcept | None = None,
    existing_music: MusicDirection | None = None,
    regenerate: frozenset[str] | None = None,
) -> tuple[FragranceConcept, MusicDirection, CongruenceReport]:
    from src.services.audio_synthesis import synthesize_audio
    from src.services.fragrance_generation import generate_fragrance
    from src.services.music_generation import generate_music_direction

    def emit(stage: str, status: str, message: str | None = None) -> None:
        if on_progress is not None:
            on_progress(stage, status, message)

    settings = _get_settings()
    max_regen = max(0, int(settings.congruence_regen_max_retries))
    regen_targets = regenerate if regenerate is not None else frozenset({"fragrance", "music"})

    if "fragrance" in regen_targets or existing_fragrance is None:
        emit("fragrance", "started", "Fragrance specialist is inventing the scent concept")
        fragrance = generate_fragrance(bad)
        emit("fragrance", "done", "Fragrance concept ready")
    else:
        fragrance = existing_fragrance
        emit("fragrance", "done", "Keeping existing fragrance concept")

    # Keep music as text first and wait to synthesize audio until later.
    if "music" in regen_targets or existing_music is None:
        emit("music", "started", "Music specialist is inventing the sound direction")
        music = generate_music_direction(bad)
        emit("music", "done", "Music direction ready")
    else:
        music = existing_music
        emit("music", "done", "Keeping existing music direction")

    attempts: list[CongruenceAttempt] = []
    regen_count = 0
    last_report: CongruenceReport | None = None

    # Regenerate only failing modalities within the configured retry limit.
    for attempt_idx in range(0, max_regen + 1):
        emit(
            "congruence",
            "started",
            f"Judging fragrance and music congruence (attempt {attempt_idx + 1})",
        )
        report = compute_congruence(bad, fragrance, music)
        consistency = report.descriptor_consistency
        frag_ok = consistency.fragrance_aligns_descriptor
        music_ok = consistency.music_aligns_descriptor
        accepted = frag_ok and music_ok

        regenerated: list[str] = []
        will_regen = (not accepted) and (attempt_idx < max_regen)
        if will_regen:
            feedback = build_regen_feedback(consistency, report.summary)
            if not frag_ok:
                if verbose:
                    print(f"  Congruence regen: fragrance (attempt {attempt_idx + 1})")
                    if consistency.fragrance_score is not None:
                        print(f"    fragrance score: {consistency.fragrance_score}/5")
                emit(
                    "fragrance",
                    "started",
                    "Regenerating fragrance after congruence feedback",
                )
                fragrance = generate_fragrance(bad, judge_feedback=feedback)
                regenerated.append("fragrance")
                emit("fragrance", "done", "Updated fragrance concept ready")
            if not music_ok:
                if verbose:
                    print(f"  Congruence regen: music (attempt {attempt_idx + 1})")
                    if consistency.music_score is not None:
                        print(f"    music score: {consistency.music_score}/5")
                emit(
                    "music",
                    "started",
                    "Regenerating music text after congruence feedback",
                )
                music = generate_music_direction(bad, judge_feedback=feedback)
                regenerated.append("music")
                emit("music", "done", "Updated music direction ready")
            regen_count += 1

        attempt_record = CongruenceAttempt(
            attempt=attempt_idx + 1,
            fragrance_aligns_descriptor=frag_ok,
            music_aligns_descriptor=music_ok,
            details=consistency.details,
            summary=report.summary,
            regenerated=regenerated,
        )
        attempts.append(attempt_record)

        last_report = report.model_copy(
            update={
                "attempts": list(attempts),
                "regen_count": regen_count,
                "accepted": accepted,
            }
        )

        if accepted:
            if verbose:
                print(f"  Congruence accepted on attempt {attempt_idx + 1}.")
            emit("congruence", "done", "Congruence accepted")
            break
        if not will_regen:
            # Keep the latest outputs so the API can still show results.
            if verbose:
                print(
                    f"  Congruence still failing after {regen_count} regen(s); "
                    "continuing with best-effort outputs."
                )
            emit(
                "congruence",
                "done",
                "Congruence finished with best-effort outputs",
            )
            break

    assert last_report is not None

    # Synthesize audio once after the congruence loop finishes.
    if execution_id:
        emit("audio", "started", "Synthesizing final MusicGen audio for this run")
        try:
            audio_ref = synthesize_audio(music, execution_id, bad=bad)
        except Exception as e:
            emit("audio", "done", "Audio synthesis failed")
            raise RuntimeError(
                f"MusicGen audio is required and failed: {e}. "
                "Check MUSICGEN_BACKEND=replicate and the Replicate token."
            ) from e
        if not audio_ref:
            emit("audio", "done", "Audio was not created")
            raise RuntimeError(
                "MusicGen audio is required but was not created. "
                "Check MUSICGEN_BACKEND=replicate and the Replicate token "
                "(MUSICGEN_BACKEND=off skips synthesis)."
            )
        music = music.model_copy(update={"audio_sample_ref": audio_ref})
        emit("audio", "done", "Final audio reference ready")

    # CLIP scores are supportive only and do not decide acceptance.
    if image_data is not None:
        from src.services.clip_proxies import compute_clip_proxies

        emit("clip", "started", "Computing CLIP image–text similarity proxies")
        proxies = compute_clip_proxies(image_data, fragrance, music, settings=settings)
        last_report = last_report.model_copy(update={"automated_proxies": proxies})
        emit("clip", "done", "CLIP proxies recorded")
        if verbose and proxies.clip_score_image_fragrance_text is not None:
            print(
                f"  CLIP proxies: fragrance={proxies.clip_score_image_fragrance_text:.3f} "
                f"music={proxies.clip_score_image_music_text:.3f}"
            )

    return fragrance, music, last_report
