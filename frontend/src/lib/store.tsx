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
  qualityScore?: number;
  numeric?: number;
  categorical?: number;
  datetime?: number;
  boolean?: number;
  other?: number;
  duplicates?: number;
  missingValues?: Record<string, number>;
  constantColumns?: string[];
  highCardinalityColumns?: string[];
  columnStats?: import("@/types").ColumnStat[];
  [key: string]: any;
}

export interface PipelineConfig {
  maxRetries: number;
  temperature: number;
  timeout: number;
}

import {
  mockHealth,
  pipelineStageTemplate,
} from "@/data/mock";
import type { ChatMessage, ExecutionLog, Insight, PipelineStage, Recommendation, ServiceHealth, Visualization } from "@/types";

export interface AppState {
  mockMode: boolean;
  selectedModel: string;
  model: string;
  profile: DatasetProfile | undefined;
  config: PipelineConfig;
  stages: PipelineStage[];
  pipelineStatus: "idle" | "running" | "completed" | "failed";
  insights: Insight[];
  recommendations: Recommendation[];
  visualizations: Visualization[];
  executionLogs: ExecutionLog[] | undefined;
  analysisResults: any[] | undefined;
  pipelineDurationMs: number;
  reportUrl: string | undefined;        // Sweetviz profile report URL (primary HTML deliverable)
  profileReportUrl: string | undefined; // Sweetviz profile report URL
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
      profile: undefined,
      config: { maxRetries: 3, temperature: 0.1, timeout: 60 },
      stages: pipelineStageTemplate,
      pipelineStatus: "idle",
      insights: [],
      recommendations: [],
      visualizations: [],
      pipelineDurationMs: 0,
      reportUrl: undefined,
      profileReportUrl: undefined,
      executionLogs: undefined,
      analysisResults: undefined,
      lastRunAt: new Date().toISOString(),
      chat: [],
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
        const nuniqueMap = prof.nunique_map || prof.nuniqueMap || {};

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
            ...Object.keys(nuniqueMap),
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
          // Use real distinct count from backend: prefer rawStats.distinct, then nunique_map, then null
          const distinct = st.distinct ?? nuniqueMap[name] ?? null;
          return {
            name,
            type: type as any,
            missing: missingMap[name] || 0,
            distinct,
            mean: st.mean ?? null,
            median: st.median ?? null,
            std: st.std ?? null,
            mode: st.mode ?? null,
            skewness: st.skewness ?? null,
            min: st.min ?? null,
            max: st.max ?? null,
          };
        });

        // Helper: derive severity label from confidence (0..1 float from backend, or 0..100 int from legacy)
        const _severity = (conf: number | undefined): "critical" | "high" | "medium" | "low" => {
          const pct = conf !== undefined && conf <= 1 ? conf * 100 : (conf ?? 50);
          if (pct >= 90) return "high";
          if (pct >= 75) return "medium";
          if (pct >= 50) return "low";
          return "low";
        };
        const _confPct = (conf: number | undefined): number => {
          if (conf === undefined) return 75;
          return conf <= 1 ? Math.round(conf * 100) : conf;
        };

        const rawInsights = data.insights || [];
        let parsedInsights: Insight[] = rawInsights.map((ins: any, idx: number) => {
          if (typeof ins === "string") {
            const colonIdx = ins.indexOf(":");
            const category = colonIdx > -1 ? ins.substring(0, colonIdx).trim() : "Insight";
            const body = colonIdx > -1 ? ins.substring(colonIdx + 1).trim() : ins;
            return {
              id: `I-0${idx + 1}`,
              title: `${category.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())} Summary`,
              explanation: body,
              evidence: body,
              severity: (idx === 0 ? "high" : idx === 1 ? "medium" : "low") as any,
              confidence: 90 + idx,
              targetMetric: category,
            };
          }
          // Backend Insight schema: {id, title, body, evidence, metric, value, confidence (0..1)}
          // Legacy / already-mapped: {id, title, explanation, evidence, targetMetric, severity, confidence (0..100)}
          const explanation = ins.explanation || ins.body || ins.title || "";
          const targetMetric = ins.targetMetric || ins.target_metric || ins.metric || "analysis";
          const conf = ins.confidence;
          return {
            id: ins.id ? (typeof ins.id === "number" ? `I-${String(ins.id).padStart(2, "0")}` : ins.id) : `I-0${idx + 1}`,
            title: ins.title || `Insight ${idx + 1}`,
            explanation,
            evidence: ins.evidence || `Metric: ${targetMetric}`,
            severity: ins.severity ?? _severity(conf),
            confidence: _confPct(conf),
            targetMetric,
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
            const body = colonIdx > -1 ? rec.substring(colonIdx + 1).trim() : rec;
            return {
              id: `R-0${idx + 1}`,
              action: body,
              impact: "Actionable improvement recommended by the insight engine.",
              severity: (idx === 0 ? "critical" : idx === 1 ? "high" : "medium") as any,
              insightId: `I-0${(idx % Math.max(parsedInsights.length, 1)) + 1}`,
            };
          }
          // Backend Recommendation schema: {title, body, insight_id}
          // Legacy: {id, action, impact, severity, insightId}
          const action = rec.action || rec.title || String(rec);
          const impact = rec.impact || rec.body || "Actionable improvement based on evidence.";
          const rawInsightId = rec.insightId || rec.insight_id;
          const insightId = rawInsightId
            ? (typeof rawInsightId === "number" ? `I-${String(rawInsightId).padStart(2, "0")}` : rawInsightId)
            : `I-0${(idx % Math.max(parsedInsights.length, 1)) + 1}`;
          return {
            id: rec.id || `R-0${idx + 1}`,
            action,
            impact,
            severity: rec.severity ?? (idx === 0 ? "high" : idx === 1 ? "medium" : "low") as any,
            insightId,
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

        // Map analysis_results and generated_files → rich, interactive Visualization objects
        const rawResults = data.analysis_results || [];
        const rawCharts: string[] = data.generated_files || [];
        const parsedVisualizations: import("@/types").Visualization[] = [];

        // 1) Extract structured interactive chart objects from execution stats (with Recharts data points)
        rawResults.forEach((res: any) => {
          const stats = res.stats || {};
          const taskCharts = stats.charts || [];
          if (Array.isArray(taskCharts) && taskCharts.length > 0) {
            taskCharts.forEach((tc: any) => {
              const fname = tc.image_file;
              parsedVisualizations.push({
                id: `V-0${parsedVisualizations.length + 1}`,
                title: tc.title || (tc.column ? `Distribution of ${tc.column}` : "Analysis Chart"),
                description: `Interactive breakdown for ${tc.column || "dataset"}`,
                kind: (tc.kind || "bar") as any,
                insightId: parsedInsights[parsedVisualizations.length % Math.max(parsedInsights.length, 1)]?.id ?? "I-01",
                data: Array.isArray(tc.data) ? tc.data : [],
                imageUrl: fname ? `${API_BASE}/report/${encodeURIComponent(fname)}` : undefined,
              });
            });
          }
        });

        // 2) Supplementary: map any leftover image files from generated_files that were not in taskCharts
        rawCharts.forEach((fname: string, idx: number) => {
          const safeName = fname.replace(/\\/g, "/").split("/").pop() || fname;
          if (/\.(png|jpg|jpeg|svg)$/i.test(safeName)) {
            const alreadyAdded = parsedVisualizations.some((v) => v.imageUrl?.endsWith(safeName));
            if (!alreadyAdded) {
              parsedVisualizations.push({
                id: `V-0${parsedVisualizations.length + 1}`,
                title: safeName.replace(/[_-]/g, " ").replace(/\.[^.]+$/, "").replace(/\b\w/g, (c: string) => c.toUpperCase()),
                description: `Analysis visualization`,
                kind: "bar" as const,
                insightId: parsedInsights[idx % Math.max(parsedInsights.length, 1)]?.id ?? "I-01",
                imageUrl: `${API_BASE}/report/${encodeURIComponent(safeName)}`,
                data: [],
              });
            }
          }
        });

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
          visualizations: parsedVisualizations,
          executionLogs: executionLogs.length ? executionLogs : undefined,
          analysisResults: rawResults,
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
    { name: "ai-data-analyst-store", version: 2 }
  )
);





// Provider component that wraps the app with the store context
// (Zustand doesn't need a Provider, but TanStack Start expects one)
export function AppStoreProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}