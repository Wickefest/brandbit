"use client";

/**
 * New submission page.
 * Upload a brand image choose BAD or Prompt Only and start generation.
 */

import { useCallback, useEffect, useRef, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
// Reference: https://motion.dev/docs/react-quick-start
import { AnimatePresence, motion } from "motion/react";
import Navbar from "@/components/Navbar";
import GoldButton from "@/components/GoldButton";
import BrandPhotoCard from "@/components/BrandPhotoCard";
import ModeSelect, { type PipelineMode } from "@/components/ModeSelect";
import PipelineShell from "@/components/PipelineShell";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import {
  GENERATION_MAX,
  getGenerationStatus,
} from "@/lib/evaluation";

type FileMeta = {
  name: string;
  type: string;
  sizeLabel: string;
  pixels: string;
};

function formatSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return mb < 1 ? `${(mb * 1024).toFixed(0)} KB` : `${mb.toFixed(2)} MB`;
}

export default function SubmitPage() {
  const router = useRouter();
  const { user, isAdmin } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload preview and file metadata
  const [preview, setPreview] = useState<string | null>(null);
  const [meta, setMeta] = useState<FileMeta | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Pipeline mode and generation quota
  const [mode, setMode] = useState<PipelineMode>("prompt");
  const [genLeft, setGenLeft] = useState<number | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Load remaining generations for non-admin accounts
  useEffect(() => {
    if (!user?.id || isAdmin) {
      setGenLeft(null);
      return;
    }
    let cancelled = false;
    void getGenerationStatus(user.id).then((status) => {
      if (!cancelled) setGenLeft(status.remaining);
    });
    return () => {
      cancelled = true;
    };
  }, [user?.id, isAdmin]);

  // Read the image into a preview and stash it for the process page
  const handleFile = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      setPreview(result);
      sessionStorage.setItem("bb_image_b64", result);
      sessionStorage.setItem("bb_image_name", file.name);
      sessionStorage.setItem("bb_image_type", file.type);

      const probe = new Image();
      probe.onload = () => {
        setMeta({
          name: file.name,
          type: file.type || "image",
          sizeLabel: formatSize(file.size),
          pixels: `${probe.naturalWidth} x ${probe.naturalHeight}`,
        });
      };
      probe.src = result;
    };
    reader.readAsDataURL(file);
  }, []);

  // Handle drag and drop onto the upload card
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  // Persist BAD vs Prompt Only choice
  const onModeChange = (next: PipelineMode) => {
    setMode(next);
    sessionStorage.setItem("bb_pipeline_mode", next);
  };

  // Check quota then move to the process page
  const onStart = async () => {
    if (!preview || starting) return;
    setStarting(true);
    setGenError(null);
    try {
      if (user?.id && !isAdmin) {
        const status = await getGenerationStatus(user.id);
        setGenLeft(status.remaining);
        if (status.remaining <= 0) {
          setGenError(
            `This account has used all ${GENERATION_MAX} generations.`
          );
          return;
        }
      }
      sessionStorage.setItem("bb_pipeline_mode", mode);
      sessionStorage.removeItem("bb_process_inflight");
      sessionStorage.removeItem("bb_rating_mode");
      router.push("/process");
    } finally {
      setStarting(false);
    }
  };

  const blocked = !isAdmin && genLeft === 0;

  return (
    <RequireAuth>
    <main id="main-content" className="min-h-screen lg:h-screen lg:overflow-hidden bg-ink flex flex-col">
      <Navbar />

      <PipelineShell className="lg:overflow-hidden">
        {/* Main content */}
        <div className="flex-1 flex items-start min-h-0 pt-2">
          <div className="w-fit max-w-full mx-auto flex flex-col lg:flex-row lg:items-end gap-8 lg:gap-24">
            <div className="flex flex-col items-start">
              {/* Pipeline mode selector */}
              <div className="mb-4">
                <ModeSelect value={mode} onChange={onModeChange} />
              </div>

              {/* Hidden file input for the upload card */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                tabIndex={-1}
                aria-hidden="true"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />

              {/* Upload / drag and drop card */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                aria-label={
                  preview
                    ? "Replace brand photo. Drag and drop or press Enter to choose a file."
                    : "Upload brand photo. Drag and drop or press Enter to choose a file."
                }
                className={`text-left cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold ${isDragging ? "opacity-80" : ""}`}
              >
                <BrandPhotoCard
                  innerClassName={
                    preview
                      ? ""
                      : "flex flex-col items-center justify-center px-8"
                  }
                >
                  {preview ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={preview}
                      alt="Brand photo"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <>
                      <div className="size-[120px] overflow-clip shrink-0">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src="/assets/icons/scan-box.svg"
                          alt=""
                          className="size-full"
                        />
                      </div>
                      <p className="text-black text-[32px] font-bold mt-6 text-center leading-tight">
                        Drag &amp; Drop Brand Photo
                      </p>
                      <p className="text-black text-xl mt-4 text-center leading-9 max-w-[376px]">
                        Please provide a proper brand photo.
                        <br />
                        Make sure it is the correct photo for parsing.
                      </p>
                    </>
                  )}
                </BrandPhotoCard>
              </button>
            </div>

            <AnimatePresence mode="popLayout">
              <motion.div
                key="submit-side"
                initial={{ opacity: 1 }}
                exit={{ opacity: 0, x: 40 }}
                transition={{ duration: 0.25 }}
                className="w-full sm:w-[470px] flex flex-col items-center shrink-0"
              >
                <div className="w-full bg-[#140E02] rounded-[10px] p-[12px]">
                  <div className="relative bg-blush rounded-[10px] h-[241px] px-8 overflow-hidden">
                    {meta ? (
                      <>
                        <div className="pt-8 text-black">
                          <Row label="File Name" value={meta.name} />
                          <Row label="Mime Type" value={meta.type} />
                          <Row label="Size" value={meta.sizeLabel} />
                          <Row label="Pixels" value={meta.pixels} />
                        </div>
                        <p
                          className="absolute left-0 right-0 bottom-2 text-[15px] font-bold text-center text-black"
                          aria-live="polite"
                        >
                          STATUS: <span className="text-ready">READY</span>
                        </p>
                      </>
                    ) : (
                      <div className="h-full flex items-center justify-center">
                        <p className="text-center text-[32px] font-bold italic text-black/50">
                          No Image Uploaded Yet.
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {!isAdmin && genLeft != null ? (
                  <p className="text-white/55 text-[13px] font-light mt-4 mb-0">
                    Generations left: {genLeft}/{GENERATION_MAX}
                  </p>
                ) : null}
                {genError ? (
                  <p className="text-red-300 text-sm mt-3 mb-0">{genError}</p>
                ) : null}

                <div className={`flex justify-center ${isAdmin || genLeft == null ? "mt-[115px]" : "mt-10"}`}>
                  <GoldButton
                    onClick={() => void onStart()}
                    disabled={!preview || blocked || starting}
                  >
                    {starting ? "Checking…" : "Begin Exploration"}
                  </GoldButton>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </PipelineShell>
    </main>
    </RequireAuth>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 text-xl font-bold leading-[25px] mb-2">
      <span>{label}</span>
      <span className="text-[15px] text-right break-all">{value}</span>
    </div>
  );
}
