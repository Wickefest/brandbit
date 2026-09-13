/**
 * Rating and experience helpers.
 * Likert keys experience answers and rating submit helpers.
 */

import { createClient } from "@/lib/supabase/client";
import type { SharedStimulus } from "./rating";

export type ExperienceKey = "perfumery" | "music" | "design";
export type LikertKey =
  | "descriptor_accuracy"
  | "brand_coherence"
  | "fragrance_alignment"
  | "music_alignment"
  | "cross_modal_congruence"
  | "creativity"
  | "ideation_usefulness"
  | "overall_quality";

export type ExperienceAnswers = Record<ExperienceKey, boolean | null>;
export type LikertAnswers = Record<LikertKey, number | null>;

const EXPERIENCE_STORAGE = "bb_eval_experience";

export const EXPERIENCE_QUESTIONS: {
  key: ExperienceKey;
  label: string;
}[] = [
  { key: "perfumery", label: "Do you have prior experience in perfumery?" },
  {
    key: "music",
    label: "Do you have prior experience in music (performance, production, or study)?",
  },
  {
    key: "design",
    label: "Do you have prior experience in creative design?",
  },
];

export const LIKERT_QUESTIONS: { key: LikertKey; title: string; prompt: string }[] = [
  {
    key: "descriptor_accuracy",
    title: "Descriptor accuracy",
    prompt:
      "How accurately does the Brand Aesthetic Descriptor reflect the source image?",
  },
  {
    key: "brand_coherence",
    title: "Brand coherence",
    prompt: "How coherent is the resulting overall brand identity?",
  },
  {
    key: "fragrance_alignment",
    title: "Fragrance alignment",
    prompt:
      "How well does the fragrance concept align with the visual brand identity and BAD?",
  },
  {
    key: "music_alignment",
    title: "Music alignment",
    prompt:
      "How well does the music direction and generated audio align with the visual brand identity and BAD?",
  },
  {
    key: "cross_modal_congruence",
    title: "Cross-modal congruence",
    prompt:
      "How well do the visual, fragrance, and music concepts feel like parts of the same brand?",
  },
  {
    key: "creativity",
    title: "Creativity",
    prompt: "How original and interesting is the generated multisensory concept?",
  },
  {
    key: "ideation_usefulness",
    title: "Ideation usefulness",
    prompt:
      "How useful would this output be for accelerating or supporting early-stage brand ideation?",
  },
  {
    key: "overall_quality",
    title: "Overall quality",
    prompt: "Overall judgement of the generated multisensory brand concept.",
  },
];

export const emptyExperience = (): ExperienceAnswers => ({
  perfumery: null,
  music: null,
  design: null,
});

export const emptyRatings = (): LikertAnswers => ({
  descriptor_accuracy: null,
  brand_coherence: null,
  fragrance_alignment: null,
  music_alignment: null,
  cross_modal_congruence: null,
  creativity: null,
  ideation_usefulness: null,
  overall_quality: null,
});

export function experienceComplete(answers: ExperienceAnswers): boolean {
  return EXPERIENCE_QUESTIONS.every((q) => typeof answers[q.key] === "boolean");
}

export function ratingsComplete(answers: LikertAnswers): boolean {
  return LIKERT_QUESTIONS.every((q) => {
    const n = answers[q.key];
    return typeof n === "number" && n >= 1 && n <= 5;
  });
}

function readLocalExperience(): ExperienceAnswers | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(EXPERIENCE_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ExperienceAnswers>;
    return {
      perfumery: typeof parsed.perfumery === "boolean" ? parsed.perfumery : null,
      music: typeof parsed.music === "boolean" ? parsed.music : null,
      design: typeof parsed.design === "boolean" ? parsed.design : null,
    };
  } catch {
    return null;
  }
}

function writeLocalExperience(answers: ExperienceAnswers) {
  if (typeof window === "undefined") return;
  localStorage.setItem(EXPERIENCE_STORAGE, JSON.stringify(answers));
}

export async function loadExperience(userId: string): Promise<ExperienceAnswers> {
  const empty = emptyExperience();
  const supabase = createClient();
  if (!supabase) return empty;

  const { data, error } = await supabase
    .from("profiles")
    .select("experience_perfumery, experience_music, experience_design")
    .eq("id", userId)
    .maybeSingle();

  if (error || !data) return empty;
  return {
    perfumery:
      typeof data.experience_perfumery === "boolean"
        ? data.experience_perfumery
        : null,
    music:
      typeof data.experience_music === "boolean" ? data.experience_music : null,
    design:
      typeof data.experience_design === "boolean" ? data.experience_design : null,
  };
}

export async function saveExperience(
  userId: string,
  answers: ExperienceAnswers
): Promise<void> {
  writeLocalExperience(answers);
  const supabase = createClient();
  if (!supabase) return;
  await supabase
    .from("profiles")
    .update({
      experience_perfumery: answers.perfumery,
      experience_music: answers.music,
      experience_design: answers.design,
    })
    .eq("id", userId);
}

type ResponseRow = {
  id: string;
  descriptor_accuracy: number;
  brand_coherence: number;
  fragrance_alignment: number;
  music_alignment: number;
  cross_modal_congruence: number;
  creativity: number;
  ideation_usefulness: number;
  overall_quality: number;
  comments: string | null;
};

export async function loadResponse(
  userId: string,
  entryId: string
): Promise<{ ratings: LikertAnswers; comments: string; responseId: string } | null> {
  const supabase = createClient();
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("library_ratings")
    .select(
      "id, descriptor_accuracy, brand_coherence, fragrance_alignment, music_alignment, cross_modal_congruence, creativity, ideation_usefulness, overall_quality, comments"
    )
    .eq("participant_id", userId)
    .eq("library_entry_id", entryId)
    .maybeSingle();

  if (error || !data) return null;
  const row = data as ResponseRow;
  return {
    responseId: row.id,
    comments: row.comments || "",
    ratings: {
      descriptor_accuracy: row.descriptor_accuracy,
      brand_coherence: row.brand_coherence,
      fragrance_alignment: row.fragrance_alignment,
      music_alignment: row.music_alignment,
      cross_modal_congruence: row.cross_modal_congruence,
      creativity: row.creativity,
      ideation_usefulness: row.ideation_usefulness,
      overall_quality: row.overall_quality,
    },
  };
}

export async function saveResponse(input: {
  userId: string;
  stimulus: SharedStimulus;
  ratings: LikertAnswers;
  comments: string;
}): Promise<string> {
  if (!ratingsComplete(input.ratings)) {
    throw new Error("Please answer every rating question.");
  }

  const supabase = createClient();
  if (!supabase) throw new Error("Supabase is not configured");

  const { data: existing } = await supabase
    .from("library_ratings")
    .select("id")
    .eq("participant_id", input.userId)
    .eq("library_entry_id", input.stimulus.entryId)
    .maybeSingle();
  if (existing?.id) {
    throw new Error("You have already rated this concept.");
  }

  const payload = {
    library_entry_id: input.stimulus.entryId,
    participant_id: input.userId,
    descriptor_accuracy: input.ratings.descriptor_accuracy,
    brand_coherence: input.ratings.brand_coherence,
    fragrance_alignment: input.ratings.fragrance_alignment,
    music_alignment: input.ratings.music_alignment,
    cross_modal_congruence: input.ratings.cross_modal_congruence,
    creativity: input.ratings.creativity,
    ideation_usefulness: input.ratings.ideation_usefulness,
    overall_quality: input.ratings.overall_quality,
    comments: input.comments.trim() || null,
    submitted_at: new Date().toISOString(),
  };

  const { data, error } = await supabase
    .from("library_ratings")
    .insert(payload)
    .select("id")
    .single();
  if (error) throw new Error(error.message);
  return data.id as string;
}

export const PERSONAL_LIBRARY_MAX = 5;
export const GENERATION_MAX = 5;

export async function getGenerationStatus(userId: string): Promise<{
  count: number;
  max: number;
  remaining: number;
}> {
  const supabase = createClient();
  if (!supabase) return { count: 0, max: GENERATION_MAX, remaining: GENERATION_MAX };
  const { data } = await supabase
    .from("profiles")
    .select("generation_count, role")
    .eq("id", userId)
    .maybeSingle();
  if (data?.role === "admin") {
    return { count: 0, max: Number.POSITIVE_INFINITY, remaining: Number.POSITIVE_INFINITY };
  }
  const count = typeof data?.generation_count === "number" ? data.generation_count : 0;
  return {
    count,
    max: GENERATION_MAX,
    remaining: Math.max(0, GENERATION_MAX - count),
  };
}

export async function recordGeneration(userId: string): Promise<void> {
  const supabase = createClient();
  if (!supabase) return;
  const { data } = await supabase
    .from("profiles")
    .select("generation_count, role")
    .eq("id", userId)
    .maybeSingle();
  if (!data || data.role === "admin") return;
  const next = (typeof data.generation_count === "number" ? data.generation_count : 0) + 1;
  await supabase.from("profiles").update({ generation_count: next }).eq("id", userId);
}
