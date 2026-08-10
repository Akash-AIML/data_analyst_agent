import { mockHealth, mockProfile, mockInsights, mockRecommendations } from "@/data/mock";
import type { DatasetProfile, Insight, Recommendation, ServiceHealth, ExecutionLog, ChatMessage } from "@/types";

const API_BASE = (import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? "";
const TIMEOUT_MS = 15000;

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) throw new Error(`Request failed [${res.status}]`);
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
    const data = await request<AnalyzeResponse>("/analyze", { method: "POST", body });
    return { data, mock: false };
  } catch (error) {
    return {
      data: {
        status: "completed",
        profile: { ...mockProfile, filename: file.name },
        insights: mockInsights,
        recommendations: mockRecommendations,
      },
      mock: true,
      error: error instanceof Error ? error.message : "Unknown error",
    };
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

