# Builds a music direction from the brand descriptor and may synthesize audio.
# Invents from the brand item sound world and avoids generic lobby defaults.

from __future__ import annotations
import json
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor
from src.models.music import MusicDirection
from src.services.audio_synthesis import synthesize_audio

# Prompt for producing a music direction grounded in the brand item sound world.
_SYSTEM_PROMPT = """\
You are a music direction assistant for a multisensory brand development system.
Given brand aesthetic attributes, invent a music direction for brand ambient audio.

Infer the SOUND WORLD of the actual brand_item — its object, place, craft, or cultural
setting — from brand_item + narrative + mood/texture. Do NOT default to a generic luxury
lobby, boutique cafe, hotel spa, or European salon (piano/cello/neo-classical) unless
that is genuinely what the object is.

Return ONLY a valid JSON object:

{
  "tempo": "...",
  "bpm": 96,
  "timbre": ["timbre1", "timbre2"],
  "instrumentation": ["instrument1", "instrument2"],
  "mood": "...",
  "style": "...",
  "music_signature": "2-5 sentence story of why this sound belongs to this brand"
}

RULES:
- tempo: free string matching energy level (e.g. "slow", "moderate", "uptempo", "cyclic-moderate")
- bpm: REQUIRED integer beats-per-minute between 40 and 200. Must match the tempo label
  and BAD energy (slow ≈ 60-80, moderate ≈ 88-110, uptempo/fast ≈ 118-140). Prefer a
  concrete producer number such as 72, 96, or 120 — not a range.
- timbre: 1-5 tonal qualities of the actual sound world (e.g. "warm pads",
  "bronze metallophones", "dry wood percussion", "breathy bamboo flute")
- instrumentation: 1-5 instruments that could plausibly belong to this object/place/craft.
  Mix freely across traditions when they fit. Examples (not a closed list): piano, cello,
  synth pads, suling, kendang, gamelan metallophones, kora, oud, erhu, shakuhachi, sitar,
  talking drum, mbira, rebab. Best is to have the combination of 3-4 instruments.
- mood: single word or short hyphenated emotional quality (e.g. "contemplative",
  "ceremonial", "uplifting")
- style: a short label, 1-3 words, hyphenated if needed. NOT limited to Western genre words.
  Examples: "ambient", "lo-fi", "neo-classical", "minimal", "contemporary-gamelan",
  "gamelan-lounge", "afro-minimal", "shakuhachi-ambient", "80s pop", "rock"
- music_signature: 2-5 sentences for a non-musician. Name the object/place/craft, say why
  these instruments and textures belong (not a generic elegant lobby), and describe how it
  should feel in a shop or ad. Mention the BPM once naturally if helpful.
  Example tone: "This is the sound of a batik workshop at warm dusk: interlocking bronze
  and wood, a cyclic pulse around 92 BPM, bamboo flute over a soft bed. It should feel
  crafted and ceremonial, not a European piano salon."
- Return ONLY valid JSON, no markdown fencing, no explanation."""

MUSIC_SYSTEM_PROMPT = _SYSTEM_PROMPT


# Builds the music user message from the brand descriptor and optional judge feedback.
def build_music_user_message(
    bad: BrandAestheticDescriptor,
    judge_feedback: str | None = None,
) -> str:
    profile = bad.to_generation_context()
    user_message = (
        "Based on this modality-neutral brand aesthetic descriptor, create a detailed, "
        "producer-ready music direction for brand ambient audio. Infer the musical identity "
        "from the brand_item, narrative, mood, energy, color_temperature, colours, texture, "
        "visual_style, and sensory_metaphors. The descriptor does not prescribe a genre, "
        "instrument, tempo, or musical answer, so choose these based on the specific character "
        "of the brand rather than defaulting to generic corporate, luxury-lobby, cinematic, "
        "or ambient music.\n\n"

        "Describe a distinctive sound world that could realistically guide music generation. "
        "Specify the most suitable genre or stylistic direction, approximate tempo or tempo "
        "feel, rhythmic character, drum and percussion style, bass character, main instruments, "
        "melodic elements, harmonic character, timbral palette, energy level, emotional tone, "
        "arrangement progression, and production texture. Be concrete about how the track "
        "should sound rather than relying only on abstract adjectives.\n\n"

        "For example, instead of saying only 'uplifting electronic music', describe something "
        "like: 'an energetic modern reggaeton-influenced track around 100 BPM, driven by a "
        "deep booming 808 kick and tight dembow-inspired rhythm, layered with crisp Latin "
        "percussion, syncopated shakers and hand drums, warm sub-bass, bright synth melodies, "
        "short rhythmic chord stabs, and subtle atmospheric pads. The arrangement should build "
        "gradually from a clean rhythmic opening into a fuller, confident groove, maintaining "
        "an uplifting and energizing character without becoming aggressive or club-heavy. "
        "Production should feel polished, spacious, contemporary, and brand-friendly, with "
        "controlled low end, clear percussion, and memorable melodic hooks.'\n\n"

        "Use that level of musical specificity, but do not copy the example unless it genuinely "
        "fits the descriptor. Every musical decision should be traceable to the supplied brand "
        "aesthetic. Avoid references to specific copyrighted songs or artists.\n\n"

        "Return tempo, bpm, timbre, instrumentation, mood, style, and music_signature. "
        "bpm must be an integer (40-200) consistent with tempo and brand energy. "
        "The music_signature should be a concise but detailed natural-language production brief "
        "that combines rhythm, bass, instrumentation, melodic/harmonic character, arrangement, "
        "energy, and production style into a description suitable for conditioning the audio "
        "generation model.\n\n"
        f"Brand Aesthetic Descriptor:\n{json.dumps(profile, indent=2)}"
    )
    if judge_feedback and judge_feedback.strip():
        user_message += (
            "\n\nA congruence judge rejected the previous music direction. "
            "Revise tempo/bpm/timbre/instrumentation/mood/style/music_signature so it "
            "better fits the descriptor. Judge feedback:\n"
            f"{judge_feedback.strip()}"
        )
    return user_message


def _get_settings() -> Settings:
    return Settings()


def _require_api_key(settings: Settings) -> None:
    from src.services.llm_chat import TextRole, require_role_credentials

    require_role_credentials(TextRole.SPECIALIST, settings)


# Returns a validated music direction without synthesizing audio.
def generate_music_direction(
    bad: BrandAestheticDescriptor,
    judge_feedback: str | None = None,
) -> MusicDirection:
    settings = _get_settings()
    _require_api_key(settings)

    from src.services.llm_chat import TextRole, chat_completion

    user_message = build_music_user_message(bad, judge_feedback=judge_feedback)

    try:
        content = chat_completion(
            TextRole.SPECIALIST,
            system=_SYSTEM_PROMPT,
            user=user_message,
            temperature=0.5,
            max_tokens=2400,
            settings=settings,
        )
    except Exception as e:
        raise RuntimeError(f"Music generation failed: {e}") from e

    if not content:
        raise RuntimeError("Music generation returned empty response")

    cleaned = content.strip().strip("```").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Music generation returned invalid JSON: {content[:200]}") from e

    try:
        return MusicDirection(**data)
    except Exception as e:
        raise RuntimeError(f"Music response does not match schema: {e}") from e


# Generates the music direction and synthesizes audio when an execution id is given.
def generate_music(
    bad: BrandAestheticDescriptor,
    execution_id: str | None = None,
    judge_feedback: str | None = None,
) -> MusicDirection:
    direction = generate_music_direction(bad, judge_feedback=judge_feedback)

    if execution_id:
        audio_ref = synthesize_audio(direction, execution_id, bad=bad)
        if not audio_ref:
            raise RuntimeError(
                "MusicGen audio is required but was not created. "
                "Check MUSICGEN_BACKEND=replicate and the Replicate token."
            )
        direction = direction.model_copy(update={"audio_sample_ref": audio_ref})

    return direction
