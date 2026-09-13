/**
 * Study export helpers.
 * Load shared ratings / automated scores and build labeled CSV downloads.
 */

import { createClient } from "@/lib/supabase/client";
import { LIKERT_QUESTIONS, type LikertKey } from "@/lib/evaluation";
import {
  pipelineProcessLabel,
  type ApiResult,
  type CongruenceReport,
} from "@/lib/types";

export type RatingRow = {
  participantId: string;
  entryId: string;
  executionId: string;
  title: string;
  process: string;
  mode: string;
  submittedAt: string;
  comments: string;
  ratings: Record<LikertKey, number>;
  experiencePerfumery: boolean | null;
  experienceMusic: boolean | null;
  experienceDesign: boolean | null;
  consentedAt: string | null;
};

export type StudyExportSummary = {
  sharedTotal: number;
  badCount: number;
  promptCount: number;
  ratingCount: number;
  participantCount: number;
  rows: RatingRow[];
};

export type AutomatedScoreRow = {
  entryId: string;
  executionId: string;
  title: string;
  process: string;
  mode: string;
  savedAt: string;
  fragranceScore: number | null;
  musicScore: number | null;
  fragranceAligns: boolean | null;
  musicAligns: boolean | null;
  congruenceAccepted: boolean | null;
  regenCount: number | null;
  clipImageFragrance: number | null;
  clipImageMusic: number | null;
  summary: string;
  fragranceIssues: string;
  musicIssues: string;
};

export type AutomatedScoreExportSummary = {
  sharedTotal: number;
  badCount: number;
  promptCount: number;
  scoredCount: number;
  missingReportCount: number;
  rows: AutomatedScoreRow[];
};

function processOf(mode: string | null | undefined, executionId: string): string {
  const fromMode = pipelineProcessLabel(mode);
  if (fromMode === "BAD" || fromMode === "Prompt Only") return fromMode;
  if (/\(BAD\)\s*$/i.test(executionId)) return "BAD";
  if (/\(Prompt Only\)\s*$/i.test(executionId)) return "Prompt Only";
  return fromMode || "";
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function joinIssues(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    .join("; ");
}

function congruenceFromOutput(output: unknown): CongruenceReport | null {
  if (!output || typeof output !== "object") return null;
  const report = (output as ApiResult).congruence_report;
  if (!report || typeof report !== "object") return null;
  return report;
}

/** Admin export: all ratings on shared study stimuli from Supabase. */
export async function loadStudyRatingExport(): Promise<StudyExportSummary> {
  const supabase = createClient();
  if (!supabase) {
    return {
      sharedTotal: 0,
      badCount: 0,
      promptCount: 0,
      ratingCount: 0,
      participantCount: 0,
      rows: [],
    };
  }

  const { data: shared, error: sharedError } = await supabase
    .from("library_entries")
    .select("id, execution_id, title, mode, saved_at")
    .eq("is_shared", true)
    .order("saved_at", { ascending: true });

  if (sharedError) throw new Error(sharedError.message);

  const stimuli = shared ?? [];
  const badCount = stimuli.filter(
    (e) => processOf(e.mode as string | null, e.execution_id as string) === "BAD"
  ).length;
  const promptCount = stimuli.filter(
    (e) =>
      processOf(e.mode as string | null, e.execution_id as string) ===
      "Prompt Only"
  ).length;

  if (stimuli.length === 0) {
    return {
      sharedTotal: 0,
      badCount: 0,
      promptCount: 0,
      ratingCount: 0,
      participantCount: 0,
      rows: [],
    };
  }

  const entryIds = stimuli.map((e) => e.id as string);
  const entryById = new Map(stimuli.map((e) => [e.id as string, e]));
  const orderIndex = new Map(entryIds.map((id, i) => [id, i]));

  const { data: responses, error: ratingsError } = await supabase
    .from("library_ratings")
    .select(
      "participant_id, library_entry_id, submitted_at, comments, descriptor_accuracy, brand_coherence, fragrance_alignment, music_alignment, cross_modal_congruence, creativity, ideation_usefulness, overall_quality"
    )
    .in("library_entry_id", entryIds)
    .order("submitted_at", { ascending: true });

  if (ratingsError) throw new Error(ratingsError.message);
  if (!responses?.length) {
    return {
      sharedTotal: stimuli.length,
      badCount,
      promptCount,
      ratingCount: 0,
      participantCount: 0,
      rows: [],
    };
  }

  const participantIds = [
    ...new Set(responses.map((r) => r.participant_id as string)),
  ];
  const { data: profiles, error: profileError } = await supabase
    .from("profiles")
    .select(
      "id, experience_perfumery, experience_music, experience_design, consented_at"
    )
    .in("id", participantIds);

  if (profileError) throw new Error(profileError.message);

  const profileById = new Map(
    (profiles ?? []).map((p) => [p.id as string, p])
  );

  const rows: RatingRow[] = responses.map((row) => {
    const entry = entryById.get(row.library_entry_id as string);
    const profile = profileById.get(row.participant_id as string);
    const executionId = (entry?.execution_id as string) || "";
    const mode = (entry?.mode as string | null) || "";
    const process = processOf(mode, executionId);
    return {
      participantId: row.participant_id as string,
      entryId: row.library_entry_id as string,
      executionId,
      title: (entry?.title as string) || "",
      process,
      mode,
      submittedAt: row.submitted_at as string,
      comments: (row.comments as string | null) || "",
      ratings: {
        descriptor_accuracy: row.descriptor_accuracy as number,
        brand_coherence: row.brand_coherence as number,
        fragrance_alignment: row.fragrance_alignment as number,
        music_alignment: row.music_alignment as number,
        cross_modal_congruence: row.cross_modal_congruence as number,
        creativity: row.creativity as number,
        ideation_usefulness: row.ideation_usefulness as number,
        overall_quality: row.overall_quality as number,
      },
      experiencePerfumery:
        typeof profile?.experience_perfumery === "boolean"
          ? profile.experience_perfumery
          : null,
      experienceMusic:
        typeof profile?.experience_music === "boolean"
          ? profile.experience_music
          : null,
      experienceDesign:
        typeof profile?.experience_design === "boolean"
          ? profile.experience_design
          : null,
      consentedAt:
        typeof profile?.consented_at === "string" ? profile.consented_at : null,
    };
  });

  rows.sort((a, b) => {
    const oi = (orderIndex.get(a.entryId) ?? 0) - (orderIndex.get(b.entryId) ?? 0);
    if (oi !== 0) return oi;
    const proc = a.process.localeCompare(b.process);
    if (proc !== 0) return proc;
    return a.submittedAt.localeCompare(b.submittedAt);
  });

  return {
    sharedTotal: stimuli.length,
    badCount,
    promptCount,
    ratingCount: rows.length,
    participantCount: participantIds.length,
    rows,
  };
}

/** Admin export: DeepSeek judge + CLIP scores from shared library generated_output. */
export async function loadAutomatedScoreExport(): Promise<AutomatedScoreExportSummary> {
  const supabase = createClient();
  if (!supabase) {
    return {
      sharedTotal: 0,
      badCount: 0,
      promptCount: 0,
      scoredCount: 0,
      missingReportCount: 0,
      rows: [],
    };
  }

  const { data: shared, error: sharedError } = await supabase
    .from("library_entries")
    .select("id, execution_id, title, mode, saved_at, generated_output")
    .eq("is_shared", true)
    .order("saved_at", { ascending: true });

  if (sharedError) throw new Error(sharedError.message);

  const stimuli = shared ?? [];
  const badCount = stimuli.filter(
    (e) => processOf(e.mode as string | null, e.execution_id as string) === "BAD"
  ).length;
  const promptCount = stimuli.filter(
    (e) =>
      processOf(e.mode as string | null, e.execution_id as string) ===
      "Prompt Only"
  ).length;

  const rows: AutomatedScoreRow[] = [];
  let missingReportCount = 0;

  for (const entry of stimuli) {
    const executionId = (entry.execution_id as string) || "";
    const mode = (entry.mode as string | null) || "";
    const process = processOf(mode, executionId);
    const report = congruenceFromOutput(entry.generated_output);
    if (!report) {
      missingReportCount += 1;
      continue;
    }
    const consistency = report.descriptor_consistency || {};
    const proxies = report.automated_proxies || {};
    rows.push({
      entryId: entry.id as string,
      executionId,
      title: (entry.title as string) || "",
      process,
      mode,
      savedAt: (entry.saved_at as string) || "",
      fragranceScore: asNumber(consistency.fragrance_score),
      musicScore: asNumber(consistency.music_score),
      fragranceAligns: asBoolean(consistency.fragrance_aligns_descriptor),
      musicAligns: asBoolean(consistency.music_aligns_descriptor),
      congruenceAccepted: asBoolean(report.accepted),
      regenCount: asNumber(report.regen_count),
      clipImageFragrance: asNumber(proxies.clip_score_image_fragrance_text),
      clipImageMusic: asNumber(proxies.clip_score_image_music_text),
      summary: typeof report.summary === "string" ? report.summary : "",
      fragranceIssues: joinIssues(consistency.fragrance_issues),
      musicIssues: joinIssues(consistency.music_issues),
    });
  }

  return {
    sharedTotal: stimuli.length,
    badCount,
    promptCount,
    scoredCount: rows.length,
    missingReportCount,
    rows,
  };
}

function csvCell(value: string | number | boolean | null): string {
  const text =
    value == null
      ? ""
      : typeof value === "boolean"
        ? value
          ? "yes"
          : "no"
        : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

/** One row per submitted rating; headers match the rating card titles. */
export function libraryRatingsToLabeledCsv(rows: RatingRow[]): string {
  const headers = [
    "Participant ID",
    "Submitted at",
    "Process (BAD / Prompt Only)",
    "Execution ID",
    "Picture title",
    ...LIKERT_QUESTIONS.map((q) => `${q.title} (1-5)`),
    "Comments",
    "Experience: perfumery",
    "Experience: music",
    "Experience: design",
    "Consented at",
  ];
  const lines = [
    headers.join(","),
    ...rows.map((row) =>
      [
        csvCell(row.participantId),
        csvCell(row.submittedAt),
        csvCell(row.process),
        csvCell(row.executionId),
        csvCell(row.title),
        ...LIKERT_QUESTIONS.map((q) => csvCell(row.ratings[q.key])),
        csvCell(row.comments),
        csvCell(row.experiencePerfumery),
        csvCell(row.experienceMusic),
        csvCell(row.experienceDesign),
        csvCell(row.consentedAt),
      ].join(",")
    ),
  ];
  return `${lines.join("\n")}\n`;
}

/** One row per shared library entry with DeepSeek judge + CLIP proxies. */
export function automatedScoresToCsv(rows: AutomatedScoreRow[]): string {
  const headers = [
    "Process (BAD / Prompt Only)",
    "Execution ID",
    "Picture title",
    "Saved at",
    "DeepSeek fragrance score (1-5)",
    "DeepSeek music score (1-5)",
    "Fragrance aligns descriptor",
    "Music aligns descriptor",
    "Congruence accepted",
    "Regen count",
    "CLIP image-fragrance",
    "CLIP image-music",
    "Judge summary",
    "Fragrance issues",
    "Music issues",
  ];
  const lines = [
    headers.join(","),
    ...rows.map((row) =>
      [
        csvCell(row.process),
        csvCell(row.executionId),
        csvCell(row.title),
        csvCell(row.savedAt),
        csvCell(row.fragranceScore),
        csvCell(row.musicScore),
        csvCell(row.fragranceAligns),
        csvCell(row.musicAligns),
        csvCell(row.congruenceAccepted),
        csvCell(row.regenCount),
        csvCell(row.clipImageFragrance),
        csvCell(row.clipImageMusic),
        csvCell(row.summary),
        csvCell(row.fragranceIssues),
        csvCell(row.musicIssues),
      ].join(",")
    ),
  ];
  return `${lines.join("\n")}\n`;
}

export function downloadTextFile(filename: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
