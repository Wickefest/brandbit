# Brandbit

Next.js · FastAPI · Supabase · Pyrfume · MusicGen

UoL undergraduate Final Year Project submission. Upload a brand image and Brandbit generates a sensory profile, a grounded fragrance concept, and a short music sample, then checks whether those outputs fit together.

## Project overview

Brand teams often jump from a visual identity to scent and sound with little shared language. Brandbit turns one product photo into a modality-neutral brand aesthetic descriptor (BAD), then two specialists invent fragrance and music independently. A separate judge scores congruence and can ask a specialist to try again.

The app keeps a propose–confirm loop: the system drafts, the user can refine in natural language, and ratings / library items are stored when Supabase is configured.

## Key features

- Vision to BAD: Qwen3-VL reads the image; GPT-4o writes a free-vocabulary sensory profile
- Fragrance specialist: Kimi + Pyrfume RAG (real material names only)
- Music specialist: Kimi direction text, then MusicGen audio (Replicate by default)
- Congruence judge: DeepSeek-V3 plus rule checks; capped regen loop
- Refinement API: user feedback updates the BAD and re-runs the affected branch
- Web app: submit, process, results, library, export, and evaluation ratings

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind |
| Backend | FastAPI, Python 3.12, uv |
| Auth / data | Supabase (Auth, Postgres, storage) |
| Schema helper | Prisma (`prisma/`) |
| Models | Qwen3-VL, GPT-4o, Kimi, DeepSeek-V3, MusicGen (Replicate) |

## Repo structure

```
brandbit/
├── frontend/     # Next.js app
├── backend/      # FastAPI pipeline and API
├── prisma/       # schema + Supabase SQL extras
├── eval/         # run logs, notebooks, comparison cases
└── data/         # leftover catalog copy (unused; backend uses backend/data/)
```

Runtime artefacts are written under `eval/result` and `eval/outputs`. Those folders are gitignored.

## Files to prepare

Copy the example env files, then fill in keys. Do not commit the real env files.

| Copy from | Create | Required for |
| --- | --- | --- |
| `backend/.env.example` | `backend/.env` | API keys and model backends |
| `frontend/.env.example` | `frontend/.env.local` | Frontend → API URL and Supabase auth |
| `prisma/.env.example` | `prisma/.env` | Optional. Only if you push/pull the database |

Minimum keys:

- `backend/.env`: `KIMI_API_KEY`, `REPLICATE_API_TOKEN`. Keep `MUSICGEN_BACKEND=replicate`.
- `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`. Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for login, library, and ratings.

Optional later: `prisma/schema.prisma` and `prisma/setup.sql` if you set up Supabase tables. The fragrance catalog at `backend/data/pyrfume_catalog.json` is used at runtime; rebuild it only if you need a fresh cache (`backend/scripts/build_pyrfume_catalog.py`).

## Installation

Prerequisites: Git, Node.js 20+, Python 3.12, [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Wickefest/brandbit.git
cd brandbit
```

Prepare the three env files above, then:

```bash
cd backend
uv sync --group dev

cd ../frontend
npm install
```

## Running

Two terminals.

Backend (http://localhost:8000):

```bash
cd backend
uv run uvicorn src.main:app --reload
```

Frontend (http://localhost:3000):

```bash
cd frontend
npm run dev
```

CLI one-shot (no UI):

```bash
cd backend
uv run brandbit path/to/image.jpg
```

## Testing

```bash
cd backend
uv run pytest
```

Tests live in `backend/src/test/` (API, fragrance RAG, congruence, refinement, CLIP proxies, and related units). Live model calls are not required for the default suite.

## Evaluation

Notebooks and comparison cases sit in `eval/notebook/` and `eval/comparison/`. Generated runs go to `eval/result/` and `eval/outputs/` and are not committed.
