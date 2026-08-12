import { mockHealth, mockProfile, mockInsights, mockRecommendations } from "@/data/mock";
import type { DatasetProfile, Insight, Recommendation, ServiceHealth, ExecutionLog, ChatMessage } from "@/types";

const API_BASE = (import.meta.env['VITE_API_BASE_URL'] as string | undefined) || "http://localhost:8000";
const TIMEOUT_MS = 300000; // 5 minutes timeout for multi-agent pipeline execution


export interface ApiResult<T> {
  data: T;
  mock: boolean;
  error?: string;
}

export interface AnalyzeResponse {
  status: string;
  profile: DatasetProfile;
  insights?: Insight[];
  recommendations?: Recommendation[];
  execution_log?: ExecutionLog[];
  report_filename?: string;
  report_url?: string;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs: number = TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Request failed [${res.status}]: ${errText || res.statusText}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/** POST /analyze — upload a CSV and run the multi-agent pipeline. */
export async function analyze(file: File): Promise<ApiResult<AnalyzeResponse>> {
  const body = new FormData();
  body.append("file", file);
  try {
    const data = await request<AnalyzeResponse>("/analyze", { method: "POST", body }, 300000);
    return { data, mock: false };
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : "Unknown error";
    console.error("Backend pipeline execution failed:", error);
    throw new Error(errMsg);
  }
}


/** POST /chat — send a question to the report grounded insight chat endpoint. */
export async function sendChatMessage(message: string): Promise<ApiResult<ChatMessage>> {
  try {
    const data = await request<ChatMessage>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    return { data, mock: false };
  } catch (error) {
    return {
      data: {
        id: String(Date.now()),
        role: "assistant",
        content: `Offline mode answer: Based on generated summary, '${message}' highlights primary trends and metric correlations.`,
        timestamp: "Just now",
        grounded: false,
      },
      mock: true,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/** GET /health — API and system health. */
export async function getHealth(): Promise<ApiResult<ServiceHealth[]>> {
  try {
    const data = await request<ServiceHealth[]>("/health");
    return { data, mock: false };
  } catch (error) {
    return { data: mockHealth, mock: true, error: error instanceof Error ? error.message : "Unknown error" };
  }
}

/** GET /report/{filename} — URL of the Sweetviz / HTML report. */
export function getReportUrl(filename: string): string {
  return `${API_BASE}/report/${encodeURIComponent(filename)}`;
}

export async function checkReportAvailable(filename: string): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(getReportUrl(filename), { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Fetch a report URL as a blob and trigger a browser download.
 *
 * Using `<a href="crossOriginUrl" download>` is silently ignored by browsers
 * (the `download` attribute only works for same-origin URLs). Fetching the
 * content as a blob and creating a temporary blob URL bypasses that restriction.
 */
export async function downloadReport(
  url: string,
  filename: string,
  onProgress?: (pct: number) => void,
): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000); // 2 min cap
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);

    // Stream-read with progress if Content-Length is available
    const total = Number(res.headers.get("Content-Length") || 0);
    const reader = res.body?.getReader();
    const chunks: Uint8Array[] = [];
    let received = 0;
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (total > 0 && onProgress) onProgress(Math.round((received / total) * 100));
      }
    } else {
      const buf = await res.arrayBuffer();
      chunks.push(new Uint8Array(buf));
    }

    const mimeType = res.headers.get("Content-Type") || "text/html";
    const blob = new Blob(chunks, { type: mimeType });
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Revoke after a tick so the browser has time to start the download
    setTimeout(() => URL.revokeObjectURL(blobUrl), 10_000);
  } finally {
    clearTimeout(timer);
  }
}
