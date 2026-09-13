# Brandbit Backend

Multimodal orchestration for cross-sensory brand concept generation.

## Testing

Unit tests: `src/test/` (pytest). From `backend/`:

```bash
uv sync --group dev
uv run pytest
```

App-related helpers under `scripts/`: catalog rebuild and live smoke. Config is in `pyproject.toml` (`[tool.pytest.ini_options]`).

## Pipeline phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | Done | Linear pipeline: vision → profile → fragrance + music text → rationale → congruence |
| 2 | Done | Free-vocabulary sensory profile (orchestrator contract) |
| 3 | Done | Pyrfume RAG fragrance generator |
| 4 | Done | MusicGen audio synthesis |
| 5 | Done | Congruence judge + capped specialist regen loop |
| 6 | **Current** | Refinement API + CLIP proxies (`CLIP_BACKEND=local`) |

## Model map (production)

| Stage | Model | Backend |
|-------|--------|---------|
| Vision | Qwen3-VL-8B-Instruct | Replicate |
| Descriptor (BAD) | GPT-4o | Replicate |
| Fragrance + music assistants | Kimi | Moonshot API |
| Congruence judge | DeepSeek-V3 | Replicate |
| Audio | MusicGen | Replicate / remote / local |

Judge is intentionally a different model from the specialists to reduce self-grading bias.

Scoring uses a **strict rubric** (1–5 per modality; pass ≥ 4) plus deterministic rule
pre-checks for obvious energy/tempo and intensity clashes. Critical rule hits override
a lenient judge pass.

After specialists run, DeepSeek judges congruence. Failing fragrance and/or music branches
are regenerated with judge feedback (default max 3 regens via `CONGRUENCE_REGEN_MAX_RETRIES`).
MusicGen audio is synthesized only after the loop finishes.

## Refinement (`POST /api/refine`)

Natural-language feedback updates the modality-neutral BAD, then re-runs the affected
specialist(s) (`target_modality` fragrance/music when clear; otherwise both), the congruence
loop, MusicGen, and rationale. History is appended on the same
`execution_id` under `refinement_history`. Responses include `congruence_accepted` (mirrors
`congruence_report.accepted`) so clients can tell best-effort soft-fails from full passes.

```bash
curl -X POST http://localhost:8000/api/refine \
  -F execution_id=Kopi_Kenangan_001 \
  -F feedback="make the mood warmer and more intimate"
```

Ambiguous feedback returns `{ "success": false, "clarification_request": "..." }` without
mutating the stored run.

## CLIP proxies (image ↔ text alignment)

CLIP runs **once at the end** of the specialist loop — supportive evaluation only, not a
regen gate. Scores are stored on `congruence_report.automated_proxies`:

- `clip_score_image_fragrance_text` — image vs fragrance caption
- `clip_score_image_music_text` — image vs music caption

**Replicate (recommended — same token as Qwen/GPT-4o/DeepSeek/MusicGen):**

```env
CLIP_BACKEND=replicate          # or auto (uses Replicate when token is set)
CLIP_REPLICATE_MODEL=openai/clip
REPLICATE_API_TOKEN=r8_...      # or MUSICGEN_API_KEY
```

**Local (optional, no API cost after model download):**

```bash
uv sync --group clip
```

```env
CLIP_BACKEND=local
CLIP_MODEL_NAME=openai/clip-vit-base-patch32
```

Scores use CLIPScore-style scaling: `2.5 * max(cosine_similarity, 0)`.
ImageBind (image↔audio) remains future work (`imagebind_score_image_audio` stays null).

## Phase 2 — Brand Sensory Profile

The orchestrator outputs a **modality-neutral** `BrandAestheticDescriptor` (alias: `BrandSensoryProfile`):

- **Identity:** `brand_item` (product/object from vision `primary_subject`, or user override)
- **Free-form:** `mood`, `texture`, `visual_style`, `sensory_metaphors`, `narrative`
- **Structured enums:** `energy`, `color_temperature`

`scent_family` and `music_direction` are **not** on the BAD — fragrance and music specialists invent those independently so congruence is not circular.

Downstream services receive the full profile via `to_generation_context()`.

## Phase 3 — Pyrfume RAG Fragrance

Fragrance generation is grounded in real perfumery materials from [Pyrfume](https://pyrfume.org/) archives:

- **GoodScents** — commercial odor descriptors
- **Leffingwell** — perfumery raw material labels
- **IFRA 2019** — standardized odor descriptors

Flow: sensory profile → LSA k-NN retrieval over the Pyrfume catalog
(TF-IDF → TruncatedSVD → cosine neighbors) → LLM composes top/heart/base using
**only retrieved ingredient names**.

Output includes `grounded_notes` and `pyrfume_sources` on `FragranceConcept`.

### Catalog cache (shipped)

Fragrance retrieval loads `backend/data/pyrfume_catalog.json` first (no Pyrfume
download on startup when that file is present). Commit/upload that JSON with the
deploy.

Optional regenerate (downloads Pyrfume datasets, overwrites the cache):

```bash
cd backend
uv run python scripts/build_pyrfume_catalog.py
```

## Phase 4 — MusicGen Audio

After the text `MusicDirection` brief is generated, MusicGen synthesizes a brand ambient WAV.

**Backends** (`MUSICGEN_BACKEND`):

| Backend | When to use |
|---------|-------------|
| `auto` | Remote URL if set, else Replicate if token set, else skip |
| `replicate` | Easiest — no GPU needed ([Replicate MusicGen](https://replicate.com/meta/musicgen)) |
| `remote` | Your own GPU worker (Noisana / RunPod) |
| `local` | Local CUDA — `uv sync --group audio` |
| `off` | Text brief only |

Output: `music_direction.audio_sample_ref` → `/api/audio/{execution_id}`

### Replicate (recommended)

```env
MUSICGEN_BACKEND=replicate
MUSICGEN_API_KEY=r8_...          # or REPLICATE_API_TOKEN
MUSICGEN_DURATION_SECONDS=15
```

### GPU worker (Noisana / RunPod)

On the GPU machine:

```bash
uv sync --group audio
uv run uvicorn scripts.musicgen_worker:app --host 0.0.0.0 --port 8080
```

On the main backend:

```env
MUSICGEN_BACKEND=remote
MUSICGEN_REMOTE_URL=https://your-gpu-host/synthesize
```

## Run locally

```bash
cd backend
uv run brandbit test_image.jpg
# or:
uv run python run_pipeline.py path/to/brand_image.jpg [brand_item]
```

Smoke-test one stage at a time (no full pipeline):

```bash
# visual analysis only
uv run python -m src.services.visual_analysis test_image.jpg

# live image → Qwen vision → BAD
uv run python -m src.services.descriptor_generation --image test_image.jpg
uv run python -m src.services.descriptor_generation --image test_image.jpg "bottled water"

# optional live pipeline smoke
uv run python scripts/smoke_live.py
```

Or stop the full CLI early: `uv run brandbit test_image.jpg --until visual|bad`.

## Outputs layout

Runtime artefacts live at the **repository root** under `eval/` (sibling of `backend/` and `frontend/`). Paths below are from the repo root.

| Path | Contents |
|------|----------|
| `eval/result/{execution_id}.json` | Full pipeline execution record |
| `eval/outputs/images/{execution_id}.*` | Persisted input image (API upload / refine CLIP) |
| `eval/outputs/fragrance/{execution_id}.json` | Fragrance specialist only |
| `eval/outputs/music/{execution_id}.json` | Music direction text only |
| `eval/outputs/music/{execution_id}.wav` | MusicGen audio |

Requires a Replicate token (`MUSICGEN_API_KEY` or `REPLICATE_API_TOKEN`) for Qwen
vision, GPT-4o descriptor, and DeepSeek judge. Specialist fragrance/music text uses
`KIMI_API_KEY`.

```bash
uv run uvicorn src.main:app --reload
```

## Environment

See `.env` for `KIMI_API_KEY` (specialists), `QWEN_REPLICATE_MODEL`,
`GPT4O_REPLICATE_MODEL`, `DEEPSEEK_REPLICATE_MODEL`, and MusicGen settings
(`MUSICGEN_BACKEND`, `MUSICGEN_API_KEY`, `MUSICGEN_REMOTE_URL`).
