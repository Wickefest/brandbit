"use client";

/**
 * Processing page.
 * Shows live pipeline stages while the backend generates a concept.
 */

import { useEffect, useRef, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
// Reference: https://motion.dev/docs/react-quick-start
import { motion } from "motion/react";
import Navbar from "@/components/Navbar";
import BrandPhotoCard from "@/components/BrandPhotoCard";
import PipelineShell from "@/components/PipelineShell";
import RequireAuth from "@/components/RequireAuth";
import ProcessAlert from "@/components/ProcessAlert";
import { useAuth } from "@/components/AuthProvider";
import { generateConcept, type GenerateStageEvent } from "@/lib/api";
import type { ApiResult } from "@/lib/types";
import {
  GENERATION_MAX,
  getGenerationStatus,
  recordGeneration,
} from "@/lib/evaluation";

type StepStatus = "pending" | "loading" | "done" | "error";

/** Survives React Strict Mode remounts so one Submit click cannot spawn two /api/generate runs. */
let processFlight: Promise<ApiResult> | null = null;
let processStageHandler: ((event: GenerateStageEvent) => void) | null = null;
let generationRecordedForFlight = false;

const STEPS_BAD = [
  {
    title: "Visual Analysis",
    details: ["Waiting for visual analysis…"],
    done: "Visual analysis complete",
  },
  {
    title: "Descriptor & Sensory Concepts",
    details: ["Waiting for BAD and specialists…"],
    done: "Fragrance concept and music direction ready",
  },
  {
    title: "Congruence & Archive",
    details: ["Waiting for congruence scoring…"],
    done: "Congruence scored and archive filed",
  },
] as const;

const STEPS_PROMPT = [
  {
    title: "Visual Analysis",
    details: ["Waiting for visual analysis…"],
    done: "Image parse ready for specialist agents",
  },
  {
    title: "Sensory Concepts",
    details: ["Waiting for specialist agents…"],
    done: "Fragrance concept and music direction ready",
  },
  {
    title: "Congruence & Archive",
    details: ["Waiting for congruence scoring…"],
    done: "Congruence scored and archive filed",
  },
] as const;

function b64toFile(dataUrl: string, filename: string): File {
  const [header, data] = dataUrl.split(",");
  const mimeMatch = header.match(/:(.*?);/);
  const mime = mimeMatch ? mimeMatch[1] : "image/jpeg";
  const binary = atob(data);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return new File([arr], filename, { type: mime });
}

function LoadingDots() {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setFrame((f) => (f + 1) % 4);
    }, 250);
    return () => clearInterval(id);
  }, []);

  const dots = ".".repeat(frame);
  return (
    <span className="inline-block w-[1.5em] text-left" aria-hidden="true">
      {dots}
    </span>
  );
}

function StepIndicator({ status }: { status: StepStatus }) {
  if (status === "loading") {
    return <span className="loading-spinner shrink-0" aria-hidden="true" />;
  }
  if (status === "done") {
    return (
      <span className="loading-check shrink-0" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M2.5 6.2L5 8.7L9.5 3.5"
            stroke="#FEFFE5"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    );
  }
  if (status === "error") {
    return (
      <span
        className="shrink-0 size-[22px] rounded-full border-2 border-red-300/70"
        aria-hidden="true"
      />
    );
  }
  return (
    <span
      className="shrink-0 size-[22px] rounded-full border-2 border-white/20"
      aria-hidden="true"
    />
  );
}

export default function ProcessPage() {
  const router = useRouter();
  const { user, isAdmin, loading: authLoading } = useAuth();

  // Pipeline step UI and live status from the API
  const [statuses, setStatuses] = useState<StepStatus[]>([
    "pending",
    "pending",
    "pending",
  ]);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [pipelineMode, setPipelineMode] = useState<"bad" | "prompt">("bad");
  const [liveDetail, setLiveDetail] = useState<string | null>(null);
  const [liveStep, setLiveStep] = useState(0);
  const startRef = useRef<number>(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const steps = pipelineMode === "prompt" ? STEPS_PROMPT : STEPS_BAD;
  const aliveRef = useRef(true);
  const userRef = useRef(user);
  const isAdminRef = useRef(isAdmin);
  userRef.current = user;
  isAdminRef.current = isAdmin;

  const stopTimer = () => {
    if (tickRef.current != null) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (startRef.current > 0) {
      setElapsed((Date.now() - startRef.current) / 1000);
    }
  };

  // Start (or reattach to) the generation request from sessionStorage image data
  useEffect(() => {
    if (authLoading) return;

    aliveRef.current = true;
    const b64 = sessionStorage.getItem("bb_image_b64");
    const name = sessionStorage.getItem("bb_image_name") || "image.jpg";
    const storedMode = sessionStorage.getItem("bb_pipeline_mode");
    const mode = storedMode === "prompt" ? "prompt" : "bad";
    setPipelineMode(mode);

    if (!b64) {
      processFlight = null;
      generationRecordedForFlight = false;
      sessionStorage.removeItem("bb_process_inflight");
      router.push("/submit");
      return;
    }

    let cancelled = false;

    const startPipeline = async () => {
      const currentUser = userRef.current;
      if (currentUser?.id && !isAdminRef.current) {
        const status = await getGenerationStatus(currentUser.id);
        if (cancelled || !aliveRef.current) return;
        if (status.remaining <= 0) {
          stopTimer();
          setError(
            `This account has used all ${GENERATION_MAX} generations.`
          );
          setAlertOpen(true);
          setStatuses(["error", "pending", "pending"]);
          return;
        }
      }

      startRef.current = Date.now();
      queueMicrotask(() => {
        if (!aliveRef.current) return;
        setImagePreview(b64);
        setStatuses(["loading", "pending", "pending"]);
        setLiveDetail("Uploading image and starting the pipeline");
        setLiveStep(0);
        setError(null);
        setAlertOpen(false);
        setElapsed(0);
      });

      if (tickRef.current != null) clearInterval(tickRef.current);
      tickRef.current = setInterval(() => {
        if (aliveRef.current) {
          setElapsed((Date.now() - startRef.current) / 1000);
        }
      }, 100);

      const brandItem = sessionStorage.getItem("bb_brand_item");

      const stepForStage = (stage: string): number => {
        if (stage === "visual") return 0;
        if (
          stage === "descriptor" ||
          stage === "specialists" ||
          stage === "fragrance" ||
          stage === "music" ||
          stage === "audio"
        ) {
          return 1;
        }
        return 2;
      };

      const applyStage = (
        stage: string,
        status: string,
        message?: string | null
      ) => {
        if (!aliveRef.current) return;
        const step = stepForStage(stage);
        setLiveStep(step);
        if (message) setLiveDetail(message);

        if (stage === "visual") {
          if (status === "started") {
            setStatuses(["loading", "pending", "pending"]);
          } else if (status === "done") {
            setStatuses(["done", "loading", "pending"]);
          }
          return;
        }

        if (
          stage === "descriptor" ||
          stage === "specialists" ||
          stage === "fragrance" ||
          stage === "music" ||
          stage === "audio"
        ) {
          setStatuses(["done", "loading", "pending"]);
          return;
        }

        if (
          stage === "congruence" ||
          stage === "clip" ||
          stage === "rationale" ||
          stage === "save"
        ) {
          if (status === "done" && stage === "save") {
            setStatuses(["done", "done", "done"]);
          } else {
            setStatuses(["done", "done", "loading"]);
          }
        }
      };

      // Single-flight: Strict Mode remount attaches to the same promise (no second POST).
      processStageHandler = ({ stage, status, message }) => {
        applyStage(stage, status, message);
      };

      if (!processFlight) {
        generationRecordedForFlight = false;
        sessionStorage.setItem("bb_process_inflight", "1");
        processFlight = generateConcept({
          image: b64toFile(b64, name),
          brandItem,
          mode,
          onStage: (event) => {
            processStageHandler?.(event);
          },
        }).finally(() => {
          sessionStorage.removeItem("bb_process_inflight");
          processFlight = null;
          processStageHandler = null;
        });
      }

      processFlight
        .then(async (result) => {
          stopTimer();
          if (!aliveRef.current) return;
          const u = userRef.current;
          if (u?.id && !isAdminRef.current && !generationRecordedForFlight) {
            generationRecordedForFlight = true;
            try {
              await recordGeneration(u.id);
            } catch {
              /* best-effort counter */
            }
          }
          sessionStorage.setItem("bb_result", JSON.stringify(result));
          setStatuses(["done", "done", "done"]);
          setLiveDetail("Done");
          setTimeout(() => {
            if (aliveRef.current) router.push("/results");
          }, 400);
        })
        .catch((err: Error) => {
          stopTimer();
          if (!aliveRef.current) return;
          setError(err.message);
          setAlertOpen(true);
          setStatuses((s) => s.map((v) => (v === "loading" ? "error" : v)));
        });
    };

    void startPipeline();

    return () => {
      cancelled = true;
      aliveRef.current = false;
      if (tickRef.current != null) {
        clearInterval(tickRef.current);
        tickRef.current = null;
      }
    };
  }, [router, authLoading]);
  const detailFor = (i: number, status: StepStatus) => {
    if (status === "error") return "This step failed";
    if (status === "done") return steps[i].done;
    if (status === "pending") return steps[i].details[0];
    // Active step: show the live backend message so it matches the real process
    if (status === "loading" && liveDetail && liveStep === i) {
      return liveDetail;
    }
    return steps[i].details[0];
  };

  const stillProcessing = statuses.some((s) => s === "loading" || s === "pending");
  const allDone = statuses.every((s) => s === "done");

  return (
    <RequireAuth>
    <main id="main-content" className="min-h-screen lg:h-screen lg:overflow-hidden bg-ink flex flex-col">
      <Navbar />

      <PipelineShell className="lg:overflow-hidden">
        {/* Main content */}
        <div className="flex-1 flex items-start min-h-0 pt-2">
          <div className="w-full flex flex-col lg:flex-row gap-12 lg:gap-16 items-start">
            {/* Spacer matches ModeSelect row on submit so the gold card Y aligns */}
            <div className="flex flex-col items-start shrink-0">
              <div className="mb-4 h-[24px]" aria-hidden="true" />
              <BrandPhotoCard>
                {imagePreview ? (
                  <img
                    src={imagePreview}
                    alt="Processing"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="h-full" />
                )}
              </BrandPhotoCard>
            </div>

            {/* Pipeline step list */}
            <motion.div
              className="flex-1 w-full pt-1 min-w-0"
              initial={{ opacity: 0, x: 36 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.12, duration: 0.35, ease: "easeOut" }}
            >
              <div
                className="bg-gold-soft rounded-[20px] h-[58px] px-8 flex items-center justify-between"
                role="status"
                aria-live="polite"
                aria-atomic="true"
              >
                <span className="text-white text-2xl font-bold inline-flex items-center gap-3">
                  {stillProcessing && !error ? (
                    <span className="loading-spinner-sm shrink-0" aria-hidden="true" />
                  ) : null}
                  <span className="inline-flex items-baseline">
                    {error ? "Failed" : allDone ? "Done" : "Processing"}
                    {stillProcessing && !error ? <LoadingDots /> : null}
                  </span>
                </span>
                <span className="text-white text-2xl font-bold tabular-nums inline-flex items-center gap-3">
                  {elapsed.toFixed(1)} s
                  {stillProcessing && !error ? (
                    <span className="loading-spinner-sm shrink-0" aria-hidden="true" />
                  ) : null}
                </span>
              </div>

              <ol className="mt-14 space-y-10">
                {steps.map((step, i) => {
                  const status = statuses[i];
                  const active = status === "loading" || status === "done";
                  const showDots = status === "loading";
                  return (
                    <li key={step.title}>
                      <div className="flex items-center justify-between gap-4">
                        <p
                          className="text-white text-xl font-bold"
                          style={{ opacity: active ? 1 : 0.45 }}
                        >
                          {i + 1}. {step.title}
                        </p>
                        <StepIndicator status={status} />
                      </div>
                      <p
                        className="text-[#FFFAFA] text-[15px] font-light mt-2 ml-6 leading-[25px] pr-10"
                        style={{
                          opacity: status === "pending" ? 0.25 : 1,
                          color: status === "error" ? "#FECACA" : undefined,
                        }}
                      >
                        {detailFor(i, status)}
                        {showDots ? <LoadingDots /> : null}
                      </p>
                    </li>
                  );
                })}
              </ol>

              {error && !alertOpen && (
                <div className="mt-10">
                  <button
                    type="button"
                    onClick={() => setAlertOpen(true)}
                    className="rounded-full bg-gold-soft px-8 py-[15px] text-xl font-bold text-white cursor-pointer hover:opacity-90"
                  >
                    View alert
                  </button>
                </div>
              )}
            </motion.div>
          </div>
        </div>
      </PipelineShell>
      <ProcessAlert
        open={Boolean(error) && alertOpen}
        message={error || ""}
        onRetry={() => router.push("/submit")}
        onClose={() => setAlertOpen(false)}
      />
    </main>
    </RequireAuth>
  );
}
