"use client";

/**
 * Study rating card.
 * Likert questions experience prompts and submit to library ratings.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  EXPERIENCE_QUESTIONS,
  LIKERT_QUESTIONS,
  emptyExperience,
  emptyRatings,
  experienceComplete,
  loadExperience,
  loadResponse,
  ratingsComplete,
  saveExperience,
  saveResponse,
  type ExperienceAnswers,
  type LikertAnswers,
} from "@/lib/evaluation";
import {
  findNextUnratedShared,
  findSharedStimulus,
  setRatingSession,
  type SharedStimulus,
} from "@/lib/rating";

type Step = "experience" | "ratings";

const POS_KEY = "bb_rating_card_pos";

type CardPos = { x: number; y: number };

function readPos(): CardPos | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(POS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CardPos>;
    if (typeof parsed.x === "number" && typeof parsed.y === "number") {
      return { x: parsed.x, y: parsed.y };
    }
  } catch {
    /* ignore */
  }
  return null;
}

function writePos(pos: CardPos) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(POS_KEY, JSON.stringify(pos));
}

function defaultPos(): CardPos {
  if (typeof window === "undefined") return { x: 16, y: 96 };
  const width = Math.min(window.innerWidth - 32, 380);
  return {
    x: Math.max(16, window.innerWidth - width - 16),
    y: 96,
  };
}

function clampPos(pos: CardPos, el: HTMLElement | null): CardPos {
  if (typeof window === "undefined") return pos;
  const w = el?.offsetWidth ?? Math.min(window.innerWidth - 32, 380);
  const h = el?.offsetHeight ?? 200;
  const maxX = Math.max(8, window.innerWidth - w - 8);
  const maxY = Math.max(8, window.innerHeight - Math.min(h, window.innerHeight - 16) - 8);
  return {
    x: Math.min(Math.max(8, pos.x), maxX),
    y: Math.min(Math.max(8, pos.y), maxY),
  };
}

export default function EvaluationCard({
  executionId,
}: {
  executionId: string;
}) {
  const { user } = useAuth();

  // Card open state and rating wizard step
  const [open, setOpen] = useState(true);
  const [step, setStep] = useState<Step>("experience");
  const [stimulus, setStimulus] = useState<SharedStimulus | null>(null);
  const [experience, setExperience] = useState<ExperienceAnswers>(emptyExperience);
  const [ratings, setRatings] = useState<LikertAnswers>(emptyRatings);
  const [comments, setComments] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [goingNext, setGoingNext] = useState(false);
  const [experienceLocked, setExperienceLocked] = useState(false);

  // Draggable card position
  const [pos, setPos] = useState<CardPos>(() => readPos() ?? defaultPos());
  const cardRef = useRef<HTMLElement | null>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
  } | null>(null);

  // Load shared stimulus and any existing answers for this execution
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDone(false);
    setHasNext(false);

    (async () => {
      const item = await findSharedStimulus(executionId);
      if (cancelled) return;
      if (!item) {
        setStimulus(null);
        setLoading(false);
        return;
      }

      const userId = user?.id;
      const [background, existing] = await Promise.all([
        userId ? loadExperience(userId) : Promise.resolve(emptyExperience()),
        userId ? loadResponse(userId, item.entryId) : Promise.resolve(null),
      ]);
      if (cancelled) return;

      setStimulus(item);
      // Background Yes/No is once per account (profile). Likert clears each picture.
      setExperience(background);
      setRatings(emptyRatings());
      setComments("");
      const alreadyAsked = experienceComplete(background);
      setExperienceLocked(alreadyAsked);
      setStep(alreadyAsked ? "ratings" : "experience");
      setOpen(true);
      setGoingNext(false);

      if (existing) {
        setDone(true);
        if (userId) {
          const next = await findNextUnratedShared(item.entryId, userId);
          if (!cancelled) setHasNext(Boolean(next));
        }
      } else {
        setDone(false);
      }
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [executionId, user?.id]);

  // Keep the card on screen when the window resizes
  useEffect(() => {
    const onResize = () => {
      setPos((prev) => clampPos(prev, cardRef.current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Pointer drag handlers for moving the floating card
  const onDragPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest("button, a, input, textarea, select, label")) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      dragRef.current = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        origX: pos.x,
        origY: pos.y,
      };
    },
    [pos.x, pos.y]
  );

  const onDragPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== e.pointerId) return;
      const next = clampPos(
        {
          x: drag.origX + (e.clientX - drag.startX),
          y: drag.origY + (e.clientY - drag.startY),
        },
        cardRef.current
      );
      setPos(next);
    },
    []
  );

  const onDragPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== e.pointerId) return;
      dragRef.current = null;
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* already released */
      }
      setPos((prev) => {
        const clamped = clampPos(prev, cardRef.current);
        writePos(clamped);
        return clamped;
      });
    },
    []
  );

  const canContinue = experienceComplete(experience);
  const canSubmit = ratingsComplete(ratings);

  const onContinue = async () => {
    if (!canContinue || saving || done) return;
    setSaving(true);
    setError(null);
    try {
      if (user?.id) await saveExperience(user.id, experience);
      setStep("ratings");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save experience");
    } finally {
      setSaving(false);
    }
  };

  const onSubmit = async () => {
    if (!canSubmit || saving || done) return;
    setSaving(true);
    setError(null);
    try {
      if (user?.id) await saveExperience(user.id, experience);
      if (!user?.id || !stimulus) {
        throw new Error("Sign in to submit your rating.");
      }
      await saveResponse({
        userId: user.id,
        stimulus,
        ratings,
        comments,
      });
      setDone(true);
      const next = await findNextUnratedShared(stimulus.entryId, user.id);
      setHasNext(Boolean(next));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit rating");
    } finally {
      setSaving(false);
    }
  };

  const goNext = async () => {
    if (!user?.id || !stimulus || goingNext) return;
    setGoingNext(true);
    setError(null);
    try {
      const next = await findNextUnratedShared(stimulus.entryId, user.id);
      if (!next) {
        setHasNext(false);
        return;
      }
      sessionStorage.setItem("bb_result", JSON.stringify(next.result));
      if (next.imageUrl) sessionStorage.setItem("bb_image_b64", next.imageUrl);
      else sessionStorage.removeItem("bb_image_b64");
      setRatingSession(true);
      window.location.assign("/results");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open the next picture");
      setGoingNext(false);
    }
  };

  if (!loading && !stimulus) return null;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed right-0 top-1/3 z-40 rounded-l-[18px] bg-nav px-3 py-5 text-black shadow-[0_12px_28px_rgba(0,0,0,0.35)] cursor-pointer hover:bg-lemon"
        aria-expanded="false"
      >
        <span className="flex flex-col items-center gap-2">
          <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-maroon/70">
            Rate
          </span>
          <span
            className="text-sm font-bold"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          >
            {done ? "Thank you" : "Rate this result"}
          </span>
        </span>
      </button>
    );
  }

  const shellStyle = {
    left: pos.x,
    top: pos.y,
    right: "auto" as const,
    bottom: "auto" as const,
  };

  const dragHandlers = {
    onPointerDown: onDragPointerDown,
    onPointerMove: onDragPointerMove,
    onPointerUp: onDragPointerUp,
    onPointerCancel: onDragPointerUp,
  };

  if (done) {
    return (
      <aside
        ref={cardRef}
        style={shellStyle}
        className="fixed z-40 w-[min(100%-2rem,380px)] flex flex-col rounded-[28px] bg-nav text-black shadow-[0_24px_60px_rgba(0,0,0,0.4)] px-6 py-7"
        aria-labelledby="evaluation-thanks-title"
      >
        <DragHeader
          {...dragHandlers}
          onHide={() => setOpen(false)}
        >
          <h2
            id="evaluation-thanks-title"
            className="text-[22px] font-bold leading-tight mt-3 mb-0"
          >
            Thank you for rating!
          </h2>
        </DragHeader>
        <p className="text-[14px] font-light leading-6 opacity-80 mt-3 mb-0">
          {hasNext
            ? "Please proceed to the next picture."
            : "You have finished every picture in the shared library."}
        </p>
        {error ? (
          <p className="text-sm font-light text-maroon mt-3 mb-0" role="alert">
            {error}
          </p>
        ) : null}
        {hasNext ? (
          <button
            type="button"
            onClick={() => void goNext()}
            disabled={goingNext}
            className="mt-6 rounded-full bg-gold-soft px-5 py-2.5 text-sm font-bold text-white disabled:opacity-40 cursor-pointer hover:opacity-90"
          >
            {goingNext ? "Opening…" : "Next picture"}
          </button>
        ) : null}
      </aside>
    );
  }

  return (
    <aside
      ref={cardRef}
      style={shellStyle}
      className="fixed z-40 w-[min(100%-2rem,380px)] max-h-[calc(100vh-2rem)] flex flex-col rounded-[28px] bg-nav text-black shadow-[0_24px_60px_rgba(0,0,0,0.4)]"
      aria-labelledby="evaluation-card-title"
    >
      <div className="px-6 pt-6 pb-3 shrink-0">
        <DragHeader
          {...dragHandlers}
          onHide={() => setOpen(false)}
        >
          <h2
            id="evaluation-card-title"
            className="text-[22px] font-bold leading-tight mt-1 mb-0"
          >
            {step === "experience" ? "Before you rate" : "Rate this concept"}
          </h2>
        </DragHeader>
        <p className="text-[13px] font-light leading-5 opacity-75 mt-2 mb-0">
          {step === "experience"
            ? "Answer once for your account. Then rate each picture."
            : "1 = strongly disagree · 5 = strongly agree. You can submit once."}
        </p>
      </div>

      <div className="bb-scroll flex-1 min-h-0 overflow-y-auto px-6 pb-4">
        {loading ? (
          <p className="text-sm font-light opacity-70">Loading questions…</p>
        ) : step === "experience" ? (
          <ol className="flex flex-col gap-5 m-0 p-0 list-none">
            {EXPERIENCE_QUESTIONS.map((q) => (
              <li key={q.key}>
                <p className="text-[14px] font-bold leading-snug m-0">{q.label}</p>
                <YesNo
                  value={experience[q.key]}
                  onChange={(value) =>
                    setExperience((prev) => ({ ...prev, [q.key]: value }))
                  }
                />
              </li>
            ))}
          </ol>
        ) : (
          <ol className="flex flex-col gap-5 m-0 p-0 list-none">
            {LIKERT_QUESTIONS.map((q, i) => (
              <li key={q.key}>
                <p className="text-[11px] font-bold tracking-wide uppercase text-maroon/60 m-0">
                  {i + 1}. {q.title}
                </p>
                <p className="text-[13px] font-light leading-snug mt-1 mb-2">
                  {q.prompt}
                </p>
                <LikertRow
                  value={ratings[q.key]}
                  onChange={(value) =>
                    setRatings((prev) => ({ ...prev, [q.key]: value }))
                  }
                />
              </li>
            ))}
            <li>
              <label className="text-[13px] font-bold" htmlFor="eval-comments">
                Comments{" "}
                <span className="font-light opacity-60">(optional)</span>
              </label>
              <textarea
                id="eval-comments"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                rows={3}
                placeholder="Anything that felt especially fitting or off?"
                className="mt-2 w-full resize-none rounded-2xl bg-white/70 px-3 py-2.5 text-sm font-light outline-none"
              />
            </li>
          </ol>
        )}

        {error ? (
          <p className="text-sm font-light text-maroon mt-3 mb-0" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <div className="px-6 py-5 shrink-0 border-t border-black/10 flex items-center justify-between gap-3">
        {step === "ratings" && !experienceLocked ? (
          <button
            type="button"
            onClick={() => setStep("experience")}
            className="text-sm font-light opacity-70 hover:opacity-100 cursor-pointer"
          >
            Back
          </button>
        ) : (
          <span />
        )}
        {step === "experience" ? (
          <button
            type="button"
            onClick={() => void onContinue()}
            disabled={!canContinue || saving || loading}
            className="rounded-full bg-gold-soft px-5 py-2.5 text-sm font-bold text-white disabled:opacity-40 cursor-pointer hover:opacity-90"
          >
            {saving ? "Saving…" : "Continue"}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void onSubmit()}
            disabled={!canSubmit || saving || loading}
            className="rounded-full bg-gold-soft px-5 py-2.5 text-sm font-bold text-white disabled:opacity-40 cursor-pointer hover:opacity-90"
          >
            {saving ? "Saving…" : "Submit rating"}
          </button>
        )}
      </div>
    </aside>
  );
}

function DragHeader({
  children,
  onHide,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
}: {
  children: ReactNode;
  onHide: () => void;
  onPointerDown: (e: ReactPointerEvent<HTMLElement>) => void;
  onPointerMove: (e: ReactPointerEvent<HTMLElement>) => void;
  onPointerUp: (e: ReactPointerEvent<HTMLElement>) => void;
  onPointerCancel: (e: ReactPointerEvent<HTMLElement>) => void;
}) {
  return (
    <div
      className="cursor-grab active:cursor-grabbing select-none touch-none"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      title="Drag to move"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-maroon/70 m-0">
            Rating
            <span className="ml-2 font-light normal-case tracking-normal opacity-50">
              drag to move
            </span>
          </p>
          {children}
        </div>
        <button
          type="button"
          onClick={onHide}
          className="text-sm font-light opacity-60 hover:opacity-100 cursor-pointer shrink-0"
          aria-label="Hide rating card"
        >
          Hide
        </button>
      </div>
    </div>
  );
}

function YesNo({
  value,
  onChange,
}: {
  value: boolean | null;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="mt-2 flex gap-2">
      {[
        { label: "Yes", val: true },
        { label: "No", val: false },
      ].map((opt) => {
        const selected = value === opt.val;
        return (
          <button
            key={opt.label}
            type="button"
            onClick={() => onChange(opt.val)}
            className={`flex-1 rounded-full py-2 text-sm font-bold cursor-pointer ${
              selected
                ? "bg-maroon text-lemon"
                : "bg-white/70 text-black/70 hover:bg-white"
            }`}
            aria-pressed={selected}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function LikertRow({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-1">
      <span className="text-[10px] font-light opacity-50 w-8">Low</span>
      {[1, 2, 3, 4, 5].map((n) => {
        const selected = value === n;
        return (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            aria-label={`${n} of 5`}
            className={`size-9 rounded-full text-sm font-bold cursor-pointer ${
              selected
                ? "bg-gold text-maroon"
                : "bg-white/70 text-black/70 hover:bg-white"
            }`}
            aria-pressed={selected}
          >
            {n}
          </button>
        );
      })}
      <span className="text-[10px] font-light opacity-50 w-8 text-right">High</span>
    </div>
  );
}
