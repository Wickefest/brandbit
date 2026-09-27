/**
 * Results download pack builder.
 * Assembles image audio and JSON into a ZIP for the user.
 */

import { makeThumb } from "@/lib/archive";
import { resolveAudioUrl } from "@/lib/api";
import {
  archiveDisplayName,
  pipelineProcessLabel,
  type ApiResult,
} from "@/lib/types";
import { zipStore, type ZipEntry } from "@/lib/zipStore";

export function packFileStem(result: ApiResult): string {
  const raw = archiveDisplayName(result) || result.execution_id || "brandbit-report";
  return raw.replace(/[<>:"/\\|?*]/g, "_").trim() || "brandbit-report";
}

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function joinList(items?: string[]): string {
  return (items || []).filter(Boolean).join(", ") || "—";
}

function plainText(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/(?<!\w)_(.+?)_(?!\w)/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/__/g, "")
    .replace(/\*\*/g, "");
}

function splitRationale(text: string): Array<{ title?: string; body: string }> {
  const cleaned = plainText(text);
  const chunks = cleaned
    .split(/\n(?=##\s)/)
    .map((c) => c.trim())
    .filter(Boolean);
  if (chunks.length === 0) return [{ body: cleaned }];
  return chunks.map((chunk) => {
    const match = chunk.match(/^##\s+(.+?)\n([\s\S]*)$/);
    if (match) return { title: match[1].trim(), body: match[2].trim() };
    return { body: chunk.replace(/^##\s+/, "").trim() };
  });
}

function formatClip(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "—";
  const pct = Math.round(Math.min(100, Math.max(0, (score / 2.5) * 100)));
  return `${pct}%`;
}

function dlRow(label: string, value: string): string {
  return `<div class="row"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
}

function section(title: string, body: string): string {
  return `<section><h2>${esc(title)}</h2>${body}</section>`;
}

export function buildReportHtml(
  result: ApiResult,
  opts: { hasImage: boolean; hasAudio: boolean }
): string {
  const title = archiveDisplayName(result);
  const desc = result.brand_aesthetic_descriptor;
  const frag = result.fragrance_concept;
  const music = result.music_direction;
  const congruence = result.congruence_report || {};
  const mode = pipelineProcessLabel(result.mode);
  const brand = desc.brand_item || "Brand exploration";

  const imageBlock = opts.hasImage
    ? `<figure><img src="brand.jpg" alt="${esc(brand)}" /><figcaption>${esc(brand)}</figcaption></figure>`
    : "";

  const audioBlock = opts.hasAudio
    ? `<p class="hint">Play the companion file in this folder, or use the player below.</p>
       <audio controls src="audio.wav">Audio: audio.wav</audio>`
    : `<p class="hint">No audio sample was available for this pack.</p>`;

  const rationale = splitRationale(result.rationale || "")
    .map((block) => {
      const heading = block.title ? `<h3>${esc(block.title)}</h3>` : "";
      return `${heading}<p>${esc(block.body)}</p>`;
    })
    .join("");

  const guide = (frag.note_guide || [])
    .map(
      (n) =>
        `<tr><td>${esc(n.chemical_name || n.ingredient)}</td><td>${esc(n.ingredient)}</td><td>${esc(n.smells_like)}</td></tr>`
    )
    .join("");

  const guideTable = guide
    ? `<table><thead><tr><th>Chemical</th><th>Ingredient</th><th>Smells like</th></tr></thead><tbody>${guide}</tbody></table>`
    : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(title)}</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f6f1e8;
      color: #1a1408;
      font: 16px/1.55 Georgia, "Times New Roman", serif;
    }
    main { max-width: 820px; margin: 0 auto; padding: 48px 28px 72px; }
    header { border-bottom: 2px solid #c9a05a; padding-bottom: 20px; margin-bottom: 28px; }
    .kicker { letter-spacing: 0.16em; text-transform: uppercase; font-size: 11px; color: #8a6a22; font-family: system-ui, sans-serif; }
    h1 { font-size: 32px; line-height: 1.15; margin: 8px 0 6px; }
    .meta { color: #5c5140; font-size: 14px; }
    h2 { font-size: 20px; margin: 36px 0 12px; color: #3b2a0c; }
    h3 { font-size: 15px; margin: 18px 0 6px; }
    p { margin: 0 0 12px; }
    .row { display: grid; grid-template-columns: 160px 1fr; gap: 8px 16px; margin: 0 0 8px; }
    dt { color: #6b5a3a; font-family: system-ui, sans-serif; font-size: 13px; }
    dd { margin: 0; }
    figure { margin: 0 0 24px; }
    img { width: 100%; max-height: 420px; object-fit: cover; border-radius: 12px; background: #ddd; }
    figcaption { font-size: 13px; color: #6b5a3a; margin-top: 8px; }
    audio { width: 100%; margin-top: 8px; }
    .hint { font-size: 13px; color: #6b5a3a; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0 20px; }
    th, td { text-align: left; border-bottom: 1px solid #e0d4be; padding: 8px 6px; vertical-align: top; }
    th { font-family: system-ui, sans-serif; color: #6b5a3a; font-weight: 600; }
    .print { font-size: 12px; color: #8a6a22; margin-top: 8px; font-family: system-ui, sans-serif; }
    @media print {
      body { background: white; }
      main { padding: 0; }
      audio, .print { display: none; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="kicker">Brandbit report · ${esc(mode)}</p>
      <h1>${esc(title)}</h1>
      <p class="meta">${esc(brand)}</p>
      <p class="print">To save a PDF: open this file, then Print → Save as PDF.</p>
    </header>
    ${imageBlock}
    ${section(
      "Brand aesthetic",
      `<dl>
        ${dlRow("Mood", joinList(desc.mood))}
        ${dlRow("Energy", desc.energy || "—")}
        ${dlRow("Colour temperature", desc.color_temperature || "—")}
        ${dlRow("Colours", joinList(desc.colours))}
        ${dlRow("Texture", joinList(desc.texture))}
        ${dlRow("Visual style", joinList(desc.visual_style))}
        ${dlRow("Sensory metaphors", joinList(desc.sensory_metaphors))}
      </dl>
      <p>${esc(desc.narrative || "—")}</p>`
    )}
    ${section(
      "Fragrance concept",
      `<dl>
        ${dlRow("Top notes", joinList(frag.top_notes))}
        ${dlRow("Heart notes", joinList(frag.heart_notes))}
        ${dlRow("Base notes", joinList(frag.base_notes))}
        ${dlRow("Accords", joinList(frag.dominant_accords))}
        ${dlRow("Intensity", frag.intensity_profile || "—")}
        ${dlRow("Emotion", joinList(frag.emotional_descriptors))}
      </dl>
      <p>${esc(frag.smell_signature || "—")}</p>
      ${guideTable}`
    )}
    ${section(
      "Music direction",
      `<dl>
        ${dlRow("Style", music.style || "—")}
        ${dlRow("Tempo", [music.tempo, music.bpm != null ? `${music.bpm} BPM` : ""].filter(Boolean).join(" · ") || "—")}
        ${dlRow("Mood", music.mood || "—")}
        ${dlRow("Instrumentation", joinList(music.instrumentation))}
        ${dlRow("Timbre", joinList(music.timbre))}
      </dl>
      <p>${esc(music.music_signature || "—")}</p>
      ${audioBlock}`
    )}
    ${section(
      "Congruence",
      `<dl>
        ${dlRow("Status", congruence.accepted ? "Approved" : "Needs review")}
        ${dlRow("Smell align", congruence.descriptor_consistency?.fragrance_score != null ? `${congruence.descriptor_consistency.fragrance_score}/5` : "—")}
        ${dlRow("Music align", congruence.descriptor_consistency?.music_score != null ? `${congruence.descriptor_consistency.music_score}/5` : "—")}
        ${dlRow("CLIP fragrance", formatClip(congruence.automated_proxies?.clip_score_image_fragrance_text))}
        ${dlRow("CLIP music", formatClip(congruence.automated_proxies?.clip_score_image_music_text))}
      </dl>
      <p>${esc(congruence.summary || congruence.descriptor_consistency?.details || "—")}</p>`
    )}
    ${result.rationale ? section("Rationale", rationale) : ""}
  </main>
</body>
</html>
`;
}

function encodeUtf8(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

function dataUrlToBytes(dataUrl: string): Uint8Array | null {
  const match = dataUrl.match(/^data:(.+?);base64,(.+)$/);
  if (!match) return null;
  const binary = atob(match[2]);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function imageBytes(imagePreview: string | null): Promise<Uint8Array | null> {
  if (!imagePreview) return null;
  if (imagePreview.startsWith("data:")) {
    const thumb = await makeThumb(imagePreview, 960);
    if (!thumb) return dataUrlToBytes(imagePreview);
    return dataUrlToBytes(thumb);
  }
  try {
    const res = await fetch(imagePreview);
    if (!res.ok) return null;
    return new Uint8Array(await res.arrayBuffer());
  } catch {
    return null;
  }
}

async function audioBytes(result: ApiResult): Promise<Uint8Array | null> {
  const url = resolveAudioUrl(
    result.music_direction?.audio_sample_ref || result.audio_sample_ref || null
  );
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return new Uint8Array(await res.arrayBuffer());
  } catch {
    return null;
  }
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadReportPack(
  result: ApiResult,
  imagePreview: string | null
): Promise<void> {
  const stem = packFileStem(result);
  const folder = `${stem}/`;
  const [image, audio] = await Promise.all([
    imageBytes(imagePreview),
    audioBytes(result),
  ]);

  const html = buildReportHtml(result, {
    hasImage: Boolean(image),
    hasAudio: Boolean(audio),
  });

  const entries: ZipEntry[] = [
    { name: `${folder}report.html`, data: encodeUtf8(html) },
    {
      name: `${folder}result.json`,
      data: encodeUtf8(JSON.stringify(result, null, 2)),
    },
  ];
  if (image) entries.push({ name: `${folder}brand.jpg`, data: image });
  if (audio) entries.push({ name: `${folder}audio.wav`, data: audio });

  triggerDownload(zipStore(entries), `${stem}.zip`);
}
