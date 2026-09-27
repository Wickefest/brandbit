/**
 * Demo API result fixture.
 * Static sample payload for offline UI checks.
 */

import type { ApiResult } from "./types";

export const DEMO_RESULT: ApiResult = {
  execution_id: "4_001",
  brand_aesthetic_descriptor: {
    brand_item: "batik shirt",
    mood: ["elegant", "confident", "refined", "traditional"],
    energy: "moderate",
    color_temperature: "warm",
    colours: ["golden ochre (#C9A05A)", "deep indigo (#4B0082)", "cream batik (#F5F0E6)"],
    texture: ["woven", "embroidered", "smooth fabric", "structured weave"],
    visual_style: ["three-quarter portrait", "angled pose"],
    sensory_metaphors: ["woven elegance", "golden heritage"],
    narrative:
      "The batik shirt embodies a blend of traditional elegance and modern confidence. Its warm color palette and intricate textures convey a sense of refined sophistication, making it a timeless piece in any wardrobe.",
  },
  fragrance_concept: {
    top_notes: ["carvyl propionate", "ethyl 2-ethoxybenzoate"],
    heart_notes: ["lavandulol", "vanillyl butyl ether", "benzyl eugenol"],
    base_notes: [
      "7,9-cyclohexadecadien-1-one",
      "myristicin",
      "2-methoxy-4-(4-methyl-1,3-dioxolan-2-yl)phenol",
    ],
    dominant_accords: ["warm floral", "spicy", "vanilla"],
    intensity_profile: "moderate",
    emotional_descriptors: ["elegant", "confident", "refined"],
    smell_signature:
      "This fragrance opens with a fresh, warm minty and floral scent, transitioning into a heart of spicy rose and sweet vanilla. The dry-down is a comforting blend of musk and warm spices, reminiscent of a luxurious, traditional spa product with a modern twist.",
    note_guide: [
      {
        smells_like: "mint, warm minty",
        chemical_name: "carvyl propionate",
        ingredient: "carvyl propionate",
      },
      {
        smells_like: "warm-floral",
        chemical_name: "ethyl 2-ethoxybenzoate",
        ingredient: "ethyl 2-ethoxybenzoate",
      },
      {
        smells_like: "rose, citrus",
        chemical_name: "lavandulol",
        ingredient: "lavandulol",
      },
      {
        smells_like: "vanilla, pungent",
        chemical_name: "vanillyl butyl ether",
        ingredient: "vanillyl butyl ether",
      },
      {
        smells_like: "hay, mild",
        chemical_name: "benzyl eugenol",
        ingredient: "benzyl eugenol",
      },
      {
        smells_like: "powdery, musk",
        chemical_name: "7,9-cyclohexadecadien-1-one",
        ingredient: "7,9-cyclohexadecadien-1-one",
      },
      {
        smells_like: "nutmeg",
        chemical_name: "myristicin",
        ingredient: "myristicin",
      },
      {
        smells_like: "vanilla, cocoa",
        chemical_name: "2-methoxy-4-(4-methyl-1,3-dioxolan-2-yl)phenol",
        ingredient: "2-methoxy-4-(4-methyl-1,3-dioxolan-2-yl)phenol",
      },
    ],
    pyrfume_sources: ["goodscents", "ifra_2019", "leffingwell"],
  },
  music_direction: {
    tempo: "moderate",
    bpm: 96,
    timbre: [
      "warm pads",
      "smooth silk strings",
      "resonant woodwinds",
      "delicate bells",
    ],
    instrumentation: ["gamelan metallophones", "suling", "sitar", "oud", "erhu"],
    mood: "refined-sophistication",
    style: "contemporary-traditional",
    music_signature:
      "This is the sound of a batik shirt, a blend of traditional elegance and modern confidence. The intricate textures and warm color palette evoke a sense of refined sophistication. The blend of gamelan metallophones, suling, sitar, oud, and erhu creates a contemporary-traditional style that reflects the structured weave and embroidered patterns of the batik shirt. It should feel elegant and confident, enveloping the listener in the golden heritage of woven elegance.",
    audio_sample_ref: null,
  },
  audio_sample_ref: null,
  rationale:
    "## Visual to Descriptor\n\nThe batik shirt's visual style, which includes a \"three-quarter portrait\" and \"angled pose,\" reflects an elegant and confident stance that aligns with the Brand Aesthetic Descriptor (BAD) field \"mood.\" The warm color temperature and intricate textures like \"woven,\" \"embroidered,\" and \"structured weave\" contribute to the refined and traditional feel, further emphasizing the BAD field \"mood\" and \"texture.\"\n\n## Descriptor to Fragrance\n\nThe mood of \"elegant,\" \"confident,\" and \"refined\" from the BAD field guided the fragrance selection towards a \"warm floral,\" \"spicy,\" and \"vanilla\" dominant accords. The \"moderate\" intensity profile of the fragrance mirrors the BAD field's \"energy,\" ensuring the scent is neither overpowering nor too subtle, reflecting the brand's refined sophistication.\n\n## Descriptor to Music\n\nThe BAD field \"mood\" with its elegant, confident, and refined qualities, along with the \"moderate\" energy, directed the music direction towards a \"moderate\" tempo and a \"refined-sophistication\" mood. The choice of \"warm pads,\" \"smooth silk strings,\" and \"resonant woodwinds\" timbres echo the BAD field's \"warm\" color temperature, creating a harmonious auditory experience that resonates with the batik shirt's traditional elegance and modern confidence.",
  congruence_report: {
    accepted: true,
    regen_count: 0,
    summary:
      "Both the fragrance and music directions are excellent, independent translations of the batik shirt's brand identity, with no major violations.",
    automated_proxies: {
      clip_score_image_fragrance_text: 0.3676,
      clip_score_image_music_text: 0.6833,
      imagebind_score_image_audio: null,
    },
    descriptor_consistency: {
      fragrance_aligns_descriptor: true,
      music_aligns_descriptor: true,
      fragrance_score: 4,
      music_score: 5,
      fragrance_issues: [],
      music_issues: [],
      details:
        "The fragrance concept aligns well with the BAD, matching the mood (elegant, confident, refined), energy (moderate), and color_temperature (warm) with its warm floral, spicy, and vanilla accords. The music direction also fits perfectly, with its moderate tempo, warm timbre, and traditional-contemporary style that reflects the batik shirt's woven elegance and golden heritage.",
    },
    attempts: [
      {
        attempt: 1,
        fragrance_aligns_descriptor: true,
        music_aligns_descriptor: true,
        regenerated: [],
      },
    ],
  },
  refinement_history: [],
  mode: "sensory_profile",
};
