/**
 * Personal library archive helpers.
 * Save list share and open stored generation entries.
 */

import type { ApiResult } from "./types";
import { archiveDisplayName, brandRunIdentity } from "./types";
import { createClient } from "@/lib/supabase/client";
import { resolveAudioUrl } from "@/lib/api";

const IMAGE_BUCKET = "library-images";
const AUDIO_BUCKET = "library-audio";

export interface ArchiveEntry {
  id: string;
  execution_id: string;
  savedAt: string;
  viewedAt: string;
  imageThumb: string | null;
  title: string;
  summary: string;
  result: ApiResult;
  mode?: string | null;
  isShared: boolean;
}

type LibraryRow = {
  id: string;
  user_id: string;
  execution_id: string;
  title: string;
  summary: string;
  mode: string | null;
  image_url: string | null;
  generated_output: ApiResult;
  is_shared?: boolean;
  saved_at: string;
  viewed_at: string;
};

type SupabaseClient = NonNullable<ReturnType<typeof createClient>>;

function rowToEntry(row: LibraryRow): ArchiveEntry {
  return {
    id: row.id,
    execution_id: row.execution_id,
    savedAt: row.saved_at,
    viewedAt: row.viewed_at,
    imageThumb: row.image_url,
    title: row.title,
    summary: row.summary,
    result: row.generated_output,
    mode: row.mode,
    isShared: Boolean(row.is_shared),
  };
}

async function requireUser() {
  const supabase = createClient();
  if (!supabase) throw new Error("Supabase is not configured");
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();
  if (error || !user) throw new Error("You must be signed in to use the Library");
  return { supabase, user };
}

export function makeThumb(dataUrl: string, max = 480): Promise<string | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(max / img.width, max / img.height, 1);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(null);
        return;
      }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.78));
    };
    img.onerror = () => resolve(null);
    img.src = dataUrl;
  });
}

function dataUrlToBlob(dataUrl: string): Blob | null {
  const match = dataUrl.match(/^data:(.+?);base64,(.+)$/);
  if (!match) return null;
  const mime = match[1];
  const binary = atob(match[2]);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const copy = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(copy).set(bytes);
  return new Blob([copy], { type: mime });
}

async function uploadThumb(
  supabase: SupabaseClient,
  userId: string,
  executionId: string,
  imagePreview: string | null
): Promise<string | null> {
  if (!imagePreview) return null;
  const thumb = imagePreview.startsWith("data:")
    ? await makeThumb(imagePreview)
    : imagePreview;
  if (!thumb?.startsWith("data:")) return thumb;

  const blob = dataUrlToBlob(thumb);
  if (!blob) return null;

  const path = `${userId}/${executionId}.jpg`;
  const { error } = await supabase.storage.from(IMAGE_BUCKET).upload(path, blob, {
    upsert: true,
    contentType: "image/jpeg",
  });
  if (error) {
    console.warn("Library image upload failed:", error.message);
    return null;
  }
  const { data } = supabase.storage.from(IMAGE_BUCKET).getPublicUrl(path);
  return data.publicUrl;
}

/** Fetch MusicGen WAV from backend (or existing URL) and store in Supabase Storage. */
async function uploadAudio(
  supabase: SupabaseClient,
  userId: string,
  executionId: string,
  result: ApiResult
): Promise<string | null> {
  const ref =
    result.music_direction?.audio_sample_ref || result.audio_sample_ref || null;
  if (!ref) return null;

  // Already a durable public URL (e.g. prior Supabase upload)
  if (/^https?:\/\//i.test(ref) && ref.includes("/storage/v1/object/public/")) {
    return ref;
  }

  const sourceUrl = resolveAudioUrl(ref);
  if (!sourceUrl) return null;

  try {
    const res = await fetch(sourceUrl);
    if (!res.ok) {
      console.warn("Library audio fetch failed:", res.status, sourceUrl);
      return null;
    }
    const blob = await res.blob();
    const path = `${userId}/${executionId}.wav`;
    const { error } = await supabase.storage.from(AUDIO_BUCKET).upload(path, blob, {
      upsert: true,
      contentType: "audio/wav",
    });
    if (error) {
      console.warn("Library audio upload failed:", error.message);
      return null;
    }
    const { data } = supabase.storage.from(AUDIO_BUCKET).getPublicUrl(path);
    return data.publicUrl;
  } catch (e) {
    console.warn("Library audio upload error:", e);
    return null;
  }
}

function withAudioUrls(result: ApiResult, audioUrl: string | null): ApiResult {
  if (!audioUrl) return result;
  return {
    ...result,
    audio_sample_ref: audioUrl,
    music_direction: {
      ...result.music_direction,
      audio_sample_ref: audioUrl,
    },
  };
}

export async function listArchive(): Promise<ArchiveEntry[]> {
  const { supabase, user } = await requireUser();
  const { data, error } = await supabase
    .from("library_entries")
    .select("*")
    .eq("user_id", user.id)
    .eq("is_shared", false)
    .order("viewed_at", { ascending: false });

  if (error) throw new Error(error.message);
  return (data as LibraryRow[] | null)?.map(rowToEntry) ?? [];
}

export async function listSharedArchive(): Promise<ArchiveEntry[]> {
  const { supabase } = await requireUser();
  const { data, error } = await supabase
    .from("library_entries")
    .select("*")
    .eq("is_shared", true)
    .order("saved_at", { ascending: true });

  if (error) throw new Error(error.message);
  return (data as LibraryRow[] | null)?.map(rowToEntry) ?? [];
}

export async function setArchiveShared(
  entryId: string,
  shared: boolean
): Promise<void> {
  const { supabase } = await requireUser();
  const { error } = await supabase
    .from("library_entries")
    .update({ is_shared: shared })
    .eq("id", entryId);
  if (error) throw new Error(error.message);
}

export async function touchViewed(executionId: string): Promise<void> {
  const { supabase, user } = await requireUser();
  const now = new Date().toISOString();
  const { error } = await supabase
    .from("library_entries")
    .update({ viewed_at: now })
    .eq("user_id", user.id)
    .eq("execution_id", executionId);
  if (error) throw new Error(error.message);
}

export async function saveArchive(
  result: ApiResult,
  imagePreview: string | null,
  options?: { title?: string; shared?: boolean }
): Promise<ArchiveEntry> {
  const { supabase, user } = await requireUser();
  const desc = result.brand_aesthetic_descriptor;
  const summary =
    desc.narrative ||
    (desc.mood || []).slice(0, 3).join(", ") ||
    result.fragrance_concept.smell_signature ||
    "Saved brand archive.";
  const title =
    (options?.title || archiveDisplayName(result)).trim() ||
    archiveDisplayName(result);
  const now = new Date().toISOString();
  const [imageUrl, audioUrl] = await Promise.all([
    uploadThumb(supabase, user.id, result.execution_id, imagePreview),
    uploadAudio(supabase, user.id, result.execution_id, result),
  ]);

  const persisted = withAudioUrls(result, audioUrl);

  // Omit is_shared on normal saves so upsert cannot demote a shared study entry.
  const payload: Record<string, unknown> = {
    user_id: user.id,
    execution_id: result.execution_id,
    title,
    summary,
    mode: result.mode ?? null,
    image_url: imageUrl,
    generated_output: persisted,
    saved_at: now,
    viewed_at: now,
  };
  if (options?.shared !== undefined) {
    payload.is_shared = options.shared;
  }

  const { data, error } = await supabase
    .from("library_entries")
    .upsert(payload, { onConflict: "user_id,execution_id" })
    .select("*")
    .single();

  if (error) throw new Error(error.message);

  await removeDraftLibraryRows(supabase, user.id, result);

  if (typeof window !== "undefined" && audioUrl) {
    sessionStorage.setItem("bb_result", JSON.stringify(persisted));
  }

  return rowToEntry(data as LibraryRow);
}

async function removeDraftLibraryRows(
  supabase: SupabaseClient,
  userId: string,
  result: ApiResult
): Promise<void> {
  // Only replace drafts when this save is the finalized mode-named slot.
  if (!/\s\((?:Prompt Only|BAD)\)$/i.test(result.execution_id)) return;
  const identity = brandRunIdentity(result.execution_id, result.mode);
  if (!identity) return;

  const { data, error } = await supabase
    .from("library_entries")
    .select("id, execution_id, mode, generated_output")
    .eq("user_id", userId);

  if (error || !data) {
    if (error) console.warn("Library draft cleanup skipped:", error.message);
    return;
  }

  const drafts = (data as LibraryRow[]).filter((row) => {
    if (row.execution_id === result.execution_id) return false;
    const rowIdentity = brandRunIdentity(
      row.execution_id,
      row.mode || row.generated_output?.mode
    );
    return (
      rowIdentity?.stem === identity.stem &&
      rowIdentity?.modeKey === identity.modeKey
    );
  });

  await Promise.all(
    drafts.map(async (row) => {
      await Promise.all([
        supabase.storage
          .from(IMAGE_BUCKET)
          .remove([`${userId}/${row.execution_id}.jpg`]),
        supabase.storage
          .from(AUDIO_BUCKET)
          .remove([`${userId}/${row.execution_id}.wav`]),
      ]);
      const { error: delError } = await supabase
        .from("library_entries")
        .delete()
        .eq("user_id", userId)
        .eq("execution_id", row.execution_id);
      if (delError) {
        console.warn("Library draft delete failed:", delError.message);
      }
    })
  );
}

export async function deleteArchive(
  entry: ArchiveEntry,
  typedName: string
): Promise<void> {
  const expected = entry.title.trim();
  if (typedName.trim() !== expected) {
    throw new Error(`Type the exact name “${expected}” to confirm deletion`);
  }

  const { supabase, user } = await requireUser();

  await Promise.all([
    supabase.storage
      .from(IMAGE_BUCKET)
      .remove([`${user.id}/${entry.execution_id}.jpg`]),
    supabase.storage
      .from(AUDIO_BUCKET)
      .remove([`${user.id}/${entry.execution_id}.wav`]),
  ]);

  let query = supabase.from("library_entries").delete().eq("id", entry.id);
  if (!entry.isShared) {
    query = query.eq("user_id", user.id);
  }
  const { error } = await query;

  if (error) throw new Error(error.message);
}

export function formatArchiveDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}.${d.getFullYear()}`;
}
