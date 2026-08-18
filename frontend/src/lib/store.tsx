import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ReactNode } from "react";

export interface LLMModel {
  id: string;
  label: string;
  provider: string;
}

export const llmModels: LLMModel[] = [
  { id: "gpt-4.1-nano", label: "GPT-4.1 Nano (OpenAI)", provider: "openai" },
  { id: "gpt-4.1-mini", label: "GPT-4.1 Mini (OpenAI)", provider: "openai" },
  { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (Groq)", provider: "groq" },
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash (Google)", provider: "gemini" },
];

export type LlmModel = "gpt-4.1-nano" | "gpt-4.1-mini" | "llama-3.3-70b-versatile" | "gemini-2.5-flash";

export interface DatasetProfile {
  filename?: string;
  rows?: number;
  columns?: number;
  [key: string]: any;
}

export interface PipelineConfig {
  maxRetries: number;
  temperature: number;
  timeout: number;
}

import {
  mockChat,
  mockHealth,
  mockInsights,
  mockProfile,
  mockRecommendations,
  mockVisualizations,
  pipelineStageTemplate,
} from "@/data/mock";
import type { ChatMessage, Insight, PipelineStage, Recommendation, ServiceHealth, Visualization } from "@/types";

export interface AppState {
  mockMode: boolean;
  selectedModel: string;
  model: string;
  profile?: DatasetProfile;
  config: PipelineConfig;
  stages: PipelineStage[];
  pipelineStatus: "idle" | "running" | "completed" | "failed";
  insights: Insight[];
  recommendations: Recommendation[];
  visualizations: Visualization[];
  executionLogs?: ExecutionLog[];
  pipelineDurationMs: number;
  reportUrl?: string;        // Sweetviz profile report URL (primary HTML deliverable)
  profileReportUrl?: string; // Sweetviz profile report URL
  lastRunAt: string;
  chat: ChatMessage[];
  health: ServiceHealth[];
  setMockMode: (v: boolean) => void;
  setSelectedModel: (v: string) => void;
  setModel: (v: string) => void;
  setProfile: (p?: DatasetProfile) => void;
  setConfig: (c: Partial<PipelineConfig>) => void;
  runPipeline: (filename: string) => void;
  finishPipeline: () => void;
  setAnalysisResults: (data: any) => void;

  appendChat: (msg: ChatMessage) => void;
  clearChat: () => void;
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      mockMode: false,
      selectedModel: "gpt-4.1-nano",
      model: "gpt-4.1-nano",
      profile: mockProfile,
      config: { maxRetries: 3, temperature: 0.1, timeout: 60 },
      stages: pipelineStageTemplate,
      pipelineStatus: "idle",
      insights: mockInsights,
      recommendations: mockRecommendations,
      visualizations: mockVisualizations,
      pipelineDurationMs: 21540,
      reportUrl: undefined,
      profileReportUrl: undefined,
      lastRunAt: new Date().toISOString(),
      chat: mockChat,
      health: mockHealth,
      setMockMode: (v) => set({ mockMode: v }),
      setSelectedModel: (v) => set({ selectedModel: v, model: v }),
      setModel: (v) => set({ model: v, selectedModel: v }),
      setProfile: (p) => set({ profile: p }),
      setConfig: (c) => set((s) => ({ config: { ...(s.config || { maxRetries: 3, temperature: 0.1, timeout: 60 }), ...c } })),
      runPipeline: (filename: string) => {
        set({
          pipelineStatus: "running",
          profile: {
            filename,
            rows: 0,
            columns: 0,
            qualityScore: 100,
            numeric: 0,
            categorical: 0,
            datetime: 0,
            boolean: 0,
            other: 0,
            columnStats: [],
          },
          insights: [],
          recommendations: [],
          executionLogs: [],
          stages: pipelineStageTemplate.map((s, idx) => ({
            ...s,
            status: idx === 0 ? ("running" as const) : ("pending" as const),
            progress: idx === 0 ? 50 : 0,
          })),
        });
      },
      finishPipeline: () => {
        set({
          pipelineStatus: "completed",
          stages: pipelineStageTemplate.map((s) => ({
            ...s,
            status: "completed" as const,
            progress: 100,
          })),
        });
      },

      setAnalysisResults: (data: any) => {
        if (!data) return;
        const prof = data.profile || {};
        const filename = prof.dataset_name || prof.filename || data.report_filename || get().profile?.filename || "uploaded_dataset.csv";
        const rows = prof.rows ?? prof.row_count ?? get().profile?.rows ?? 0;
        const columns = prof.columns ?? prof.column_count ?? get().profile?.columns ?? 0;
        const qualityScore = prof.qualityScore ?? prof.quality_score ?? 98.5;

        // Parse columnStats from backend descriptive_stats & column types
        const rawStats = prof.descriptive_stats || prof.descriptiveStats || {};
        const missingMap = prof.missing_values || prof.missingValues || {};

        const numCols: string[] = prof.numeric_columns || prof.numericColumns || [];
        const catCols: string[] = prof.categorical_columns || prof.categoricalColumns || [];
        const dtCols: string[] = prof.datetime_columns || prof.datetimeColumns || [];
        const idCols: string[] = prof.id_columns || prof.idColumns || [];

        const allColNames = Array.from(
          new Set([
            ...numCols,
            ...catCols,
            ...dtCols,
            ...idCols,
            ...Object.keys(rawStats),
            ...Object.keys(missingMap),
          ]),
        );

        const columnStats = allColNames.map((name) => {
          const isNum = numCols.includes(name);
          const isCat = catCols.includes(name);
          const isDt = dtCols.includes(name);
          const type = isNum
            ? "numeric"
            : isCat
              ? "categorical"
              : isDt
                ? "datetime"
                : "other";
          const st = rawStats[name] || {};
          return {
            name,
            type: type as any,
            missing: missingMap[name] || 0,
            distinct: isNum ? Math.min(rows || 100, 100) : isCat ? 10 : 50,
            mean: st.mean ?? null,
            median: st.median ?? null,
            std: st.std ?? null,
            mode: st.mode ?? null,
            min: st.min ?? null,
            max: st.max ?? null,
          };
        });

        const rawInsights = data.insights || [];
        let parsedInsights: Insight[] = rawInsights.map((ins: any, idx: number) => {
          if (typeof ins === "string") {
            const colonIdx = ins.indexOf(":");
            const category = colonIdx > -1 ? ins.substring(0, colonIdx).trim() : "Insight";
            const body = colonIdx > -1 ? ins.substring(colonIdx + 1).trim() : ins;
            return {
              id: `I-0${idx + 1}`,
              title: `${category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} Summary`,
              explanation: body,
              evidence: body,
              severity: (idx === 0 ? "high" : idx === 1 ? "medium" : "low") as any,
              confidence: 90 + idx,
              targetMetric: category,
            };
          }
          return {
            id: ins.id || `I-0${idx + 1}`,
            title: ins.title || ins.explanation || `Insight ${idx + 1}`,
            explanation: ins.explanation || ins.title || "",
            evidence: ins.evidence || "Verified from dataset analysis.",
            severity: ins.severity || "medium",
            confidence: ins.confidence || 90,
            targetMetric: ins.targetMetric || ins.target_metric || "analysis",
          };
        });

        if (!parsedInsights.length && allColNames.length) {
          parsedInsights = [
            {
              id: "I-01",
              title: `Feature & Distribution Profile for ${filename}`,
              explanation: `Ingested ${rows.toLocaleString()} rows and ${columns} columns (${numCols.length} numeric, ${catCols.length} categorical, ${dtCols.length} datetime features).`,
              evidence: `Features detected: ${allColNames.slice(0, 8).join(", ")}${allColNames.length > 8 ? "..." : ""}`,
              severity: "high",
              confidence: 98,
              targetMetric: "feature_profile",
            },
            {
              id: "I-02",
              title: `Data Quality & Completeness Audit`,
              explanation: Object.keys(missingMap).length
                ? `Missing values detected in: ${Object.entries(missingMap).map(([k, v]) => `${k} (${v} nulls)`).join(", ")}.`
                : `Dataset is 100% complete with zero null cells detected across ${columns} features.`,
              evidence: `Quality score: ${qualityScore}%.`,
              severity: Object.keys(missingMap).length ? "medium" : "low",
              confidence: 95,
              targetMetric: "data_quality",
            },
          ];
        }

        const rawRecs = data.recommendations || [];
        let parsedRecs: Recommendation[] = rawRecs.map((rec: any, idx: number) => {
          if (typeof rec === "string") {
            const colonIdx = rec.indexOf(":");
            const category = colonIdx > -1 ? rec.substring(0, colonIdx).trim() : "";
            const body = colonIdx > -1 ? rec.substring(colonIdx + 1).trim() : rec;
            return {
              id: `R-0${idx + 1}`,
              action: body,
              impact: "Actionable improvement recommended by the insight engine.",
              severity: (idx === 0 ? "critical" : idx === 1 ? "high" : "medium") as any,
              insightId: `I-0${(idx % Math.max(parsedInsights.length, 1)) + 1}`,
            };
          }
          return {
            id: rec.id || `R-0${idx + 1}`,
            action: rec.action || String(rec),
            impact: rec.impact || "Actionable improvement based on evidence.",
            severity: rec.severity || "medium",
            insightId: rec.insightId || rec.insight_id || "I-01",
          };
        });

        if (!parsedRecs.length && parsedInsights.length) {
          parsedRecs = [
            {
              id: "R-01",
              action: `Review distribution and correlation bounds across key numeric features (${numCols.slice(0, 3).join(", ") || "numeric features"}).`,
              impact: "Establishes baseline thresholds for automated anomaly detection.",
              severity: "high",
              insightId: "I-01",
            },
            {
              id: "R-02",
              action: Object.keys(missingMap).length
                ? `Implement input validation and backfill routines for missing cells in ${Object.keys(missingMap).join(", ")}.`
                : `Enforce schema constraints and data type validation at ingestion.`,
              impact: "Eliminates null-value bias in downstream reporting.",
              severity: "medium",
              insightId: "I-02",
            },
          ];
        }


        const rawLogs = data.execution_log || [];
        const executionLogs = rawLogs.map((log: any, idx: number) => ({
          id: `L-${idx + 1}`,
          node: log.task_name || log.node || "Executor",
          attempt: log.attempt || 1,
          snippet: (log.code || "").split("\n")[0] || log.snippet || "Python Analysis Snippet",
          code: log.code || "# Executed snippet",
          stdout: log.stdout || "",
          stderr: log.stderr || "",
          durationMs: log.durationMs || 1500,
          status: log.success !== false ? ("success" as const) : ("failed" as const),
        }));

        const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_BASE_URL as string) || "http://localhost:8000";
        const reportFilename = data.report_filename;
        const profileReportFilename = data.profile_report_filename || data.report_filename;
        const reportUrl = reportFilename ? `${API_BASE}/report/${encodeURIComponent(reportFilename)}` : undefined;
        const profileReportUrl = profileReportFilename ? `${API_BASE}/report/${encodeURIComponent(profileReportFilename)}` : undefined;

        set(() => ({
          profile: {
            ...prof,
            filename,
            rows,
            columns,
            qualityScore,
            numeric: numCols.length,
            categorical: catCols.length,
            datetime: dtCols.length,
            boolean: 0,
            other: idCols.length,
            columnStats,
            // raw backend fields for the Overview tab
            duplicates: prof.duplicates ?? 0,
            missingValues: prof.missing_values ?? prof.missingValues ?? {},
            constantColumns: prof.constant_columns ?? prof.constantColumns ?? [],
            highCardinalityColumns: prof.high_cardinality_columns ?? prof.highCardinalityColumns ?? [],
          },
          insights: parsedInsights,
          recommendations: parsedRecs,
          executionLogs: executionLogs.length ? executionLogs : undefined,
          reportUrl,
          profileReportUrl,
          chat: [
            {
              id: `c-${Date.now()}`,
              role: "assistant",
              content: `I'm grounded in **${filename}** (${rows.toLocaleString()} rows · ${columns} columns). Ask me about key findings, quality risks, or trends from the active report.`,
              timestamp: new Date().toISOString(),
              grounded: true,
            },
          ],
        }));
      },

      appendChat: (msg: ChatMessage) => set((s) => ({ chat: [...(s.chat || []), msg] })),

      clearChat: () => set({ chat: [] }),
    }),
    { name: "ai-data-analyst-store" }
  )
);





// Provider component that wraps the app with the store context
// (Zustand doesn't need a Provider, but TanStack Start expects one)
export function AppStoreProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}