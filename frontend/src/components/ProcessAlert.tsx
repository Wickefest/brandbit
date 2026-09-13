"use client";

/**
 * Process status alert.
 * Short toast style messages during generation.
 */

import { useEffect } from "react";

export function processErrorCopy(raw: string): { title: string; body: string } {
  const text = (raw || "").trim() || "Something went wrong while generating.";
  const lower = text.toLowerCase();

  if (lower.includes("musicgen") || lower.includes("audio is required")) {
    return {
      title: "Music could not be generated",
      body: "A finished run needs a MusicGen track. Check that the backend is running and the Replicate token is set, then try again.",
    };
  }
  if (lower.includes("cannot reach") || lower.includes("backend")) {
    return {
      title: "Backend unavailable",
      body: "Brandbit could not reach the generation server. Start the backend, then try again.",
    };
  }
  if (lower.includes("already in progress")) {
    return {
      title: "Already in progress",
      body: "A generation for this image is already running. Wait for it to finish before starting another.",
    };
  }
  return {
    title: "Process interrupted",
    body: text,
  };
}

export default function ProcessAlert({
  open,
  message,
  onRetry,
  onClose,
}: {
  open: boolean;
  message: string;
  onRetry: () => void;
  onClose: () => void;
}) {
  const { title, body } = processErrorCopy(message);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="process-alert-title"
      aria-describedby="process-alert-body"
    >
      <button
        type="button"
        className="absolute inset-0 bg-ink-overlay/70 backdrop-blur-[6px] cursor-default"
        aria-label="Dismiss alert"
        onClick={onClose}
      />
      <div className="relative w-full max-w-[420px] rounded-[28px] bg-nav px-8 py-9 text-black shadow-[0_24px_60px_rgba(0,0,0,0.4)]">
        <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-maroon/70">
          Brandbit
        </p>
        <h2 id="process-alert-title" className="text-[28px] font-bold leading-tight mt-2">
          {title}
        </h2>
        <p
          id="process-alert-body"
          className="mt-3 text-sm font-light leading-6 opacity-80"
        >
          {body}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-8 w-full rounded-full bg-gold-soft px-5 py-[15px] text-xl font-bold text-white cursor-pointer hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-maroon"
        >
          Try again
        </button>
        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full text-sm font-light opacity-70 cursor-pointer hover:opacity-100"
        >
          Close
        </button>
      </div>
    </div>
  );
}
