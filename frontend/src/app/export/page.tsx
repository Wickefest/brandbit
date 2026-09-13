"use client";

/**
 * Study export page.
 * Admin download of human ratings and DeepSeek/CLIP automated scores as CSV.
 */

import { useEffect, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import GoldButton from "@/components/GoldButton";
import PipelineShell from "@/components/PipelineShell";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import { LIKERT_QUESTIONS } from "@/lib/evaluation";
import {
  automatedScoresToCsv,
  downloadTextFile,
  libraryRatingsToLabeledCsv,
  loadAutomatedScoreExport,
  loadStudyRatingExport,
  type AutomatedScoreExportSummary,
  type StudyExportSummary,
} from "@/lib/study";

export default function ExportPage() {
  const router = useRouter();
  const { isAdmin, loading: authLoading } = useAuth();

  const [ratingsBusy, setRatingsBusy] = useState(false);
  const [scoresBusy, setScoresBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ratingSummary, setRatingSummary] = useState<StudyExportSummary | null>(
    null
  );
  const [scoreSummary, setScoreSummary] =
    useState<AutomatedScoreExportSummary | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAdmin) router.replace("/");
  }, [authLoading, isAdmin, router]);

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    void Promise.all([loadStudyRatingExport(), loadAutomatedScoreExport()])
      .then(([ratings, scores]) => {
        if (cancelled) return;
        setRatingSummary(ratings);
        setScoreSummary(scores);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load export data");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const onDownloadRatings = async () => {
    if (ratingsBusy) return;
    setRatingsBusy(true);
    setError(null);
    try {
      const pack = await loadStudyRatingExport();
      setRatingSummary(pack);
      if (pack.ratingCount === 0) {
        setError(
          pack.sharedTotal === 0
            ? "No shared study pictures yet. Add BAD and Prompt Only entries to the shared library first."
            : "No ratings submitted yet for the shared study pictures."
        );
        return;
      }
      const stamp = new Date().toISOString().slice(0, 10);
      downloadTextFile(
        `brandbit-shared-study-ratings-${stamp}.csv`,
        libraryRatingsToLabeledCsv(pack.rows),
        "text/csv;charset=utf-8"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not export ratings CSV");
    } finally {
      setRatingsBusy(false);
    }
  };

  const onDownloadAutomated = async () => {
    if (scoresBusy) return;
    setScoresBusy(true);
    setError(null);
    try {
      const pack = await loadAutomatedScoreExport();
      setScoreSummary(pack);
      if (pack.scoredCount === 0) {
        setError(
          pack.sharedTotal === 0
            ? "No shared study pictures yet. Add BAD and Prompt Only entries to the shared library first."
            : "Shared pictures have no congruence_report in generated_output yet."
        );
        return;
      }
      const stamp = new Date().toISOString().slice(0, 10);
      downloadTextFile(
        `brandbit-shared-judge-clip-scores-${stamp}.csv`,
        automatedScoresToCsv(pack.rows),
        "text/csv;charset=utf-8"
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not export judge/CLIP CSV"
      );
    } finally {
      setScoresBusy(false);
    }
  };

  if (authLoading || !isAdmin) {
    return (
      <RequireAuth>
        <main id="main-content" className="min-h-screen bg-ink flex flex-col">
          <Navbar />
        </main>
      </RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <main id="main-content" className="min-h-screen bg-ink flex flex-col">
        <Navbar />
        <PipelineShell title="Export study data" className="pb-20">
          <div className="flex flex-1 justify-center items-start">
            <div className="w-full max-w-[720px] space-y-8">
              {/* Human Likert ratings */}
              <section className="bg-panel rounded-[30px] px-8 py-10 sm:px-12 text-center shadow-[0_18px_40px_rgba(0,0,0,0.28)]">
                <h2 className="text-white text-xl font-bold m-0">
                  Participant ratings
                </h2>
                <p className="text-white/70 text-sm font-light leading-6 m-0 mt-3 mx-auto max-w-xl text-left">
                  Pulls every submitted rating from Supabase for your shared
                  study pictures. Columns match the rating card Likert items
                  (1–5), plus comments and background experience.
                </p>

                <ul className="mt-8 mb-0 mx-auto max-w-lg list-none p-0 space-y-3 text-left">
                  {LIKERT_QUESTIONS.map((q) => (
                    <li
                      key={q.key}
                      className="text-white/55 text-[13px] font-light leading-5"
                    >
                      <span className="text-white/85 font-bold">{q.title}</span>
                      <span className="block mt-0.5">{q.prompt}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8 text-white text-[13px] font-light space-y-1">
                  {ratingSummary == null ? (
                    <p className="m-0">Checking Supabase…</p>
                  ) : (
                    <>
                      <p className="m-0">
                        Shared pictures: {ratingSummary.sharedTotal} (
                        {ratingSummary.badCount} BAD ·{" "}
                        {ratingSummary.promptCount} Prompt Only)
                      </p>
                      <p className="m-0">
                        Ratings ready: {ratingSummary.ratingCount} from{" "}
                        {ratingSummary.participantCount} participant
                        {ratingSummary.participantCount === 1 ? "" : "s"}
                      </p>
                    </>
                  )}
                </div>

                <div className="mt-8 flex justify-center">
                  <GoldButton
                    onClick={() => void onDownloadRatings()}
                    disabled={ratingsBusy}
                  >
                    {ratingsBusy ? "Preparing…" : "Download ratings CSV"}
                  </GoldButton>
                </div>
              </section>

              {/* DeepSeek judge + CLIP */}
              <section className="bg-panel rounded-[30px] px-8 py-10 sm:px-12 text-center shadow-[0_18px_40px_rgba(0,0,0,0.28)]">
                <h2 className="text-white text-xl font-bold m-0">
                  Judge &amp; CLIP scores
                </h2>
                <p className="text-white/70 text-sm font-light leading-6 m-0 mt-3 mx-auto max-w-xl text-left">
                  One row per shared library picture, read from{" "}
                  <code className="text-white/90">generated_output.congruence_report</code>
                  . Includes DeepSeek fragrance/music scores (descriptor
                  alignment) and CLIP image↔fragrance / image↔music proxies.
                </p>

                <ul className="mt-8 mb-0 mx-auto max-w-lg list-none p-0 space-y-2 text-left text-white/55 text-[13px] font-light leading-5">
                  <li>
                    <span className="text-white/85 font-bold">
                      DeepSeek fragrance / music
                    </span>{" "}
                    — 1–5 vs brand descriptor
                  </li>
                  <li>
                    <span className="text-white/85 font-bold">
                      CLIP image-fragrance / image-music
                    </span>{" "}
                    — automated image–text similarity
                  </li>
                  <li>
                    <span className="text-white/85 font-bold">
                      Congruence accepted / regen count
                    </span>{" "}
                    — pipeline pass/fail metadata
                  </li>
                </ul>

                <div className="mt-8 text-white text-[13px] font-light space-y-1">
                  {scoreSummary == null ? (
                    <p className="m-0">Checking Supabase…</p>
                  ) : (
                    <>
                      <p className="m-0">
                        Shared pictures: {scoreSummary.sharedTotal} (
                        {scoreSummary.badCount} BAD · {scoreSummary.promptCount}{" "}
                        Prompt Only)
                      </p>
                      <p className="m-0">
                        Rows with congruence report: {scoreSummary.scoredCount}
                        {scoreSummary.missingReportCount > 0
                          ? ` (${scoreSummary.missingReportCount} missing report)`
                          : ""}
                      </p>
                    </>
                  )}
                </div>

                <div className="mt-8 flex justify-center">
                  <GoldButton
                    onClick={() => void onDownloadAutomated()}
                    disabled={scoresBusy}
                  >
                    {scoresBusy ? "Preparing…" : "Download judge + CLIP CSV"}
                  </GoldButton>
                </div>
              </section>

              {error ? (
                <p className="text-red-300 text-sm mt-0 mb-0 text-center" role="alert">
                  {error}
                </p>
              ) : null}
            </div>
          </div>
        </PipelineShell>
      </main>
    </RequireAuth>
  );
}
