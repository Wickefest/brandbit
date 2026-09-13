"use client";

/**
 * Library page.
 * Personal archives and shared study stimuli for rating.
 */

import { useCallback, useEffect, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
// Reference: https://motion.dev/docs/react-quick-start
import { motion } from "motion/react";
import Navbar from "@/components/Navbar";
import PipelineShell from "@/components/PipelineShell";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import {
  deleteArchive,
  formatArchiveDate,
  listArchive,
  listSharedArchive,
  setArchiveShared,
  touchViewed,
  type ArchiveEntry,
} from "@/lib/archive";
import {
  PERSONAL_LIBRARY_MAX,
} from "@/lib/evaluation";
import { setRatingSession } from "@/lib/rating";
import { pipelineProcessLabel } from "@/lib/types";

type SortMode = "recent" | "most" | "least" | "asc" | "desc";
type ArchiveFilter = "bad" | "prompt" | "all";

const SORTS: { id: SortMode; label: string }[] = [
  { id: "recent", label: "Recently Viewed" },
  { id: "most", label: "Most Rated" },
  { id: "least", label: "Least Rated" },
  { id: "asc", label: "Ascending" },
  { id: "desc", label: "Descending" },
];

const FILTERS: { id: ArchiveFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "prompt", label: "Prompt Only" },
  { id: "bad", label: "BAD only" },
];

function entryModeKey(entry: ArchiveEntry): "bad" | "prompt" | null {
  const label = pipelineProcessLabel(entry.mode || entry.result.mode);
  if (label === "BAD") return "bad";
  if (label === "Prompt Only") return "prompt";
  return null;
}

function filterEntries(entries: ArchiveEntry[], filter: ArchiveFilter) {
  if (filter === "all") return entries;
  return entries.filter((entry) => entryModeKey(entry) === filter);
}

function sortEntries(entries: ArchiveEntry[], mode: SortMode) {
  const copy = [...entries];
  if (mode === "recent") {
    return copy.sort((a, b) => b.viewedAt.localeCompare(a.viewedAt));
  }
  if (mode === "asc") return copy.sort((a, b) => a.title.localeCompare(b.title));
  if (mode === "desc") return copy.sort((a, b) => b.title.localeCompare(a.title));
  if (mode === "most") {
    return copy.sort(
      (a, b) =>
        (b.result.refinement_history?.length ?? 0) -
        (a.result.refinement_history?.length ?? 0)
    );
  }
  return copy.sort(
    (a, b) =>
      (a.result.refinement_history?.length ?? 0) -
      (b.result.refinement_history?.length ?? 0)
  );
}

function LinkRow<T extends string>({
  items,
  active,
  onSelect,
}: {
  items: { id: T; label: string }[];
  active: T;
  onSelect: (id: T) => void;
}) {
  return (
    <p className="text-white text-xs font-light">
      {items.map((s, i) => (
        <span key={s.id}>
          {i > 0 && " | "}
          <button
            type="button"
            onClick={() => onSelect(s.id)}
            className={`transition-opacity duration-200 hover:opacity-100 ${
              active === s.id ? "font-bold opacity-100" : "opacity-55"
            }`}
          >
            {s.label}
          </button>
        </span>
      ))}
    </p>
  );
}

export default function LibraryPage() {
  const router = useRouter();
  const { isAdmin } = useAuth();

  // Sort, filter, and loaded archive lists
  const [mode, setMode] = useState<SortMode>("recent");
  const [filter, setFilter] = useState<ArchiveFilter>("all");
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [shared, setShared] = useState<ArchiveEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ArchiveEntry | null>(null);
  const [shareBusyId, setShareBusyId] = useState<string | null>(null);

  // Load personal and shared archives
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mine, study] = await Promise.all([
        listArchive(),
        listSharedArchive(),
      ]);
      setEntries(mine);
      setShared(study);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load library");
      setEntries([]);
      setShared([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const visible = filterEntries(entries, filter);
  const sorted = sortEntries(visible, mode);
  const sharedVisible = filterEntries(shared, filter);
  const recentlyViewed = [...visible]
    .sort((a, b) => b.viewedAt.localeCompare(a.viewedAt))
    .slice(0, 3);

  // Open an archive entry on the results page
  const openEntry = async (entry: ArchiveEntry) => {
    sessionStorage.setItem("bb_result", JSON.stringify(entry.result));
    if (entry.isShared) setRatingSession(true);
    else setRatingSession(false);
    if (entry.imageThumb) {
      sessionStorage.setItem("bb_image_b64", entry.imageThumb);
    }
    try {
      await touchViewed(entry.execution_id);
    } catch {
      /* open anyway */
    }
    router.push("/results");
  };

  // After delete confirm, reload lists
  const onDeleted = async () => {
    setPendingDelete(null);
    await refresh();
  };

  // Admin toggle for shared study membership
  const onToggleShare = async (entry: ArchiveEntry, next: boolean) => {
    if (shareBusyId) return;
    setShareBusyId(entry.id);
    setError(null);
    try {
      await setArchiveShared(entry.id, next);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update shared library");
    } finally {
      setShareBusyId(null);
    }
  };

  return (
    <RequireAuth>
      <main id="main-content" className="min-h-screen bg-ink flex flex-col">
        <Navbar />

        <PipelineShell title="Library" className="pb-20">
          {/* Main content */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          >
            <p className="text-white text-[13px] font-light -mt-4 mb-2">
              {isAdmin
                ? `Total of ${entries.length} on my library`
                : `Total of ${entries.length} on my library (${entries.length}/${PERSONAL_LIBRARY_MAX})`}
            </p>
            {/* Filter and sort controls */}
            <div className="mb-8 space-y-2">
              <LinkRow items={FILTERS} active={filter} onSelect={setFilter} />
              <LinkRow items={SORTS} active={mode} onSelect={setMode} />
            </div>

            {error && (
              <p className="text-red-300 text-sm mb-6">
                {error}
                {error.toLowerCase().includes("library_entries") ||
                error.toLowerCase().includes("schema cache") ||
                error.toLowerCase().includes("does not exist")
                  ? " — run prisma/setup.sql in the Supabase SQL Editor, then refresh."
                  : null}
              </p>
            )}

            {loading ? (
              <p className="text-white/60 text-sm font-light">Loading library…</p>
            ) : (
              <>
                {/* Shared study stimuli */}
                <section className="mb-12">
                  <h2 className="text-white text-2xl italic mb-2">Shared library</h2>
                  <p className="text-white/55 text-[13px] font-light mb-4 max-w-2xl">
                    Open a card to rate it. Ratings save as soon as you submit
                  </p>
                  {sharedVisible.length === 0 ? (
                    <p className="text-white/60 text-sm font-light">
                      {shared.length === 0
                        ? isAdmin
                          ? "No shared stimuli yet. Save a personal archive, then use “Add to shared study”."
                          : "The shared study is empty for now. Check back after the admin publishes pictures."
                        : `No ${filter === "bad" ? "BAD" : "Prompt Only"} entries in the shared library.`}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                      {sharedVisible.map((entry, i) => (
                        <ArchiveCard
                          key={`shared-${entry.id}`}
                          entry={entry}
                          index={i}
                          onOpen={() => void openEntry(entry)}
                          onDelete={
                            isAdmin ? () => setPendingDelete(entry) : undefined
                          }
                          onShare={
                            isAdmin
                              ? () => void onToggleShare(entry, false)
                              : undefined
                          }
                          shareLabel="Remove from shared"
                          shareBusy={shareBusyId === entry.id}
                        />
                      ))}
                    </div>
                  )}
                </section>

                {recentlyViewed.length > 0 ? (
                  <section className="mb-12">
                    <h2 className="text-white text-2xl italic mb-4">Recently Viewed</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                      {recentlyViewed.map((entry, i) => (
                        <ArchiveCard
                          key={`recent-${entry.id}`}
                          entry={entry}
                          index={i}
                          onOpen={() => void openEntry(entry)}
                          onDelete={() => setPendingDelete(entry)}
                          onShare={
                            isAdmin
                              ? () => void onToggleShare(entry, true)
                              : undefined
                          }
                          shareLabel="Add to shared study"
                          shareBusy={shareBusyId === entry.id}
                        />
                      ))}
                    </div>
                  </section>
                ) : null}

                <section>
                  {/* Personal archives */}
                  <h2 className="text-white text-2xl italic mb-4">My library</h2>
                  {sorted.length === 0 ? (
                    <p className="text-white/60 text-sm font-light">
                      {entries.length === 0
                        ? "No personal archives yet. Run the generation through new submission, then save this archive on the results page."
                        : `No ${filter === "bad" ? "BAD" : "Prompt Only"} entries in your library.`}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                      {sorted.map((entry, i) => (
                        <ArchiveCard
                          key={entry.id}
                          entry={entry}
                          index={i}
                          onOpen={() => void openEntry(entry)}
                          onDelete={() => setPendingDelete(entry)}
                          onShare={
                            isAdmin
                              ? () => void onToggleShare(entry, true)
                              : undefined
                          }
                          shareLabel="Add to shared study"
                          shareBusy={shareBusyId === entry.id}
                        />
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </motion.div>
        </PipelineShell>

        {pendingDelete && (
          <DeleteConfirmModal
            entry={pendingDelete}
            onCancel={() => setPendingDelete(null)}
            onDeleted={() => void onDeleted()}
          />
        )}
      </main>
    </RequireAuth>
  );
}

function ArchiveCard({
  entry,
  index,
  onOpen,
  onDelete,
  onShare,
  shareLabel,
  shareBusy,
}: {
  entry: ArchiveEntry;
  index: number;
  onOpen: () => void;
  onDelete?: () => void;
  onShare?: () => void;
  shareLabel?: string;
  shareBusy?: boolean;
}) {
  const process = pipelineProcessLabel(entry.mode || entry.result.mode);

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -10, scale: 1.015 }}
      transition={{
        type: "spring",
        stiffness: 320,
        damping: 24,
        delay: index * 0.04,
      }}
      className="group"
    >
      <div
        role="button"
        tabIndex={0}
        onClick={onOpen}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onOpen();
          }
        }}
        className="bg-lemon rounded-[20px] h-[255px] p-4 flex gap-4 cursor-pointer shadow-[0_0_0_rgba(0,0,0,0)] transition-shadow duration-250 group-hover:shadow-[0_18px_40px_rgba(0,0,0,0.38)]"
      >
        <div className="w-[183px] h-[226px] bg-[#FFF7F7] rounded-[20px] overflow-hidden shrink-0">
          {entry.imageThumb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={entry.imageThumb}
              alt=""
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : null}
        </div>
        <div className="flex flex-col min-w-0 flex-1 py-1">
          <p className="text-black text-2xl font-bold leading-tight truncate">
            {entry.title}
          </p>
          <span className="mt-2 inline-flex w-fit rounded-full bg-ink/90 px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-gold">
            {process}
          </span>
          <p className="text-black text-[13px] font-light leading-[25px] mt-3 line-clamp-4">
            {entry.summary}
          </p>
          <span className="mt-auto text-[13px] font-light text-black text-right transition-transform duration-200 group-hover:translate-x-1">
            → Check Result
          </span>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-3 px-1">
        <p className="text-[#FFF2F2]/70 text-[12px] font-light">{process} process</p>
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <p className="text-[#FFF2F2] text-[13px] font-light">
            {formatArchiveDate(entry.savedAt)}
          </p>
          {onShare && shareLabel ? (
            <button
              type="button"
              disabled={shareBusy}
              onClick={(e) => {
                e.stopPropagation();
                onShare();
              }}
              className="text-[12px] font-light text-gold/90 hover:text-gold disabled:opacity-40 cursor-pointer"
            >
              {shareBusy ? "Updating…" : shareLabel}
            </button>
          ) : null}
          {onDelete ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="text-[12px] font-light text-red-300/80 hover:text-red-300 cursor-pointer"
            >
              Delete
            </button>
          ) : null}
        </div>
      </div>
    </motion.article>
  );
}

function DeleteConfirmModal({
  entry,
  onCancel,
  onDeleted,
}: {
  entry: ArchiveEntry;
  onCancel: () => void;
  onDeleted: () => void;
}) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const matches = typed.trim() === entry.title.trim();

  const confirm = async () => {
    setBusy(true);
    setErr(null);
    try {
      await deleteArchive(entry, typed);
      onDeleted();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-archive-title"
    >
      <div className="w-full max-w-md rounded-[24px] bg-panel border border-white/10 p-6 shadow-2xl">
        <h2 id="delete-archive-title" className="text-white text-xl font-bold m-0">
          Delete archive?
        </h2>
        <p className="text-white/70 text-sm font-light mt-3 leading-relaxed">
          This permanently removes the library entry from Supabase. Type the archive name
          to confirm:
        </p>
        <p className="text-gold text-sm font-mono mt-3 break-all">{entry.title}</p>
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="Type the name exactly"
          autoFocus
          className="mt-4 w-full rounded-xl bg-[#D9D9D9] text-black px-4 py-3 text-sm outline-none"
        />
        {err && <p className="text-red-300 text-sm mt-3">{err}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-full px-4 py-2 text-sm text-white/80 hover:text-white cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void confirm()}
            disabled={!matches || busy}
            className="rounded-full bg-red-600/90 px-5 py-2 text-sm font-bold text-white disabled:opacity-40 cursor-pointer"
          >
            {busy ? "Deleting…" : "Delete permanently"}
          </button>
        </div>
      </div>
    </div>
  );
}
