"use client";

/**
 * Pipeline mode selector.
 * Choose BAD path or Prompt Only before generation.
 */

import { useEffect, useId, useRef, useState } from "react";
// Reference: https://base-ui.com/react/components/select
import { Select } from "@base-ui/react/select";

export type PipelineMode = "prompt" | "bad";

const OPTIONS: { value: PipelineMode; label: string; hint: string }[] = [
  {
    value: "prompt",
    label: "Prompt-Only",
    hint: "Generate straight from the image",
  },
  {
    value: "bad",
    label: "BAD",
    hint: "Route through Brand Aesthetic Descriptor",
  },
];

const labels: Record<PipelineMode, string> = {
  prompt: "Prompt-Only",
  bad: "BAD",
};

const CLOSE_DELAY_MS = 180;

export default function ModeSelect({
  value,
  onChange,
}: {
  value: PipelineMode;
  onChange: (next: PipelineMode) => void;
}) {
  const labelId = useId();
  const hintId = useId();
  const liveId = useId();
  const [liveMsg, setLiveMsg] = useState("");
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const overTrigger = useRef(false);
  const overPopup = useRef(false);

  const clearCloseTimer = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const openFromTrigger = () => {
    overTrigger.current = true;
    clearCloseTimer();
    setOpen(true);
    setLiveMsg(`Opened. Current mode: ${labels[value]}.`);
  };

  const leaveTrigger = () => {
    overTrigger.current = false;
    clearCloseTimer();
    closeTimer.current = setTimeout(() => {
      if (!overTrigger.current && !overPopup.current) setOpen(false);
    }, CLOSE_DELAY_MS);
  };

  const enterPopup = () => {
    overPopup.current = true;
    clearCloseTimer();
  };

  const leavePopup = () => {
    overPopup.current = false;
    clearCloseTimer();
    closeTimer.current = setTimeout(() => {
      if (!overTrigger.current && !overPopup.current) setOpen(false);
    }, CLOSE_DELAY_MS);
  };

  useEffect(() => () => clearCloseTimer(), []);

  return (
    <div className="mode-select-root inline-flex">
      <p id={labelId} className="sr-only">
        Pipeline mode
      </p>
      <p id={hintId} className="sr-only">
        Hover to open. Click or Enter to apply a mode. Escape cancels.
      </p>
      <p id={liveId} className="sr-only" aria-live="polite" aria-atomic="true">
        {liveMsg}
      </p>

      <Select.Root
        value={value}
        open={open}
        modal={false}
        onOpenChange={(next, details) => {
          clearCloseTimer();

          if (next) {
            if (
              details.reason === "trigger-press" ||
              details.reason === "list-navigation"
            ) {
              setOpen(true);
              setLiveMsg(`Opened. Current mode: ${labels[value]}.`);
            }
            return;
          }

          overTrigger.current = false;
          overPopup.current = false;
          setOpen(false);
          if (details.reason === "escape-key") {
            setLiveMsg("Closed. Selection unchanged.");
          }
        }}
        onValueChange={(next) => {
          if (next !== "prompt" && next !== "bad") return;
          onChange(next);
          setLiveMsg(`Mode applied: ${labels[next]}`);
          overTrigger.current = false;
          overPopup.current = false;
          setOpen(false);
        }}
      >
        <Select.Trigger
          aria-labelledby={labelId}
          aria-describedby={hintId}
          onMouseEnter={openFromTrigger}
          onMouseLeave={leaveTrigger}
          className="mode-select-trigger group inline-flex h-[24px] w-[132px] items-center justify-between rounded-full bg-gold-soft px-3 text-white text-xs font-bold tracking-wide outline-none cursor-pointer focus-visible:ring-2 focus-visible:ring-nav focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
        >
          <Select.Value className="flex-1 text-center">
            {(v) => labels[(v as PipelineMode) || "prompt"]}
          </Select.Value>
          <Select.Icon className="flex shrink-0 items-center">
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              aria-hidden="true"
              className="opacity-90 transition-transform duration-300 ease-out group-data-[popup-open]:rotate-180"
            >
              <path
                d="M2.5 4.5L6 8L9.5 4.5"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Positioner
            className="z-50 outline-none"
            sideOffset={10}
            alignItemWithTrigger={false}
          >
            <Select.Popup
              aria-labelledby={labelId}
              onMouseEnter={enterPopup}
              onMouseLeave={leavePopup}
              className="mode-select-popup min-w-[260px] rounded-2xl border border-gold/35 bg-nav text-black outline-none"
            >
              <p className="px-3 pt-2.5 pb-1 text-[10px] font-light tracking-wide text-black/45">
                Hover option to preview · click to apply
              </p>
              <Select.List className="p-2 pt-1 flex flex-col gap-1">
                {OPTIONS.map((option) => {
                  const isApplied = value === option.value;
                  return (
                    <Select.Item
                      key={option.value}
                      value={option.value}
                      label={`${option.label}. ${option.hint}`}
                      className="mode-select-item relative grid cursor-pointer grid-cols-[1fr_auto] items-start gap-x-3 rounded-xl px-3 py-2.5 outline-none focus-visible:ring-2 focus-visible:ring-gold/60"
                    >
                      <div className="min-w-0">
                        <Select.ItemText className="block text-sm font-bold leading-tight">
                          {option.label}
                        </Select.ItemText>
                        <span className="mt-1 block text-[11px] font-light leading-snug text-black/55">
                          {option.hint}
                        </span>
                        {isApplied && (
                          <span className="mt-1 block text-[10px] font-bold tracking-wide text-gold">
                            Applied
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 col-start-2 min-w-[18px]">
                        <Select.ItemIndicator>
                          <span className="inline-flex size-[18px] items-center justify-center rounded-full bg-gold/20">
                            <svg
                              width="12"
                              height="12"
                              viewBox="0 0 14 14"
                              fill="none"
                              aria-hidden="true"
                            >
                              <path
                                d="M2.5 7.2L5.4 10.1L11.5 3.9"
                                stroke="#C5A059"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </span>
                        </Select.ItemIndicator>
                      </div>
                    </Select.Item>
                  );
                })}
              </Select.List>
            </Select.Popup>
          </Select.Positioner>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
