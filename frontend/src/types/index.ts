export type Severity = "critical" | "high" | "medium" | "low";
export type StageStatus = "pending" | "running" | "completed" | "failed";
export type HealthStatus = "connected" | "degraded" | "offline";

export interface ColumnStat {
  name: string;
  type: "numeric" | "categorical" | "datetime" | "boolean" | "other";
  missing: number;
  distinct: number;
  mean: number | null;
  min: number | string | null;
  max: number | string | null;
}

export interface DatasetProfile {
  filename: string;
  rows: number;
  columns: number;
  qualityScore: number;
  numeric: number;
  categorical: number;
  datetime: number;
  boolean: number;
  other: number;
  columnStats: ColumnStat[];
  preview: { headers: string[]; rows: string[][] };
}

export interface PipelineStage {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  status: StageStatus;
  durationMs: number;
  progress: number;
}

export interface Insight {
  id: string;
  title: string;
  explanation: string;
  evidence: string;
  severity: Severity;
  confidence: number;
  targetMetric: string;
}

export interface Recommendation {
  id: string;
  action: string;
  impact: string;
  severity: Severity;
  insightId: string;
}

export interface Visualization {
  id: string;
  title: string;
  description: string;
  insightId: string;
  kind: "bar" | "line" | "donut" | "area";
  data: { label: string; value: number }[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  latencyMs?: number;
  grounded?: boolean;
}

export interface ServiceHealth {
  name: string;
  status: HealthStatus;
  latencyMs: number;
  lastChecked: string;
}

export interface ExecutionLog {
  id: string;
  node: string;
  attempt: number;
  snippet: string;
  code: string;
  stdout: string;
  stderr: string;
  durationMs: number;
  status: "success" | "failed" | "running";
}

export interface TelemetryCall {
  id: string;
  task: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  cost: number;
}

export interface SampleDataset {
  id: string;
  name: string;
  filename: string;
  description: string;
  rows: number;
  columns: number;
  icon: "sales" | "hiring" | "churn";
}

export interface PipelineConfig {
  maxRetries: number;
  temperature: number;
  timeout: number;
}
