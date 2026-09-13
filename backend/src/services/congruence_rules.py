# Rule based checks for energy mood tempo and intensity clashes before the judge runs.
# Hard fails force rejection later. Soft temperature flags only inform the judge.
from __future__ import annotations
import re
from dataclasses import dataclass, field
from src.models.descriptor import BrandAestheticDescriptor, ColorTemperature, EnergyLevel
from src.models.fragrance import FragranceConcept, IntensityProfile
from src.models.music import MusicDirection

_SLOW_TEMPO = re.compile(
    r"\b(very\s+slow|slow|leisurely|languid|relaxed|downtempo|adagio)\b", re.I
)
_FAST_TEMPO = re.compile(
    r"\b(very\s+fast|fast|uptempo|up-tempo|energetic|driving|allegro|brisk)\b", re.I
)
_AGGRESSIVE_MUSIC = re.compile(
    r"\b(edm|techno|dubstep|metal|punk|hip[\s-]?hop|trap|drum[\s-]?and[\s-]?bass|hardcore)\b",
    re.I,
)
_CALM_BAD = re.compile(r"\b(calm|serene|peaceful|hushed|quiet|gentle|soft|intimate)\b", re.I)
_ENERGETIC_BAD = re.compile(
    r"\b(energetic|bold|dynamic|vibrant|lively|powerful|intense|exciting)\b", re.I
)


@dataclass
class RuleCheckResult:
    fragrance_issues: list[str] = field(default_factory=list)
    music_issues: list[str] = field(default_factory=list)
    critical_fragrance_fail: bool = False
    critical_music_fail: bool = False

    def summary_for_judge(self) -> str:
        lines: list[str] = []
        if self.fragrance_issues:
            lines.append("Fragrance rule flags:")
            lines.extend(f"  - {i}" for i in self.fragrance_issues)
        if self.music_issues:
            lines.append("Music rule flags:")
            lines.extend(f"  - {i}" for i in self.music_issues)
        return "\n".join(lines) if lines else "No deterministic rule flags."


def _energy_band(energy: EnergyLevel) -> str:
    if energy in (EnergyLevel.VERY_LOW, EnergyLevel.LOW):
        return "low"
    if energy == EnergyLevel.MODERATE:
        return "moderate"
    return "high"


def _music_blob(music: MusicDirection) -> str:
    return " ".join(
        [
            music.tempo,
            music.mood,
            music.style,
            music.music_signature,
            *music.timbre,
            *music.instrumentation,
        ]
    )


def _fragrance_blob(fragrance: FragranceConcept) -> str:
    guide_text = [
        f"{entry.ingredient} {entry.smells_like}" for entry in fragrance.note_guide
    ]
    return " ".join(
        [
            fragrance.intensity_profile.value,
            fragrance.smell_signature,
            *fragrance.dominant_accords,
            *fragrance.emotional_descriptors,
            *fragrance.top_notes,
            *fragrance.heart_notes,
            *fragrance.base_notes,
            *guide_text,
        ]
    )


# Runs the rule based congruence checks for fragrance and music.
def run_rule_checks(
    bad: BrandAestheticDescriptor,
    fragrance: FragranceConcept,
    music: MusicDirection,
) -> RuleCheckResult:
    result = RuleCheckResult()
    band = _energy_band(bad.energy)
    tempo = music.tempo or ""
    music_text = _music_blob(music)
    frag_text = _fragrance_blob(fragrance)
    bad_mood = " ".join(bad.mood)

    # Flag when brand energy is high but music tempo is clearly slow.
    if band == "high" and _SLOW_TEMPO.search(tempo) and not _FAST_TEMPO.search(tempo):
        result.music_issues.append(
            f"BAD energy is {bad.energy.value} but music tempo is '{music.tempo}' (too slow)."
        )
        result.critical_music_fail = True

    # Flag when brand energy is low but music tempo is clearly fast.
    if band == "low" and _FAST_TEMPO.search(tempo) and not _SLOW_TEMPO.search(tempo):
        result.music_issues.append(
            f"BAD energy is {bad.energy.value} but music tempo is '{music.tempo}' (too fast)."
        )
        result.critical_music_fail = True

    # Flag when brand mood is calm but music sounds aggressive.
    if _CALM_BAD.search(bad_mood) and _AGGRESSIVE_MUSIC.search(music_text):
        result.music_issues.append(
            f"BAD mood suggests calm ({bad.mood[:2]}) but music style/instrumentation "
            f"looks aggressive ({music.style}, {music.instrumentation[:2]})."
        )
        result.critical_music_fail = True

    # Flag energetic brand mood paired with slow ambient style music.
    if _ENERGETIC_BAD.search(bad_mood) and _SLOW_TEMPO.search(tempo):
        if music.style.lower() in {"ambient", "minimal", "drone"} and band == "high":
            result.music_issues.append(
                f"BAD mood/energy suggest drive but music is slow {music.style} at '{music.tempo}'."
            )
            result.critical_music_fail = True

    # Flag when fragrance intensity does not match brand energy.
    if bad.energy in (EnergyLevel.VERY_HIGH, EnergyLevel.HIGH):
        if fragrance.intensity_profile == IntensityProfile.LIGHT:
            result.fragrance_issues.append(
                f"BAD energy is {bad.energy.value} but fragrance intensity is light."
            )
            result.critical_fragrance_fail = True

    if bad.energy in (EnergyLevel.VERY_LOW, EnergyLevel.LOW):
        if fragrance.intensity_profile == IntensityProfile.BOLD:
            result.fragrance_issues.append(
                f"BAD energy is {bad.energy.value} but fragrance intensity is bold."
            )
            result.critical_fragrance_fail = True

    # Flag when fragrance emotion language conflicts with brand mood.
    if _CALM_BAD.search(bad_mood) and _ENERGETIC_BAD.search(frag_text):
        if not _CALM_BAD.search(frag_text):
            result.fragrance_issues.append(
                "BAD mood is calm/soft but fragrance emotional descriptors feel energetic."
            )
            result.critical_fragrance_fail = True

    if _ENERGETIC_BAD.search(bad_mood) and _CALM_BAD.search(frag_text):
        if not _ENERGETIC_BAD.search(frag_text):
            result.fragrance_issues.append(
                "BAD mood is energetic but fragrance emotional descriptors feel too subdued."
            )
            # Treat as a hard fail only when brand energy is already high.
            if band == "high":
                result.critical_fragrance_fail = True

    # Soft flag when color temperature cues conflict with fragrance accords.
    if bad.color_temperature == ColorTemperature.COOL:
        warm_only = re.search(r"\b(cozy warmth|amber warmth|gourmand|spicy heat)\b", frag_text, re.I)
        if warm_only and not re.search(r"\b(fresh|crisp|cool|marine|mint|citrus)\b", frag_text, re.I):
            result.fragrance_issues.append(
                "BAD color_temperature is cool but fragrance accords read predominantly warm."
            )

    if bad.color_temperature == ColorTemperature.WARM:
        cold_only = re.search(r"\b(icy|polar|ozonic|metallic cold)\b", frag_text, re.I)
        if cold_only and not re.search(r"\b(warm|amber|vanilla|musk|cozy)\b", frag_text, re.I):
            result.fragrance_issues.append(
                "BAD color_temperature is warm but fragrance accords read predominantly cold."
            )

    return result
