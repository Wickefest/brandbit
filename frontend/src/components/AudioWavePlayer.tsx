"use client";

/**
 * Audio player with waveform UI.
 * Plays the MusicGen sample returned by the backend.
 */

import { useEffect, useRef, useState } from "react";

type Props = {
  src?: string | null;
  /** Hex colours from visual analysis palette */
  colors?: string[];
  className?: string;
};

const FALLBACK_COLORS = ["#C9A05A", "#EA3737", "#8B3A3A", "#D9D9D9", "#3B1010"];
const BAR_COUNT = 48;
/** How quickly bars chase the audio (lower = silkier). */
const LERP = 0.14;
/** Blend each bar with neighbours for a flowing surface. */
const SPATIAL = 0.38;

function pickColors(colors: string[] | undefined, n: number): string[] {
  const base = (colors || []).filter(Boolean);
  const palette = base.length > 0 ? base : FALLBACK_COLORS;
  if (palette.length === 1) return Array.from({ length: n }, () => palette[0]);

  // Smooth gradient across the strip by interpolating palette stops
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const t = (i / Math.max(1, n - 1)) * (palette.length - 1);
    const i0 = Math.floor(t);
    const i1 = Math.min(palette.length - 1, i0 + 1);
    const f = t - i0;
    out.push(mixHex(palette[i0], palette[i1], f));
  }
  return out;
}

function mixHex(a: string, b: string, t: number): string {
  const pa = parseHex(a);
  const pb = parseHex(b);
  if (!pa || !pb) return a;
  const m = (x: number, y: number) => Math.round(x + (y - x) * t);
  return `#${[m(pa[0], pb[0]), m(pa[1], pb[1]), m(pa[2], pb[2])]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

function parseHex(hex: string): [number, number, number] | null {
  const h = hex.replace("#", "").trim();
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  if (full.length !== 6) return null;
  const n = Number.parseInt(full, 16);
  if (Number.isNaN(n)) return null;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function spatialSmooth(values: number[], amount: number): number[] {
  const out = new Array(values.length);
  for (let i = 0; i < values.length; i++) {
    const l = values[i - 1] ?? values[i];
    const r = values[i + 1] ?? values[i];
    const ll = values[i - 2] ?? l;
    const rr = values[i + 2] ?? r;
    const soft = (ll + l * 2 + values[i] * 3 + r * 2 + rr) / 9;
    out[i] = values[i] * (1 - amount) + soft * amount;
  }
  return out;
}

/** Play/pause + flowing frequency visualizer tinted with analysis colours. */
export default function AudioWavePlayer({
  src,
  colors,
  className = "",
}: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Reference: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const levelsRef = useRef<number[]>(
    Array.from({ length: BAR_COUNT }, () => 0.18)
  );
  const targetsRef = useRef<number[]>(
    Array.from({ length: BAR_COUNT }, () => 0.18)
  );
  const playingRef = useRef(false);
  const colorsRef = useRef(pickColors(colors, BAR_COUNT));
  const phaseRef = useRef(0);

  // Playback UI state
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    colorsRef.current = pickColors(colors, BAR_COUNT);
  }, [colors]);

  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  useEffect(() => {
    setPlaying(false);
    playingRef.current = false;
    setReady(false);
    setError(src ? null : "No audio sample");
    levelsRef.current = Array.from({ length: BAR_COUNT }, () => 0.18);
    targetsRef.current = Array.from({ length: BAR_COUNT }, () => 0.18);

    if (!src) return;

    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audio.preload = "auto";
    audio.src = src;
    audioRef.current = audio;

    const onCanPlay = () => setReady(true);
    const onEnded = () => {
      setPlaying(false);
      playingRef.current = false;
    };
    const onError = () => {
      setError("Could not load audio");
      setReady(false);
    };

    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);

    return () => {
      audio.pause();
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      audioRef.current = null;
      sourceRef.current?.disconnect();
      sourceRef.current = null;
      analyserRef.current?.disconnect();
      analyserRef.current = null;
      void ctxRef.current?.close();
      ctxRef.current = null;
    };
  }, [src]);

  // Continuous draw loop — canvas + lerp = fluid motion (no React churn)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const draw = (time: number) => {
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cssW = canvas.clientWidth || 320;
      const cssH = canvas.clientHeight || 110;
      const w = Math.max(1, Math.floor(cssW * dpr));
      const h = Math.max(1, Math.floor(cssH * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      phaseRef.current = time * 0.001;
      const phase = phaseRef.current;

      // Pull live frequency targets when playing
      const analyser = analyserRef.current;
      if (playingRef.current && analyser) {
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        const step = Math.max(1, Math.floor(data.length / BAR_COUNT));
        const raw: number[] = [];
        for (let i = 0; i < BAR_COUNT; i++) {
          // Left → bass/mids, right → highs (weaker on ambient MusicGen — expected)
          const srcIdx = Math.min(
            data.length - step,
            Math.floor(Math.pow(i / BAR_COUNT, 0.85) * (data.length - step))
          );
          let sum = 0;
          for (let j = 0; j < step; j++) sum += data[srcIdx + j] || 0;
          const avg = sum / step / 255;
          const wave = 0.04 * Math.sin(phase * 2.2 + i * 0.28);
          const shaped = Math.min(1, Math.pow(avg, 0.72) * 1.25 + wave);
          raw.push(0.1 + shaped * 0.9);
        }
        targetsRef.current = spatialSmooth(raw, SPATIAL);
      } else {
        // Idle breath — soft flowing undulation
        const idle: number[] = [];
        for (let i = 0; i < BAR_COUNT; i++) {
          const t = i / BAR_COUNT;
          const v =
            0.16 +
            0.1 * Math.sin(phase * 1.4 + t * Math.PI * 2.2) +
            0.06 * Math.sin(phase * 2.1 + t * Math.PI * 4.5 + 1.2);
          idle.push(v);
        }
        targetsRef.current = spatialSmooth(idle, 0.45);
      }

      // Exponential chase toward targets
      const levels = levelsRef.current;
      const targets = targetsRef.current;
      for (let i = 0; i < BAR_COUNT; i++) {
        levels[i] += (targets[i] - levels[i]) * LERP;
      }
      // Extra spatial pass on displayed levels for silk
      const display = spatialSmooth(levels, 0.25);

      ctx.clearRect(0, 0, w, h);

      const gap = 2.2 * dpr;
      const barW = (w - gap * (BAR_COUNT - 1)) / BAR_COUNT;
      const mid = h * 0.55;
      const palette = colorsRef.current;
      const live = playingRef.current;

      for (let i = 0; i < BAR_COUNT; i++) {
        const level = display[i];
        const x = i * (barW + gap);
        const amp = level * h * 0.92;
        const top = mid - amp * 0.62;
        const bot = mid + amp * 0.38;
        const bh = Math.max(barW * 0.8, bot - top);
        const radius = Math.min(barW / 2, 6 * dpr);

        const color = palette[i % palette.length];
        const grad = ctx.createLinearGradient(x, top, x, bot);
        grad.addColorStop(0, withAlpha(color, live ? 0.95 : 0.4));
        grad.addColorStop(0.55, withAlpha(color, live ? 0.75 : 0.28));
        grad.addColorStop(1, withAlpha(color, live ? 0.35 : 0.12));

        ctx.fillStyle = grad;
        if (live) {
          ctx.shadowColor = withAlpha(color, 0.35);
          ctx.shadowBlur = 10 * dpr;
        } else {
          ctx.shadowBlur = 0;
        }
        roundRect(ctx, x, top, barW, bh, radius);
        ctx.fill();
      }

      // Soft flowing ribbon across peaks
      ctx.shadowBlur = 0;
      ctx.beginPath();
      for (let i = 0; i < BAR_COUNT; i++) {
        const x = i * (barW + gap) + barW / 2;
        const amp = display[i] * h * 0.92;
        const y = mid - amp * 0.62;
        if (i === 0) ctx.moveTo(x, y);
        else {
          const px = (i - 1) * (barW + gap) + barW / 2;
          const pAmp = display[i - 1] * h * 0.92;
          const py = mid - pAmp * 0.62;
          const cpx = (px + x) / 2;
          ctx.quadraticCurveTo(px, py, cpx, (py + y) / 2);
        }
      }
      // finish last segment to final peak
      {
        const i = BAR_COUNT - 1;
        const x = i * (barW + gap) + barW / 2;
        const y = mid - display[i] * h * 0.92 * 0.62;
        ctx.lineTo(x, y);
      }
      ctx.strokeStyle = withAlpha("#ffffff", live ? 0.22 : 0.1);
      ctx.lineWidth = 1.25 * dpr;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, []);

  const ensureGraph = async () => {
    const audio = audioRef.current;
    if (!audio) return null;

    const AC =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    if (!ctxRef.current) {
      ctxRef.current = new AC();
    }
    const ctx = ctxRef.current;
    if (ctx.state === "suspended") await ctx.resume();

    if (!analyserRef.current) {
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.86;
      analyserRef.current = analyser;
    }

    if (!sourceRef.current) {
      sourceRef.current = ctx.createMediaElementSource(audio);
      sourceRef.current.connect(analyserRef.current);
      analyserRef.current.connect(ctx.destination);
    }

    return audio;
  };

  const toggle = async () => {
    if (!src || !ready || error) return;
    try {
      const audio = await ensureGraph();
      if (!audio) return;
      if (playing) {
        audio.pause();
        setPlaying(false);
        playingRef.current = false;
      } else {
        await audio.play();
        setPlaying(true);
        playingRef.current = true;
      }
    } catch {
      setError("Playback failed");
      setPlaying(false);
      playingRef.current = false;
    }
  };

  return (
    <div
      className={`rounded-[20px] px-4 py-4 flex flex-col gap-3 min-h-[150px] ${className}`}
      style={{
        background:
          "linear-gradient(180deg, rgba(0,0,0,0.18) 0%, rgba(0,0,0,0.08) 100%)",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.12)",
      }}
    >
      <div className="flex items-center gap-3 flex-1 min-h-[110px]">
        <button
          type="button"
          onClick={() => void toggle()}
          disabled={!src || !ready || Boolean(error)}
          className="shrink-0 size-11 rounded-full bg-ink text-gold flex items-center justify-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-0"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              <rect x="3" y="2" width="3.5" height="12" rx="1" />
              <rect x="9.5" y="2" width="3.5" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              <path d="M4 2.5v11l10-5.5L4 2.5z" />
            </svg>
          )}
        </button>

        <canvas
          ref={canvasRef}
          className="flex-1 h-[110px] w-full min-w-0"
          aria-hidden
        />
      </div>

      {!src && (
        <p className="text-[12px] text-black/50 font-light">No audio sample for this run</p>
      )}
      {error && src && (
        <p className="text-[12px] text-black/50 font-light">{error}</p>
      )}
      {src && !ready && !error && (
        <p className="text-[12px] text-black/50 font-light">Loading audio…</p>
      )}
      {src && ready && !error && (
        <p className="text-[11px] text-black/45 font-light">
          {playing ? "Visualizer flowing · tap pause to stop" : "Tap play for visualizer mode"}
        </p>
      )}
    </div>
  );
}

function withAlpha(hex: string, alpha: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}
