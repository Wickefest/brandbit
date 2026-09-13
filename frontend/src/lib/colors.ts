/**
 * Colour swatch helpers.
 * Turn BAD colour names into display swatches with a temperature fallback.
 */

export type Swatch = {
  hex: string;
  label: string;
};

const TEMP_FALLBACK: Record<string, string[]> = {
  warm: ["#C9A05A", "#EA3737", "#FFFDFD", "#D9D9D9", "#8B3A3A"],
  cool: ["#7A9BB8", "#2F5D6A", "#FFFDFD", "#D9D9D9", "#3B1010"],
  neutral: ["#D9D9D9", "#EA3737", "#FFFDFD", "#C9A05A", "#6B6B6B"],
};

/** Common fashion / product colour names → approx hex (not exhaustive). */
const NAME_HEX: Record<string, string> = {
  black: "#1A1A1A",
  white: "#FFFDFD",
  cream: "#F5F0E6",
  ivory: "#FFFFF0",
  beige: "#F5F5DC",
  taupe: "#8B7D6B",
  grey: "#9CA3AF",
  gray: "#9CA3AF",
  charcoal: "#36454F",
  silver: "#C0C0C0",
  gold: "#C9A05A",
  golden: "#C9A05A",
  ochre: "#CC7722",
  mustard: "#E1AD01",
  amber: "#FFBF00",
  bronze: "#CD7F32",
  copper: "#B87333",
  red: "#EA3737",
  crimson: "#DC143C",
  burgundy: "#800020",
  maroon: "#8B3A3A",
  wine: "#722F37",
  coral: "#FF7F50",
  pink: "#FFC0CB",
  rose: "#FF007F",
  blush: "#DE5D83",
  orange: "#FF8C00",
  terracotta: "#E2725B",
  rust: "#B7410E",
  yellow: "#F5D76E",
  lemon: "#FFF44F",
  green: "#2E8B57",
  olive: "#808000",
  sage: "#9CAF88",
  mint: "#98FF98",
  teal: "#008080",
  turquoise: "#40E0D0",
  cyan: "#00FFFF",
  blue: "#3B6EA5",
  navy: "#001F3F",
  indigo: "#4B0082",
  cobalt: "#0047AB",
  sky: "#87CEEB",
  purple: "#6B5B95",
  violet: "#8F00FF",
  lavender: "#E6E6FA",
  lilac: "#C8A2C8",
  brown: "#8B4513",
  chocolate: "#7B3F00",
  espresso: "#3C1414",
  khaki: "#C3B091",
  sand: "#C2B280",
  linen: "#FAF0E6",
  pearl: "#F8F6F0",
  champagne: "#F7E7CE",
};

const HEX_RE = /#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b/;

function expandHex(hex: string): string {
  const h = hex.replace("#", "").toUpperCase();
  if (h.length === 3) {
    return `#${h[0]}${h[0]}${h[1]}${h[1]}${h[2]}${h[2]}`;
  }
  return `#${h}`;
}

function hexFromName(raw: string): string | null {
  const cleaned = raw
    .toLowerCase()
    .replace(/[#].*$/, "")
    .replace(/[^a-z\s-]/g, " ")
    .trim();
  if (!cleaned) return null;

  if (NAME_HEX[cleaned]) return NAME_HEX[cleaned];

  const tokens = cleaned.split(/[\s-]+/).filter(Boolean);
  for (let i = tokens.length - 1; i >= 0; i--) {
    const t = tokens[i];
    if (NAME_HEX[t]) return NAME_HEX[t];
  }
  // multi-word keys like "golden ochre"
  for (const [key, hex] of Object.entries(NAME_HEX)) {
    if (cleaned.includes(key)) return hex;
  }
  return null;
}

/** Parse one colour string into a swatch (label + hex when resolvable). */
export function parseColourEntry(entry: string): Swatch | null {
  const label = entry.trim();
  if (!label) return null;

  const hexMatch = label.match(HEX_RE);
  if (hexMatch) {
    return { hex: expandHex(hexMatch[0]), label };
  }

  const mapped = hexFromName(label);
  if (mapped) return { hex: mapped, label };

  return null;
}

/**
 * Build swatches from BAD colours (variable length 1–10).
 * Falls back to temperature palette when nothing resolves.
 */
export function resolvePalette(
  colours: string[] | undefined | null,
  colorTemperature?: string
): Swatch[] {
  const fromDesc: Swatch[] = [];
  for (const c of colours || []) {
    const swatch = parseColourEntry(c);
    if (swatch) fromDesc.push(swatch);
  }

  if (fromDesc.length > 0) {
    // Dedupe by hex, keep order, cap at 10
    const seen = new Set<string>();
    const unique: Swatch[] = [];
    for (const s of fromDesc) {
      const key = s.hex.toUpperCase();
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(s);
      if (unique.length >= 10) break;
    }
    return unique;
  }

  const temp = (colorTemperature || "neutral").toLowerCase();
  const fallback =
    TEMP_FALLBACK[temp] || TEMP_FALLBACK.neutral;
  return fallback.map((hex) => ({ hex, label: hex }));
}
