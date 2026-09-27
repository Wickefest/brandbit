/**
 * Shared study rating session helpers.
 * Rating mode flags and next unrated shared stimulus lookup.
 */

import { createClient } from "@/lib/supabase/client";
import { brandRunIdentity } from "@/lib/types";
import type { ApiResult } from "@/lib/types";

export const RATING_MODE_KEY = "bb_rating_mode";

export type SharedStimulus = {
  entryId: string;
  executionId: string;
  imageUrl: string;
  result: ApiResult;
};

export function isRatingSession(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(RATING_MODE_KEY) === "1";
}

export function setRatingSession(enabled: boolean): void {
  if (typeof window === "undefined") return;
  if (enabled) sessionStorage.setItem(RATING_MODE_KEY, "1");
  else sessionStorage.removeItem(RATING_MODE_KEY);
}

function lookupKeys(executionId: string): string[] {
  const keys = new Set([executionId]);
  const suffixed = executionId.match(/^(.*_\d+)\s*\((Prompt Only|BAD)\)$/i);
  if (suffixed) {
    keys.add(suffixed[1]);
  } else if (/_(\d+)$/.test(executionId)) {
    keys.add(`${executionId} (Prompt Only)`);
    keys.add(`${executionId} (BAD)`);
  }
  return [...keys];
}

/** Shared library stimulus matching this execution, if any. */
export async function findSharedStimulus(
  executionId: string
): Promise<SharedStimulus | null> {
  const id = executionId.trim();
  if (!id) return null;
  const supabase = createClient();
  if (!supabase) return null;

  const { data, error } = await supabase
    .from("library_entries")
    .select("id, execution_id, image_url, generated_output, mode")
    .eq("is_shared", true)
    .in("execution_id", lookupKeys(id))
    .limit(20);

  if (error || !data?.length) return null;

  const identity = brandRunIdentity(id);
  const row =
    data.find((item) => item.execution_id === id) ||
    data.find((item) => {
      if (!identity) return false;
      const rowIdentity = brandRunIdentity(
        item.execution_id,
        (item.generated_output as { mode?: string } | null)?.mode || item.mode
      );
      return (
        rowIdentity?.stem === identity.stem &&
        rowIdentity?.modeKey === identity.modeKey
      );
    }) ||
    data[0];

  if (!row) return null;
  return {
    entryId: row.id as string,
    executionId: row.execution_id as string,
    imageUrl: (row.image_url as string) || "",
    result: row.generated_output as ApiResult,
  };
}

export async function isEvaluationStimulus(
  executionId: string
): Promise<boolean> {
  return (await findSharedStimulus(executionId)) != null;
}

/** Next unrated shared library entry (by saved_at). */
export async function findNextUnratedShared(
  currentEntryId: string,
  userId: string
): Promise<SharedStimulus | null> {
  const supabase = createClient();
  if (!supabase) return null;

  const [{ data: items }, { data: mine }] = await Promise.all([
    supabase
      .from("library_entries")
      .select("id, execution_id, image_url, generated_output, saved_at")
      .eq("is_shared", true)
      .order("saved_at", { ascending: true }),
    supabase
      .from("library_ratings")
      .select("library_entry_id")
      .eq("participant_id", userId),
  ]);

  if (!items?.length) return null;
  const rated = new Set(
    (mine ?? []).map((row) => row.library_entry_id as string)
  );
  const currentIdx = items.findIndex((item) => item.id === currentEntryId);
  const ordered =
    currentIdx < 0
      ? items
      : [...items.slice(currentIdx + 1), ...items.slice(0, currentIdx)];

  const next = ordered.find((item) => !rated.has(item.id as string));
  if (!next) return null;
  return {
    entryId: next.id as string,
    executionId: next.execution_id as string,
    imageUrl: (next.image_url as string) || "",
    result: next.generated_output as ApiResult,
  };
}
