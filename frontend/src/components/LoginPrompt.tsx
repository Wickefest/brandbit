"use client";

/**
 * Google sign in modal.
 * Collects research consent then starts OAuth.
 */

import { useEffect, useId, useState } from "react";
import ResearchInformation from "@/components/ResearchInformation";

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.2-2.27H12v4.3h6.46a5.52 5.52 0 0 1-2.4 3.62v3h3.88c2.27-2.09 3.55-5.17 3.55-8.65z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.9l-3.88-3c-1.08.72-2.47 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.09A12 12 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29A7.2 7.2 0 0 1 4.89 12c0-.8.14-1.57.38-2.29V6.62H1.27A12 12 0 0 0 0 12c0 1.94.46 3.77 1.27 5.38l4-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.76 0 3.34.6 4.58 1.79l3.43-3.43C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.69 1.27 6.62l4 3.09C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  );
}

export default function LoginPrompt({
  open,
  nextPath,
  error,
  onClose,
  onContinue,
}: {
  open: boolean;
  nextPath: string;
  error: string | null;
  onClose: () => void;
  onContinue: () => void;
}) {
  const consentId = useId();

  // Consent checkbox and research info overlay
  const [consented, setConsented] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);

  // Close on Escape; reset when the modal closes
  useEffect(() => {
    if (!open) {
      setConsented(false);
      setInfoOpen(false);
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (infoOpen) {
        setInfoOpen(false);
        return;
      }
      onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, infoOpen, onClose]);

  if (!open) return null;

  const goingToSubmit = nextPath.startsWith("/submit");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
    >
      {/* Backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-ink-overlay/70 backdrop-blur-[6px] cursor-default"
        aria-label="Close sign in"
        onClick={() => {
          if (!infoOpen) onClose();
        }}
      />
      {/* Sign-in card */}
      <div className="relative w-full max-w-[420px] rounded-[28px] bg-nav px-8 py-9 text-black shadow-[0_24px_60px_rgba(0,0,0,0.4)]">
        <h2 id="login-title" className="text-[28px] font-bold leading-tight">
          Sign in to continue
        </h2>
        <p className="mt-3 text-sm font-light leading-6 opacity-80">
          {goingToSubmit
            ? "Start Process needs a Google account so Brandbit can keep your session."
            : "Use your Google account to unlock New Submission and Library."}
        </p>

        {/* Research consent */}
        <label
          htmlFor={consentId}
          className="mt-6 flex cursor-pointer items-start gap-3 rounded-2xl border border-black/10 bg-white/55 px-4 py-3.5"
        >
          <input
            id={consentId}
            type="checkbox"
            checked={consented}
            onChange={(event) => setConsented(event.target.checked)}
            className="mt-1 size-4 shrink-0 accent-maroon cursor-pointer"
          />
          <span className="text-sm font-light leading-5 opacity-85">
            I have read the{" "}
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setInfoOpen(true);
              }}
              className="font-bold underline decoration-gold underline-offset-2 cursor-pointer"
            >
              Research Information
            </button>{" "}
            and I consent to take part. Ratings appear without my name in the
            report.
          </span>
        </label>

        {error ? (
          <p className="mt-4 text-sm font-light text-maroon" role="alert">
            {error}
          </p>
        ) : null}

        <button
          type="button"
          onClick={onContinue}
          disabled={!consented}
          aria-disabled={!consented}
          className="mt-7 flex w-full items-center justify-center gap-3 rounded-full bg-white px-5 py-3 text-base font-bold text-black shadow-[0_8px_20px_rgba(0,0,0,0.12)] cursor-pointer hover:bg-white/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-white"
        >
          <GoogleMark />
          Continue with Google
        </button>
        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full text-sm font-light opacity-70 cursor-pointer hover:opacity-100"
        >
          Not now
        </button>
      </div>

      {infoOpen ? (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center px-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="research-info-title"
        >
          <button
            type="button"
            className="absolute inset-0 bg-ink-overlay/50 cursor-default"
            aria-label="Close research information"
            onClick={() => setInfoOpen(false)}
          />
          <div className="relative flex max-h-[85vh] w-full max-w-[560px] flex-col rounded-[28px] bg-nav px-7 py-7 text-black shadow-[0_24px_60px_rgba(0,0,0,0.45)]">
            <div className="min-h-0 flex-1 overflow-y-auto pr-1 text-[13px] font-light leading-5 text-black/85">
              <ResearchInformation />
            </div>
            <button
              type="button"
              onClick={() => setInfoOpen(false)}
              className="mt-5 w-full rounded-full bg-gold-soft px-5 py-3 text-sm font-bold text-white cursor-pointer hover:opacity-90"
            >
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
