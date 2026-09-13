/**
 * Shared frontend types.
 * API result shapes labels and identity helpers.
 */

export interface NoteGuideEntry {
  smells_like: string;
  chemical_name?: string;
  ingredient: string;
}

export interface FragranceConcept {
  top_notes: string[];
  heart_notes: string[];
  base_notes: string[];
  dominant_accords: string[];
  intensity_profile: string;
  emotional_descriptors: string[];
  smell_signature?: string;
  note_guide?: NoteGuideEntry[];
  pyrfume_sources?: string[];
}

export interface MusicDirection {
  tempo: string;
  bpm?: number;
  timbre: string[];
  instrumentation: string[];
  mood: string;
  style: string;
  music_signature?: string;
  audio_sample_ref: string | null;
}

export interface CongruenceReport {
  accepted?: boolean;
  regen_count?: number;
  summary?: string;
  automated_proxies?: {
    clip_score_image_fragrance_text?: number | null;
    clip_score_image_music_text?: number | null;
    imagebind_score_image_audio?: number | null;
  };
  descriptor_consistency?: {
    fragrance_aligns_descriptor?: boolean;
    music_aligns_descriptor?: boolean;
    fragrance_score?: number | null;
    music_score?: number | null;
    fragrance_issues?: string[];
    music_issues?: string[];
    details?: string;
  };
  attempts?: Array<{
    attempt: number;
    fragrance_aligns_descriptor: boolean;
    music_aligns_descriptor: boolean;
    regenerated?: string[];
  }>;
}

export interface BrandAestheticDescriptor {
  brand_item?: string;
  mood: string[];
  energy: string;
  color_temperature: string;
  colours?: string[];
  texture: string[];
  visual_style: string[];
  sensory_metaphors?: string[];
  narrative?: string;
}

export interface ApiResult {
  execution_id: string;
  brand_aesthetic_descriptor: BrandAestheticDescriptor;
  fragrance_concept: FragranceConcept;
  music_direction: MusicDirection;
  audio_sample_ref?: string | null;
  rationale: string;
  congruence_report: CongruenceReport;
  /** ``sensory_profile`` (BAD path) or ``prompt_only`` (parse → agents) */
  mode?: string;
  refinement_history?: unknown[];
}

/** Human label for pipeline mode stored on results / archive. */
export function pipelineProcessLabel(mode?: string | null): string {
  const raw = (mode || "").trim().toLowerCase();
  if (raw === "prompt" || raw === "prompt_only" || raw === "prompt-only") {
    return "Prompt Only";
  }
  if (raw === "bad" || raw === "sensory_profile" || raw === "descriptor") {
    return "BAD";
  }
  return "Unknown";
}

/** Library / evaluation name: `Indomie_001 (Prompt Only)` or `Indomie_001 (BAD)`. */
export function archiveDisplayName(result: {
  execution_id: string;
  mode?: string | null;
}): string {
  const id = (result.execution_id || "").trim();
  if (!id) return id;
  if (/\s\((?:Prompt Only|BAD)\)$/i.test(id)) return id;
  const label = pipelineProcessLabel(result.mode);
  if (label === "Unknown") return id;
  return `${id} (${label})`;
}

/** Short id for UI: `Indomie_001` from `Indomie_001 (Prompt Only)`. */
export function brandRunShortId(executionId?: string | null): string {
  const id = (executionId || "").trim();
  return id.replace(/\s\((?:Prompt Only|BAD)\)$/i, "") || id;
}

export type BrandRunMode = "prompt" | "bad";

/** Brand stem + pipeline mode, used to replace draft library rows. */
export function brandRunIdentity(
  executionId?: string | null,
  mode?: string | null
): { stem: string; modeKey: BrandRunMode } | null {
  const id = (executionId || "").trim();
  if (!id) return null;
  const suffix = id.match(/\s\((Prompt Only|BAD)\)$/i);
  const base = suffix ? id.slice(0, suffix.index).trim() : id;
  const stemMatch = base.match(/^(.*)_(\d+)$/);
  if (!stemMatch) return null;
  const stem = stemMatch[1];
  if (suffix) {
    const modeKey: BrandRunMode =
      suffix[1].toLowerCase() === "bad" ? "bad" : "prompt";
    return { stem, modeKey };
  }
  const label = pipelineProcessLabel(mode);
  if (label === "Prompt Only") return { stem, modeKey: "prompt" };
  if (label === "BAD") return { stem, modeKey: "bad" };
  return null;
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
