"use client";

/**
 * Results page.
 * Shows brand fragrance music audio rationale and rating or save actions.
 */

import { useEffect, useRef, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
// Reference: https://motion.dev/docs/react-quick-start
import { motion } from "motion/react";
import Navbar from "@/components/Navbar";
import GoldButton from "@/components/GoldButton";
import PhotoFrame from "@/components/PhotoFrame";
import PipelineShell from "@/components/PipelineShell";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import AudioWavePlayer from "@/components/AudioWavePlayer";
import EvaluationCard from "@/components/EvaluationCard";
import { saveArchive } from "@/lib/archive";
import { DEMO_RESULT } from "@/lib/demoResult";
import { refineConcept, resolveAudioUrl } from "@/lib/api";
import { downloadReportPack } from "@/lib/reportPack";
import { resolvePalette } from "@/lib/colors";
import {
  isEvaluationStimulus,
  isRatingSession,
  setRatingSession,
} from "@/lib/rating";
import { brandRunShortId, type ApiResult, type FragranceConcept } from "@/lib/types";

const STACK_REST = [
  { rotate: -22, x: -110, y: 26 },
  { rotate: -16, x: -82, y: 18 },
  { rotate: -10, x: -54, y: 12 },
  { rotate: -5, x: -28, y: 6 },
  { rotate: -2, x: -8, y: 2 },
  { rotate: 1, x: 10, y: 6 },
  { rotate: 4, x: 28, y: 12 },
];

const STACK_REST_MOBILE = [
  { rotate: -10, x: -36, y: 12 },
  { rotate: -7, x: -24, y: 8 },
  { rotate: -4, x: -12, y: 5 },
  { rotate: -1, x: 0, y: 2 },
  { rotate: 2, x: 10, y: 4 },
  { rotate: 5, x: 20, y: 7 },
  { rotate: 8, x: 30, y: 10 },
];

const STACK_HOVER = [
  { rotate: -32, x: -190, y: 40 },
  { rotate: -24, x: -145, y: 30 },
  { rotate: -16, x: -100, y: 20 },
  { rotate: -8, x: -55, y: 10 },
  { rotate: -2, x: -18, y: 4 },
  { rotate: 4, x: 16, y: 8 },
  { rotate: 10, x: 48, y: 16 },
];

const STACK_HOVER_MOBILE = [
  { rotate: -14, x: -52, y: 16 },
  { rotate: -10, x: -36, y: 12 },
  { rotate: -6, x: -20, y: 8 },
  { rotate: -2, x: -4, y: 4 },
  { rotate: 2, x: 12, y: 4 },
  { rotate: 6, x: 26, y: 8 },
  { rotate: 10, x: 40, y: 12 },
];

const PILE_REST_X = [-72, -48, -24, 0, 24, 48, 72];
const PILE_REST_X_MOBILE = [-28, -18, -8, 0, 8, 18, 28];
const PILE_HOVER_X = [-120, -80, -40, 0, 40, 80, 120];
const PILE_HOVER_X_MOBILE = [-40, -26, -12, 0, 12, 26, 40];

const DEALT_PARK = [
  { rotate: -26, x: -150, y: 28 },
  { rotate: -22, x: -138, y: 24 },
  { rotate: -18, x: -126, y: 20 },
  { rotate: -14, x: -114, y: 16 },
  { rotate: -10, x: -102, y: 12 },
  { rotate: -6, x: -90, y: 8 },
  { rotate: -2, x: -78, y: 4 },
];

const DEALT_PARK_MOBILE = [
  { rotate: -12, x: -42, y: 12 },
  { rotate: -10, x: -36, y: 10 },
  { rotate: -8, x: -30, y: 8 },
  { rotate: -6, x: -24, y: 6 },
  { rotate: -4, x: -18, y: 4 },
  { rotate: -2, x: -12, y: 2 },
  { rotate: 0, x: -6, y: 0 },
];

type CardKind =
  | "top"
  | "heart"
  | "base"
  | "accords"
  | "intensity"
  | "emotions"
  | "signature";

const CARD_FACES: Array<{ kind: CardKind; title: string; blurb: string }> = [
  { kind: "top", title: "Top Notes", blurb: "Opening chemicals from the concept" },
  { kind: "heart", title: "Heart Notes", blurb: "Mid-layer chemicals from the concept" },
  { kind: "base", title: "Base Notes", blurb: "Dry-down chemicals from the concept" },
  { kind: "accords", title: "Dominant Accords", blurb: "Main scent families" },
  { kind: "intensity", title: "Intensity Profile", blurb: "Overall strength of the fragrance" },
  { kind: "emotions", title: "Emotional Descriptors", blurb: "Feelings the scent evokes" },
  { kind: "signature", title: "Smell Signature", blurb: "Full fragrance narrative" },
];

const FRAG_CARD_SIZE =
  "size-[220px] sm:size-[280px] lg:size-[320px] rounded-[28px]";
const FRAG_CARD = `${FRAG_CARD_SIZE} bg-lemon`;

function joinList(items?: string[]) {
  return (items || []).filter(Boolean).join(", ") || "—";
}

/** Strip leftover markdown emphasis for display (also cleaned on backend). */
function plainText(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/(?<!\w)_(.+?)_(?!\w)/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/__/g, "")
    .replace(/\*\*/g, "");
}

function splitRationale(text: string): Array<{ title?: string; body: string }> {
  const cleaned = plainText(text);
  const chunks = cleaned
    .split(/\n(?=##\s)/)
    .map((c) => c.trim())
    .filter(Boolean);

  if (chunks.length === 0) return [{ body: cleaned }];

  return chunks.map((chunk) => {
    const match = chunk.match(/^##\s+(.+?)\n([\s\S]*)$/);
    if (match) return { title: match[1].trim(), body: match[2].trim() };
    return { body: chunk.replace(/^##\s+/, "").trim() };
  });
}

function formatClip(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "—";
  // Backend stores CLIPScore = 2.5 * cosine (typical range ~0–2.5). Show as %.
  const pct = Math.round(Math.min(100, Math.max(0, (score / 2.5) * 100)));
  return `${pct}%`;
}

function noteNames(frag: FragranceConcept, kind: CardKind): string[] {
  if (kind === "top") return frag.top_notes || [];
  if (kind === "heart") return frag.heart_notes || [];
  if (kind === "base") return frag.base_notes || [];
  return [];
}

function notesForCard(frag: FragranceConcept, kind: CardKind) {
  const guide = frag.note_guide || [];
  return noteNames(frag, kind).map((name) => {
    const hit = guide.find(
      (g) => (g.chemical_name || g.ingredient).toLowerCase() === name.toLowerCase()
    );
    return {
      chemical_name: hit?.chemical_name || name,
      ingredient: hit?.ingredient || name,
      smells_like: hit?.smells_like || "—",
    };
  });
}

function clipText(s: string, n = 72) {
  return s.length > n ? `${s.slice(0, n).trimEnd()}…` : s;
}

function previewForCard(frag: FragranceConcept, kind: CardKind): string {
  if (kind === "top" || kind === "heart" || kind === "base") {
    const notes = noteNames(frag, kind);
    const fallback = CARD_FACES.find((c) => c.kind === kind)?.title || "";
    return notes.length ? clipText(notes.join(" · "), 80) : fallback;
  }
  if (kind === "signature") {
    return frag.smell_signature
      ? clipText(frag.smell_signature, 90)
      : "Smell Signature";
  }
  if (kind === "accords") {
    const items = frag.dominant_accords || [];
    return items.length ? clipText(items.join(" · ")) : "Dominant Accords";
  }
  if (kind === "intensity") return frag.intensity_profile || "Intensity Profile";
  const emotions = frag.emotional_descriptors || [];
  return emotions.length ? clipText(emotions.join(" · ")) : "Emotional Descriptors";
}

export default function ResultsPage() {
  const router = useRouter();
  const { isAdmin } = useAuth();

  // Result payload and image from sessionStorage
  const [result, setResult] = useState<ApiResult | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  // Refine feedback form
  const [feedback, setFeedback] = useState("");
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);
  const [clarify, setClarify] = useState<string | null>(null);

  // Save / download / share actions
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Fragrance card stack UI
  const [stackHover, setStackHover] = useState(false);
  const [pileHover, setPileHover] = useState(false);
  const [hoverCard, setHoverCard] = useState<number | null>(null);
  const [dealtPile, setDealtPile] = useState<number[]>([]);
  const [slotFlipped, setSlotFlipped] = useState(false);
  const [colorTip, setColorTip] = useState<string | null>(null);
  const [compactCards, setCompactCards] = useState(false);

  // Shared study rating mode
  const [ratingStimulus, setRatingStimulus] = useState(false);
  const [stimulusKnown, setStimulusKnown] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [sharedStudy, setSharedStudy] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);
  const slotClickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Participants cannot refine admin-curated rating stimuli; admins still can.
  const refineLocked = !isAdmin && (isRatingSession() || ratingStimulus);

  useEffect(() => {
    const sync = () => setCompactCards(window.innerWidth < 640);
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, []);

  // Keep results in sync with sessionStorage
  const persistResult = (next: ApiResult) => {
    setResult(next);
    sessionStorage.setItem("bb_result", JSON.stringify(next));
  };

  // Deal a fragrance card into the pile (or return it)
  const dealCard = (index: number) => {
    if (dealtPile.includes(index)) {
      setDealtPile((prev) => prev.filter((i) => i !== index));
      setSlotFlipped(false);
      return;
    }
    setDealtPile((prev) => [...prev, index]);
    setSlotFlipped(false);
  };

  // Return the top dealt card to the stack
  const returnTopCard = () => {
    if (slotClickTimer.current) {
      clearTimeout(slotClickTimer.current);
      slotClickTimer.current = null;
    }
    setDealtPile((prev) => prev.slice(0, -1));
    setSlotFlipped(false);
  };

  // Single click flips; double click returns the card
  const onSlotActivate = () => {
    if (slotClickTimer.current) {
      clearTimeout(slotClickTimer.current);
      slotClickTimer.current = null;
      returnTopCard();
      return;
    }
    slotClickTimer.current = setTimeout(() => {
      slotClickTimer.current = null;
      setSlotFlipped((f) => !f);
    }, 220);
  };

  // Send feedback to the refine API
  const submitRefine = async () => {
    if (!result || !feedback.trim() || refining || refineLocked) return;
    setRefining(true);
    setRefineError(null);
    setClarify(null);

    try {
      const body = await refineConcept(result.execution_id, feedback.trim());
      if (body.success === false) {
        setClarify(
          body.clarification_request || "Could you clarify your request?"
        );
        return;
      }
      persistResult(body as ApiResult);
      setFeedback("");
      setSaved(false);
    } catch (e) {
      setRefineError(e instanceof Error ? e.message : "Refine failed");
    } finally {
      setRefining(false);
    }
  };

  useEffect(() => {
    const isDemo = new URLSearchParams(window.location.search).get("demo") === "1";

    if (isDemo) {
      sessionStorage.setItem("bb_result", JSON.stringify(DEMO_RESULT));
      setResult(DEMO_RESULT);
      setImagePreview(sessionStorage.getItem("bb_image_b64"));
      return;
    }

    const stored = sessionStorage.getItem("bb_result");
    if (!stored) {
      router.push("/");
      return;
    }
    try {
      const parsed = JSON.parse(stored) as ApiResult;
      setResult(parsed);
      setImagePreview(sessionStorage.getItem("bb_image_b64"));
    } catch {
      router.push("/");
    }
  }, [router]);

  useEffect(() => {
    if (!result?.execution_id) {
      setRatingStimulus(false);
      setStimulusKnown(true);
      return;
    }
    let cancelled = false;
    setStimulusKnown(false);
    void isEvaluationStimulus(result.execution_id).then((yes) => {
      if (cancelled) return;
      setRatingStimulus(yes);
      setSharedStudy(yes);
      if (yes) setRatingSession(true);
      setStimulusKnown(true);
    });
    return () => {
      cancelled = true;
    };
  }, [result?.execution_id]);

  // Persist to Supabase Library when a real result is opened (idempotent upsert)
  useEffect(() => {
    if (!result || !stimulusKnown) return;
    const isDemo = new URLSearchParams(window.location.search).get("demo") === "1";
    if (isDemo) return;
    // Do not archive admin rating stimuli into a participant library
    if (refineLocked) return;

    let cancelled = false;
    (async () => {
      try {
        const entry = await saveArchive(
          result,
          sessionStorage.getItem("bb_image_b64")
        );
        if (cancelled) return;
        // Keep player on the same durable URL that was just uploaded (avoid
        // backend path vs Supabase path mismatch after save).
        setResult(entry.result);
        setSaved(true);
        setSharedStudy(entry.isShared);
        setSaveError(null);
      } catch (e) {
        if (!cancelled) {
          setSaveError(
            e instanceof Error ? e.message : "Could not sync archive to Library"
          );
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // Sync once per execution once we know it is not a rating stimulus
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result?.execution_id, stimulusKnown, refineLocked]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dealtPile.length > 0) {
        returnTopCard();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dealtPile.length]);

  if (!result) return null;

  const { fragrance_concept: frag, music_direction: music, rationale, brand_aesthetic_descriptor: desc } =
    result;
  const congruence = result.congruence_report || {};
  const fragScore = congruence.descriptor_consistency?.fragrance_score;
  const musicScore = congruence.descriptor_consistency?.music_score;
  const clipFrag = congruence.automated_proxies?.clip_score_image_fragrance_text;
  const clipMusic = congruence.automated_proxies?.clip_score_image_music_text;
  const audioSrc =
    resolveAudioUrl(music.audio_sample_ref || result.audio_sample_ref || null) ??
    undefined;
  const tags = [
    music.bpm != null ? `${music.bpm} BPM` : null,
    ...(music.instrumentation || []),
  ].filter(Boolean) as string[];
  const colors = resolvePalette(desc.colours, desc.color_temperature);
  const source = (frag.pyrfume_sources || []).join(", ");
  const topDealt =
    dealtPile.length > 0 ? dealtPile[dealtPile.length - 1] : null;
  const activeFace =
    topDealt != null ? CARD_FACES[topDealt] : CARD_FACES[0];

  const pileX = (pilePos: number, total: number) => {
    if (total <= 1) return 0;
    const xs = compactCards
      ? pileHover
        ? PILE_HOVER_X_MOBILE
        : PILE_REST_X_MOBILE
      : pileHover
        ? PILE_HOVER_X
        : PILE_REST_X;
    return xs[Math.round((pilePos / (total - 1)) * (xs.length - 1))];
  };

  const stackRest = compactCards ? STACK_REST_MOBILE : STACK_REST;
  const stackHoverPos = compactCards ? STACK_HOVER_MOBILE : STACK_HOVER;
  const dealtPark = compactCards ? DEALT_PARK_MOBILE : DEALT_PARK;

  const downloadReport = async () => {
    if (!result || downloading) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadReportPack(result, imagePreview);
    } catch (e) {
      setDownloadError(
        e instanceof Error ? e.message : "Could not build the report pack"
      );
    } finally {
      setDownloading(false);
    }
  };

  const onSave = async () => {
    if (!result || saving || refineLocked) return;
    setSaving(true);
    setSaveError(null);
    try {
      const entry = await saveArchive(result, imagePreview);
      setResult(entry.result);
      setSaved(true);
      setSharedStudy(entry.isShared);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not save to Library");
      setSaved(false);
    } finally {
      setSaving(false);
    }
  };

  const onShareStudy = async () => {
    if (!result || !isAdmin || sharing || refineLocked) return;
    setSharing(true);
    setShareError(null);
    try {
      const entry = await saveArchive(result, imagePreview, { shared: true });
      setResult(entry.result);
      setSaved(true);
      setSharedStudy(true);
      setRatingStimulus(true);
      setRatingSession(true);
    } catch (e) {
      setShareError(
        e instanceof Error
          ? e.message
          : "Could not add to shared library"
      );
    } finally {
      setSharing(false);
    }
  };

  return (
    <RequireAuth>
    <main id="main-content" className="min-h-screen bg-ink flex flex-col overflow-x-hidden">
      <Navbar />

      <PipelineShell title="Orchestration Result" className="pb-16">
        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(280px,0.92fr)_1.2fr] gap-8 items-stretch">
          {/* Brand photo and colour strip */}
          <PhotoFrame className="h-full min-h-[360px] sm:min-h-[560px]" innerClassName="flex flex-col h-full">
            <div className="flex-1 min-h-0">
              {imagePreview ? (
                <img
                  src={imagePreview}
                  alt="Brand image"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="h-full min-h-[360px]" />
              )}
            </div>
            <div className="h-[92px] flex shrink-0 relative">
              {colors.map((c, i) => (
                <div
                  key={`${c.hex}-${i}`}
                  className="flex-1 relative cursor-help group"
                  style={{ background: c.hex }}
                  onMouseEnter={() => setColorTip(`${c.label} · ${c.hex}`)}
                  onMouseLeave={() => setColorTip(null)}
                  title={`${c.label} (${c.hex})`}
                >
                  <span className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink/90 px-2 py-1 text-[11px] font-mono text-gold opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
                    {c.hex}
                  </span>
                </div>
              ))}
              {colorTip && (
                <p className="pointer-events-none absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-ink/85 px-3 py-1 text-[11px] text-white/90">
                  {colorTip}
                </p>
              )}
            </div>
          </PhotoFrame>

          <div className="flex flex-col gap-5 min-h-[560px]">
            {/* Visual analysis panel */}
            <section className="bg-lemon rounded-[30px] px-5 sm:px-8 py-6 sm:py-7 flex-[1.05] flex flex-col overflow-hidden">
              <p className="text-black text-xl font-bold mb-4">
                Visual Analysis
              </p>
              <div className="flex flex-col md:flex-row gap-5 md:gap-7 text-[15px] text-black flex-1 min-h-0">
                <div className="flex flex-col gap-2.5 shrink-0 w-full md:w-[300px] min-w-0">
                  {[
                    { label: "Mood", value: joinList(desc.mood) },
                    { label: "Energy", value: desc.energy || "—" },
                    {
                      label: "Colours",
                      value: joinList(desc.colours || []),
                    },
                    { label: "Texture", value: joinList(desc.texture) },
                    {
                      label: "Sensory metaphors",
                      value: joinList(desc.sensory_metaphors),
                    },
                  ].map((row, i) => (
                    <div
                      key={row.label}
                      className="grid grid-cols-[110px_1fr] sm:grid-cols-[140px_1fr] gap-2 sm:gap-3 items-baseline min-w-0"
                    >
                      <motion.span
                        className="font-normal text-black/70"
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.08 + i * 0.07, duration: 0.3 }}
                      >
                        {row.label}
                      </motion.span>
                      <HoverReveal
                        label={row.label}
                        value={row.value}
                        delay={0.14 + i * 0.07}
                      />
                    </div>
                  ))}
                </div>
                <motion.p
                  className="font-light leading-[25px] flex-1 text-black/85 min-w-0"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4, duration: 0.4 }}
                >
                  {desc.narrative || ""}
                </motion.p>
              </div>
              <p className="text-[11px] font-light text-black/40 mt-3">
                Hover a truncated line to read the full text
              </p>
            </section>

            {/* Music sample player */}
            <section className="bg-music rounded-[30px] px-8 py-7 flex-[1.15] flex flex-col">
              <p className="text-black text-xl font-bold mb-4">
                Music Generation
              </p>
              <AudioWavePlayer
                src={audioSrc}
                colors={colors.map((c) => c.hex)}
                className="flex-1"
              />
              <p className="text-[11px] font-mono text-black/45 mt-2">
                Now playing {brandRunShortId(result.execution_id)}
              </p>
              <div className="flex flex-wrap gap-3 mt-4">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="bg-nav rounded-full px-4 py-1.5 text-[15px] font-bold text-black"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <p className="text-[12px] font-light text-black mt-3 leading-[25px]">
                {music.music_signature ||
                  [music.style, music.tempo, music.mood].filter(Boolean).join(" · ")}
              </p>
            </section>
          </div>
        </div>

        {/* Fragrance card stack */}
        <section className="mt-14 sm:mt-20 overflow-x-hidden">
          <div className="text-center mb-8 sm:mb-10 px-2 sm:px-4">
            <h2 className="text-white text-2xl sm:text-3xl lg:text-4xl font-normal tracking-wide">
              Fragrance Concept
            </h2>
            <p className="text-white/55 text-[14px] sm:text-[15px] font-light mt-3 max-w-xl mx-auto leading-relaxed">
              Deal cards from the left deck into the reading pile to explore
              notes, accords, intensity, emotion, and the smell signature.
            </p>
          </div>

          <div className="flex flex-col lg:flex-row items-center justify-center gap-10 sm:gap-16 lg:gap-40 xl:gap-52 px-2 sm:px-6 lg:px-16 overflow-x-hidden">
          <div className="relative flex flex-col items-center w-[min(100%,280px)] sm:w-[min(100%,380px)] mx-auto">
            <p className="text-gold text-[13px] font-normal mb-4">
              Concept deck
            </p>
            <motion.div
              className={`relative ${FRAG_CARD_SIZE} shrink-0 overflow-visible mx-auto`}
              onHoverStart={() => setStackHover(true)}
              onHoverEnd={() => {
                setStackHover(false);
                setHoverCard(null);
              }}
            >
              {stackRest.map((rest, i) => {
                const hover = stackHoverPos[i];
                const park = dealtPark[i];
                const isDealt = dealtPile.includes(i);
                const pose = isDealt ? park : stackHover ? hover : rest;
                const face = CARD_FACES[i];
                const isPeek = hoverCard === i && !isDealt;
                return (
                  <motion.button
                    key={i}
                    type="button"
                    className="absolute inset-0 bg-lemon rounded-[28px] flex flex-col items-center justify-center shadow-[0_10px_28px_rgba(0,0,0,0.28)] cursor-pointer border-0 p-0 outline-none"
                    initial={false}
                    animate={{
                      rotate: pose.rotate,
                      x: pose.x,
                      y: isPeek ? pose.y - 18 : pose.y,
                      opacity: isDealt ? 0.35 : 1,
                      scale: isDealt ? 0.92 : isPeek ? 1.08 : 1,
                    }}
                    transition={{
                      type: "spring",
                      stiffness: stackHover ? 280 : 220,
                      damping: stackHover ? 18 : 22,
                      mass: 0.85,
                    }}
                    style={{ zIndex: isDealt ? 0 : isPeek ? 40 : i + 1 }}
                    onHoverStart={() => setHoverCard(i)}
                    onHoverEnd={() =>
                      setHoverCard((cur) => (cur === i ? null : cur))
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      dealCard(i);
                    }}
                    aria-label={isDealt ? `Return ${face.title}` : `Deal ${face.title}`}
                  >
                    <p className="text-black text-[18px] lg:text-[20px] font-bold text-center px-5 leading-tight">
                      {face.title}
                    </p>
                    <motion.p
                      className="text-black/50 text-[11px] font-light text-center px-5 mt-2 leading-snug max-w-[85%]"
                      initial={false}
                      animate={{
                        opacity: isPeek ? 1 : 0,
                        y: isPeek ? 0 : 6,
                      }}
                      transition={{ duration: 0.18 }}
                    >
                      {face.blurb}
                    </motion.p>
                  </motion.button>
                );
              })}
            </motion.div>

            <div className="relative z-50 h-20 mt-6 w-full max-w-[360px] flex items-start justify-center">
              {hoverCard != null && !dealtPile.includes(hoverCard) && (
                <motion.div
                  key={hoverCard}
                  initial={{ opacity: 0, y: 8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  className="w-full rounded-[18px] bg-ink-overlay/95 border border-gold/35 px-4 py-3 shadow-[0_12px_28px_rgba(0,0,0,0.45)]"
                >
                  <p className="text-gold text-[13px] font-bold">
                    {CARD_FACES[hoverCard].title}
                  </p>
                  <p className="text-white/75 text-[12px] font-light leading-snug mt-1 line-clamp-3">
                    {previewForCard(frag, CARD_FACES[hoverCard].kind)}
                  </p>
                </motion.div>
              )}
            </div>
          </div>

          <div className="relative shrink-0 w-[min(100%,280px)] sm:w-[min(100%,420px)] flex flex-col items-center mx-auto">
            <p className="text-gold text-[13px] font-normal mb-4 relative z-[1]">
              Reading pile
            </p>
            <div className="relative">
              <div className="absolute -inset-2 rounded-[32px] border border-dashed border-white/85 pointer-events-none z-0" />

            {dealtPile.length === 0 ? (
              <div
                className={`${FRAG_CARD_SIZE} flex items-center justify-center relative z-[1]`}
                aria-hidden
              >
                <p className="text-white/35 text-sm font-light tracking-wide text-center px-6">
                  Deal cards here to build a pile
                </p>
              </div>
            ) : (
              <motion.div
                className={`relative ${FRAG_CARD_SIZE} z-[1] overflow-visible`}
                onHoverStart={() => setPileHover(true)}
                onHoverEnd={() => setPileHover(false)}
              >
                {dealtPile.map((cardIdx, pilePos) => {
                  const isTop = pilePos === dealtPile.length - 1;
                  const face = CARD_FACES[cardIdx];
                  const x = pileX(pilePos, dealtPile.length);

                  if (!isTop) {
                    return (
                      <motion.div
                        key={`pile-${cardIdx}`}
                        className="absolute inset-0 bg-lemon rounded-[28px] flex flex-col items-center justify-center shadow-[0_8px_20px_rgba(0,0,0,0.22)] pointer-events-none"
                        initial={{ opacity: 0, x: -24, scale: 0.96 }}
                        animate={{ opacity: 1, x, scale: 1 }}
                        transition={{ type: "spring", stiffness: 260, damping: 24 }}
                        style={{ zIndex: pilePos }}
                      >
                        <p className="text-black text-[16px] lg:text-[18px] font-bold text-center px-5">
                          {face.title}
                        </p>
                      </motion.div>
                    );
                  }

                  return (
                    <div
                      key={`pile-top-${cardIdx}`}
                      className="absolute inset-0"
                      style={{ perspective: 1400, zIndex: pilePos + 1 }}
                    >
                      <motion.button
                        type="button"
                        className={`relative block ${FRAG_CARD_SIZE} cursor-pointer outline-none border-0 bg-transparent p-0 text-left`}
                        initial={{ opacity: 0, scale: 0.92, x: -24 }}
                        animate={{ opacity: 1, scale: 1, x }}
                        transition={{ type: "spring", stiffness: 280, damping: 24 }}
                        onClick={(e) => {
                          if ((e.target as HTMLElement).closest(".bb-scroll")) return;
                          onSlotActivate();
                        }}
                        aria-label={
                          slotFlipped
                            ? `Flip back to ${activeFace.title}`
                            : `Flip ${activeFace.title}`
                        }
                      >
                        <motion.div
                          className={`relative ${FRAG_CARD_SIZE}`}
                          animate={{ rotateY: slotFlipped ? 180 : 0 }}
                          transition={{ duration: 0.55, ease: "easeOut" }}
                          style={{ transformStyle: "preserve-3d" }}
                        >
                          <div
                            className={`${FRAG_CARD} absolute inset-0 flex flex-col items-center justify-center px-6 shadow-[0_10px_28px_rgba(0,0,0,0.28)]`}
                            style={{
                              backfaceVisibility: "hidden",
                              WebkitBackfaceVisibility: "hidden",
                            }}
                          >
                            <p className="text-black text-[20px] lg:text-[22px] font-bold text-center leading-tight">
                              {activeFace.title}
                            </p>
                            <p className="text-black/50 text-[12px] font-light text-center mt-3 px-2 leading-snug">
                              {activeFace.blurb}
                            </p>
                          </div>

                          <div
                            className={`${FRAG_CARD} absolute inset-0 px-6 py-5 text-black flex flex-col overflow-hidden shadow-[0_10px_28px_rgba(0,0,0,0.28)]`}
                            style={{
                              backfaceVisibility: "hidden",
                              WebkitBackfaceVisibility: "hidden",
                              transform: "rotateY(180deg)",
                            }}
                          >
                            <p className="text-[17px] lg:text-[19px] font-bold shrink-0 leading-tight tracking-tight">
                              {activeFace.title}
                            </p>
                            <div className="mt-2 h-px w-10 bg-black/20 shrink-0" />
                            <CardBackBody
                              kind={activeFace.kind}
                              frag={frag}
                              source={source}
                            />
                          </div>
                        </motion.div>
                      </motion.button>
                    </div>
                  );
                })}
              </motion.div>
            )}
            </div>
            <p className="text-white/40 text-[11px] text-center mt-4 font-light">
              {dealtPile.length === 0
                ? "Hover to peek · click to deal onto the reading pile"
                : `${dealtPile.length} in pile · hover to stretch left to right · click to flip · Esc returns top`}
            </p>
          </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-8 mt-16">
          <section className="bg-panel rounded-[30px] px-8 py-7 min-h-[426px] flex flex-col">
            <div className="flex flex-wrap items-center gap-3 mb-7">
              <h3 className="text-[#FFFBFB] text-xl font-bold m-0">
                Congruence and Report
              </h3>
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-[12px] font-normal ${
                  congruence.accepted
                    ? "border-gold/60 text-gold"
                    : "border-white/25 text-white/55"
                }`}
              >
                {congruence.accepted ? "Approved" : "Needs review"}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
              <Metric
                label="Smell align"
                value={fragScore != null ? `${fragScore}/5` : "—"}
              />
              <Metric
                label="Music align"
                value={musicScore != null ? `${musicScore}/5` : "—"}
              />
              <Metric label="CLIP fragrance" value={formatClip(clipFrag)} />
              <Metric label="CLIP music" value={formatClip(clipMusic)} />
            </div>
            {(clipFrag == null && clipMusic == null) && (
              <p className="text-white/40 text-[12px] font-light -mt-5 mb-6">
                CLIP proxies unavailable for this run (image–text similarity was skipped or failed).
              </p>
            )}

            <div className="bb-scroll flex-1 min-h-0 overflow-y-auto space-y-5 pr-1">
              <div>
                <p className="text-gold text-[13px] font-normal mb-2">
                  Summary
                </p>
                <p className="text-[#FFF7F7] text-[15px] font-light leading-[25px]">
                  {congruence.summary ||
                    congruence.descriptor_consistency?.details ||
                    "No summary yet."}
                </p>
              </div>

              {rationale && (
                <div>
                  {/* Congruence rationale blocks */}
                  <p className="text-gold text-[13px] font-normal mb-2">
                    Rationale
                  </p>
                  <div className="space-y-4 text-[#FFF7F7] text-[14px] font-light leading-[24px]">
                    {splitRationale(rationale).map((block) => (
                      <div key={block.title || block.body.slice(0, 24)}>
                        {block.title && (
                          <p className="text-white/80 text-[13px] font-normal mb-1.5">
                            {block.title}
                          </p>
                        )}
                        <p className="text-white/70 font-light text-justify">
                          {block.body}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Refine chat panel */}
          <section
            className={`relative bg-panel rounded-[30px] px-5 sm:px-8 py-6 sm:py-7 min-h-[426px] flex flex-col overflow-hidden mx-auto w-full ${
              refineLocked ? "select-none" : ""
            }`}
            aria-disabled={refineLocked}
          >
            <h3 className="text-[#FFFBFB] text-xl font-bold mb-3 m-0">
              Refinement
            </h3>
            <p className="text-[#FFF7F7] text-[15px] font-light leading-[25px] mb-4">
              This is a chat space to refine some of the aspects that might not
              suit best with the current brand image.
            </p>
            <div
              className={`flex flex-1 flex-col ${
                refineLocked ? "pointer-events-none blur-[2px] opacity-45" : ""
              }`}
            >
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={5}
                maxLength={1200}
                disabled={refining || refineLocked}
                readOnly={refineLocked}
                placeholder="Describe a brand change (mood, energy, colours, texture, narrative)…"
                className="flex-1 bg-[#D9D9D9] rounded-[20px] text-black text-[15px] font-normal px-5 py-4 outline-none resize-none min-h-[149px] disabled:opacity-50"
              />
              <div className="flex justify-center mt-6">
                <GoldButton
                  onClick={submitRefine}
                  disabled={refineLocked || refining || !feedback.trim()}
                >
                  {refining ? "Refining…" : "Regenerate"}
                </GoldButton>
              </div>
            </div>
            {refineLocked ? (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-[30px] bg-black/55 px-8 text-center backdrop-blur-[3px]">
                <span
                  className="flex size-12 items-center justify-center rounded-full border border-gold/50 bg-black/40 text-gold"
                  aria-hidden="true"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M7 11V8a5 5 0 0 1 10 0v3"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                    <rect
                      x="5"
                      y="11"
                      width="14"
                      height="10"
                      rx="2.5"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    />
                  </svg>
                </span>
                <p className="text-nav text-base font-bold m-0">Refinement locked</p>
                <p className="text-nav/85 text-sm font-light leading-6 m-0 max-w-[280px]">
                  During rating of this mode, you are not allowed to refine.
                  Only participants rate the curated admin stimuli.
                </p>
              </div>
            ) : null}
            {clarify && (
              <p className="text-sm text-nav mt-3 opacity-80">{clarify}</p>
            )}
            {refineError && (
              <p className="text-sm mt-3 text-red-300">{refineError}</p>
            )}
          </section>
        </div>

        <div className="flex flex-col sm:flex-row flex-wrap gap-6 mt-10 items-center justify-center">
          <div className="flex flex-col items-center gap-2 w-full sm:w-auto">
            <GoldButton onClick={onSave} disabled={saving || refineLocked}>
              {saving ? "Saving…" : saved ? "Saved to Library" : "Save this Archive"}
            </GoldButton>
            <p className="text-white/45 text-[12px] font-light m-0 max-w-[279px] text-center">
              Generated result will be saved to library.
            </p>
            {saveError ? (
              <p className="text-red-300 text-sm m-0 max-w-[279px] text-center">{saveError}</p>
            ) : null}
          </div>
          {isAdmin && !refineLocked ? (
            <GoldButton
              onClick={() => void onShareStudy()}
              disabled={sharing || sharedStudy}
            >
              {sharing
                ? "Sharing…"
                : sharedStudy
                  ? "In shared library"
                  : "Add to shared study"}
            </GoldButton>
          ) : null}
          {shareError ? (
            <p className="text-red-300 text-sm self-center max-w-md text-center">{shareError}</p>
          ) : null}
          <div className="flex flex-col items-center gap-2 w-full sm:w-auto">
            <GoldButton
              onClick={() => void downloadReport()}
              disabled={downloading}
            >
              {downloading ? "Preparing…" : "Download ZIP"}
            </GoldButton>
            <p className="text-white/45 text-[12px] font-light m-0 max-w-[279px] text-center">
              Zip consisting of the generated outputs.
            </p>
            {downloadError ? (
              <p className="text-red-300 text-sm m-0 max-w-[279px] text-center">
                {downloadError}
              </p>
            ) : null}
          </div>
        </div>
      </PipelineShell>
      {/* Floating rating card for shared study stimuli */}
      <EvaluationCard executionId={result.execution_id} />
    </main>
  </RequireAuth>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-white/55 text-[13px] font-light mb-1">{label}</p>
      <p className="text-white text-2xl font-bold leading-none">{value}</p>
    </div>
  );
}

function HoverReveal({
  label,
  value,
  delay,
}: {
  label: string;
  value: string;
  delay: number;
}) {
  return (
    <motion.div
      className="relative group/reveal min-w-0"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
    >
      <span className="block font-light truncate text-black/80 cursor-help border-b border-dotted border-black/20 group-hover/reveal:border-gold group-hover/reveal:text-[#6B4E12] transition-colors duration-200">
        {value}
      </span>
      <div
        role="tooltip"
        className="pointer-events-none absolute left-0 bottom-[calc(100%+8px)] z-50 w-max max-w-[260px] opacity-0 translate-y-1 group-hover/reveal:opacity-100 group-hover/reveal:translate-y-0 transition-all duration-200"
      >
        <div className="rounded-[14px] bg-maroon text-lemon px-3.5 py-2.5 shadow-[0_10px_24px_rgba(0,0,0,0.35)] border border-gold/40">
          <p className="text-[10px] font-normal text-gold mb-1">{label}</p>
          <p className="text-[12px] font-light leading-snug">{value}</p>
        </div>
      </div>
    </motion.div>
  );
}

function CardSources({ source }: { source: string }) {
  return (
    <p className="text-[10px] font-light mt-2 pt-2 border-t border-black/10 truncate shrink-0 text-black/40">
      Sources: {source || "—"}
    </p>
  );
}

function CardBackBody({
  kind,
  frag,
  source,
}: {
  kind: CardKind;
  frag: FragranceConcept;
  source: string;
}) {
  if (kind === "top" || kind === "heart" || kind === "base") {
    const rows = notesForCard(frag, kind);
    return (
      <>
        <div className="bb-scroll mt-3 space-y-0 overflow-y-auto min-h-0 flex-1 pr-1 font-light">
          {rows.map((row, i) => (
            <div
              key={row.chemical_name || row.ingredient}
              className={`py-2.5 ${i !== 0 ? "border-t border-black/10" : ""}`}
            >
              <p className="text-[13px] lg:text-[14px] font-light leading-snug text-black/90 capitalize">
                {row.chemical_name || row.ingredient}
              </p>
              {row.ingredient &&
                row.ingredient !== row.chemical_name && (
                  <p className="text-[10px] font-light text-black/40 mt-0.5">
                    {row.ingredient}
                  </p>
                )}
              <p className="text-[11px] font-light mt-1.5 leading-snug">
                <span className="text-black/35">Smells like</span>{" "}
                <span className="italic text-[#6B3A2A]">{row.smells_like}</span>
              </p>
            </div>
          ))}
          {rows.length === 0 && (
            <p className="text-sm font-light text-black/40 py-2">No notes yet.</p>
          )}
        </div>
        <CardSources source={source} />
      </>
    );
  }

  if (kind === "signature") {
    return (
      <div className="bb-scroll mt-3 overflow-y-auto min-h-0 flex-1 pr-1 flex flex-col font-light">
        <p className="text-[13px] lg:text-[14px] font-light leading-[1.55] text-black/75">
          {frag.smell_signature || "No smell signature yet."}
        </p>
        <div className="mt-auto">
          <CardSources source={source} />
        </div>
      </div>
    );
  }

  if (kind === "accords") {
    const items = frag.dominant_accords || [];
    return (
      <div className="bb-scroll mt-4 overflow-y-auto min-h-0 flex-1 pr-1 font-light">
        <ul className="flex flex-col gap-2.5">
          {items.map((item) => (
            <li
              key={item}
              className="text-[14px] lg:text-[15px] font-light capitalize leading-snug pl-3 border-l-2 border-[#8B3A3A]/50 text-black/80"
            >
              {item}
            </li>
          ))}
          {items.length === 0 && (
            <p className="text-sm font-light text-black/40">No accords yet.</p>
          )}
        </ul>
      </div>
    );
  }

  if (kind === "intensity") {
    return (
      <div className="mt-4 flex-1 flex flex-col items-center justify-center text-center px-2 font-light">
        <p className="text-[11px] font-light text-black/35 mb-3">Strength</p>
        <p className="text-[30px] lg:text-[34px] font-light capitalize leading-none text-[#6B3A2A]">
          {frag.intensity_profile || "—"}
        </p>
      </div>
    );
  }

  const emotions = frag.emotional_descriptors || [];
  return (
    <div className="bb-scroll mt-4 overflow-y-auto min-h-0 flex-1 pr-1 font-light">
      <ul className="flex flex-col gap-2.5">
        {emotions.map((item) => (
          <li
            key={item}
            className="text-[15px] lg:text-[16px] font-light capitalize leading-snug pl-3 border-l-2 border-[#C9A05A]/70 text-black/80"
          >
            {item}
          </li>
        ))}
        {emotions.length === 0 && (
          <p className="text-sm font-light text-black/40">No descriptors yet.</p>
        )}
      </ul>
    </div>
  );
}

