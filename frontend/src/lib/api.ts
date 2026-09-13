/**
 * Backend API client.
 * Calls generate refine health and builds audio URLs.
 */

import { API_BASE, type ApiResult } from "@/lib/types";
export { API_BASE };

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object" && "msg" in first) {
      const msg = (first as { msg?: unknown }).msg;
      if (typeof msg === "string") return msg;
    }
  }
  return fallback;
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

async function requestJson(
  path: string,
  init?: RequestInit,
  fallback = "Request failed"
): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach Brandbit backend at ${API_BASE}. Start it with: cd backend && uv run uvicorn src.main:app --reload`,
      0
    );
  }

  const body = await readJson(res);
  if (!res.ok) {
    throw new ApiError(detailMessage(body, fallback), res.status);
  }
  return body;
}

export type GenerateOptions = {
  image: File;
  brandItem?: string | null;
  /** ``bad`` = visual → BAD LLM → agents; ``prompt`` = visual to agents */
  mode?: "bad" | "prompt" | null;
  onStage?: (event: GenerateStageEvent) => void;
};

export type GenerateStageEvent = {
  stage: string;
  status: "started" | "done" | string;
  message?: string | null;
};

export async function generateConcept({
  image,
  brandItem,
  mode,
  onStage,
}: GenerateOptions): Promise<ApiResult> {
  const form = new FormData();
  form.append("image", image);
  const item = brandItem?.trim();
  if (item) form.append("brand_item", item);
  const pipelineMode = mode === "prompt" ? "prompt" : "bad";
  form.append("mode", pipelineMode);
  form.append("stream", onStage ? "1" : "0");

  // POST the image and optionally read the NDJSON stage stream
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError(
      `Cannot reach Brandbit backend at ${API_BASE}. Start it with: cd backend && uv run uvicorn src.main:app --reload`,
      0
    );
  }

  if (!onStage) {
    const body = await readJson(res);
    if (!res.ok) {
      throw new ApiError(detailMessage(body, "Generation failed"), res.status);
    }
    return body as ApiResult;
  }

  if (!res.ok) {
    const body = await readJson(res);
    throw new ApiError(detailMessage(body, "Generation failed"), res.status);
  }

  if (!res.body) {
    throw new ApiError("Generation stream returned no body", res.status);
  }

  // Reference: https://developer.mozilla.org/en-US/docs/Web/API/ReadableStreamDefaultReader
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ApiResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((part) => part.trim())
        .find((part) => part.startsWith("data:"));
      if (!line) continue;
      const raw = line.replace(/^data:\s*/, "");
      if (!raw) continue;

      let event: {
        type?: string;
        stage?: string;
        status?: string;
        message?: string | null;
        result?: ApiResult;
        detail?: string;
      };
      try {
        event = JSON.parse(raw) as typeof event;
      } catch {
        continue;
      }

      if (event.type === "stage" && event.stage && event.status) {
        onStage({
          stage: event.stage,
          status: event.status,
          message: event.message,
        });
      } else if (event.type === "result" && event.result) {
        result = event.result;
      } else if (event.type === "error") {
        throw new ApiError(event.detail || "Generation failed", 500);
      }
    }
  }

  if (!result) {
    throw new ApiError("Generation finished without a result payload", 500);
  }
  return result;
}

export type RefineSuccess = ApiResult & { success?: true };
export type RefineClarification = {
  success: false;
  clarification_request?: string;
};
export type RefineResult = RefineSuccess | RefineClarification;

export async function refineConcept(
  executionId: string,
  feedback: string
): Promise<RefineResult> {
  const form = new FormData();
  form.append("execution_id", executionId);
  form.append("feedback", feedback);

  const body = await requestJson(
    "/api/refine",
    { method: "POST", body: form },
    "Refine failed"
  );
  return body as RefineResult;
}

function encodePathSegment(seg: string): string {
  if (!seg) return seg;
  try {
    return encodeURIComponent(decodeURIComponent(seg));
  } catch {
    return encodeURIComponent(seg);
  }
}

/** Resolve `/api/audio/...` (or absolute URL) against the backend base. */
export function resolveAudioUrl(
  audioSampleRef: string | null | undefined
): string | null {
  if (!audioSampleRef) return null;
  if (/^https?:\/\//i.test(audioSampleRef)) return audioSampleRef;
  const path = audioSampleRef.startsWith("/")
    ? audioSampleRef
    : `/${audioSampleRef}`;
  const encoded = path
    .split("/")
    .map((seg, i) => (i === 0 ? seg : encodePathSegment(seg)))
    .join("/");
  return `${API_BASE}${encoded}`;
}
