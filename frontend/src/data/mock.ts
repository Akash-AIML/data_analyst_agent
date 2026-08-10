import type {
  ChatMessage,
  DatasetProfile,
  ExecutionLog,
  Insight,
  PipelineStage,
  Recommendation,
  SampleDataset,
  ServiceHealth,
  TelemetryCall,
  Visualization,
} from "@/types";

export const sampleDatasets: SampleDataset[] = [
  {
    id: "sales",
    name: "Sales Transactions",
    filename: "sales_transactions.csv",
    description: "Regional transaction and revenue analysis.",
    rows: 1000,
    columns: 10,
    icon: "sales",
  },
  {
    id: "hiring",
    name: "Hiring Bias Data",
    filename: "hiring_bias.csv",
    description: "Candidate demographics and hiring outcome analysis.",
    rows: 2400,
    columns: 14,
    icon: "hiring",
  },
  {
    id: "churn",
    name: "E-commerce Churn",
    filename: "ecommerce_churn.csv",
    description: "Customer behavior and churn prediction analysis.",
    rows: 5200,
    columns: 18,
    icon: "churn",
  },
];

export const mockProfile: DatasetProfile = {
  filename: "sales_transactions.csv",
  rows: 1000,
  columns: 10,
  qualityScore: 98.5,
  numeric: 6,
  categorical: 4,
  datetime: 1,
  boolean: 1,
  other: 0,
  columnStats: [
    { name: "transaction_id", type: "other", missing: 0, distinct: 1000, mean: null, min: null, max: null },
    { name: "order_date", type: "datetime", missing: 0, distinct: 365, mean: null, min: "2024-01-01", max: "2024-12-31" },
    { name: "region", type: "categorical", missing: 0, distinct: 5, mean: null, min: null, max: null },
    { name: "channel", type: "categorical", missing: 12, distinct: 4, mean: null, min: null, max: null },
    { name: "product_category", type: "categorical", missing: 3, distinct: 8, mean: null, min: null, max: null },
    { name: "customer_segment", type: "categorical", missing: 0, distinct: 3, mean: null, min: null, max: null },
    { name: "units", type: "numeric", missing: 0, distinct: 42, mean: 6.4, min: 1, max: 48 },
    { name: "unit_price", type: "numeric", missing: 0, distinct: 318, mean: 128.72, min: 4.99, max: 1499 },
    { name: "discount_pct", type: "numeric", missing: 27, distinct: 21, mean: 0.08, min: 0, max: 0.45 },
    { name: "revenue", type: "numeric", missing: 0, distinct: 962, mean: 5862.4, min: 12.4, max: 51840 },
  ],
  preview: {
    headers: ["transaction_id", "order_date", "region", "channel", "units", "unit_price", "revenue"],
    rows: [
      ["TX-100001", "2024-01-03", "West", "Online", "6", "249.00", "1494.00"],
      ["TX-100002", "2024-01-03", "East", "Retail", "2", "99.50", "199.00"],
      ["TX-100003", "2024-01-04", "West", "Partner", "14", "128.00", "1792.00"],
      ["TX-100004", "2024-01-05", "North", "Online", "1", "1499.00", "1499.00"],
      ["TX-100005", "2024-01-05", "South", "Retail", "9", "64.25", "578.25"],
    ],
  },
};

export const pipelineStageTemplate: PipelineStage[] = [
  {
    id: "profiling",
    title: "Dataset Profiling",
    subtitle: "Sweetviz",
    description: "Scanning schema, distributions, and missing-value patterns.",
    status: "pending",
    durationMs: 4200,
    progress: 0,
  },
  {
    id: "plan",
    title: "Plan Generation",
    subtitle: "Planner Node",
    description: "Drafting an analysis plan grounded in the dataset profile.",
    status: "pending",
    durationMs: 3100,
    progress: 0,
  },
  {
    id: "execute",
    title: "Python Code Execution",
    subtitle: "Sandbox",
    description: "Running generated pandas / matplotlib analysis in an isolated sandbox.",
    status: "pending",
    durationMs: 6400,
    progress: 0,
  },
  {
    id: "insight",
    title: "Insight & Recommendation Synthesis",
    subtitle: "Executive Insight Agent",
    description: "Converting verified evidence into executive narrative and actions.",
    status: "pending",
    durationMs: 5200,
    progress: 0,
  },
  {
    id: "report",
    title: "Report Compilation",
    subtitle: "HTML & PDF",
    description: "Assembling the deliverable report with charts and citations.",
    status: "pending",
    durationMs: 2600,
    progress: 0,
  },
];

export const mockInsights: Insight[] = [
  {
    id: "I-01",
    title: "West region generates the highest sales volume.",
    explanation:
      "The West region is the single largest revenue contributor and outpaces the next-best region by a wide margin, driven mainly by partner and online channels.",
    evidence: "West region generated $1.84M in sales, representing 31.4% of total revenue (n=1,000 transactions).",
    severity: "high",
    confidence: 95,
    targetMetric: "sales_by_region",
  },
  {
    id: "I-02",
    title: "Discount depth erodes margin without lifting units.",
    explanation:
      "Transactions with discounts above 20% show no meaningful increase in units sold, suggesting discounting is being applied to demand that already exists.",
    evidence:
      "Mean units for discount_pct > 0.20 is 6.6 vs 6.3 for discount_pct <= 0.20 (Δ = +0.3 units, p = 0.41).",
    severity: "critical",
    confidence: 88,
    targetMetric: "discount_vs_units",
  },
  {
    id: "I-03",
    title: "Q4 revenue growth is concentrated in two months.",
    explanation:
      "Revenue accelerates sharply in November and December, indicating heavy seasonality that should shape inventory and staffing plans.",
    evidence: "Nov + Dec revenue = $1.41M, 24.1% of annual revenue across 16.7% of the calendar.",
    severity: "medium",
    confidence: 92,
    targetMetric: "monthly_revenue",
  },
  {
    id: "I-04",
    title: "discount_pct has a material missing-data gap.",
    explanation:
      "2.7% of rows are missing discount data, which biases any margin analysis that silently treats missing as zero discount.",
    evidence: "27 of 1,000 rows have null discount_pct; all other numeric columns are complete.",
    severity: "low",
    confidence: 99,
    targetMetric: "missing_data",
  },
];

export const mockRecommendations: Recommendation[] = [
  {
    id: "R-01",
    action:
      "Investigate West-region sales drivers and replicate the strongest-performing channels in underperforming regions.",
    impact: "Estimated +6-9% revenue lift in South and North regions within two quarters.",
    severity: "high",
    insightId: "I-01",
  },
  {
    id: "R-02",
    action: "Cap standard discounts at 20% and require approval beyond that threshold.",
    impact: "Recovers an estimated $180K in annual gross margin with negligible volume risk.",
    severity: "critical",
    insightId: "I-02",
  },
  {
    id: "R-03",
    action: "Shift inventory and support staffing toward the November-December peak.",
    impact: "Reduces stockout risk during the period carrying ~24% of annual revenue.",
    severity: "medium",
    insightId: "I-03",
  },
  {
    id: "R-04",
    action: "Add a not-null constraint and backfill process for discount_pct at ingestion.",
    impact: "Removes a known bias source from all downstream margin reporting.",
    severity: "low",
    insightId: "I-04",
  },
];

export const mockVisualizations: Visualization[] = [
  {
    id: "V-01",
    title: "Sales by Region",
    description: "Total revenue contribution per region.",
    insightId: "I-01",
    kind: "bar",
    data: [
      { label: "West", value: 1840 },
      { label: "East", value: 1420 },
      { label: "North", value: 1180 },
      { label: "South", value: 960 },
      { label: "Central", value: 460 },
    ],
  },
  {
    id: "V-02",
    title: "Monthly Revenue Trend",
    description: "Revenue by month with a pronounced Q4 peak.",
    insightId: "I-03",
    kind: "line",
    data: [
      { label: "Jan", value: 380 },
      { label: "Feb", value: 402 },
      { label: "Mar", value: 448 },
      { label: "Apr", value: 431 },
      { label: "May", value: 469 },
      { label: "Jun", value: 512 },
      { label: "Jul", value: 488 },
      { label: "Aug", value: 501 },
      { label: "Sep", value: 522 },
      { label: "Oct", value: 596 },
      { label: "Nov", value: 662 },
      { label: "Dec", value: 749 },
    ],
  },
  {
    id: "V-03",
    title: "Customer Churn Distribution",
    description: "Retained vs churned customers by segment.",
    insightId: "I-02",
    kind: "bar",
    data: [
      { label: "Enterprise", value: 6 },
      { label: "Mid-market", value: 13 },
      { label: "SMB", value: 21 },
    ],
  },
  {
    id: "V-04",
    title: "Missing Data Analysis",
    description: "Null rate per column, in percent.",
    insightId: "I-04",
    kind: "bar",
    data: [
      { label: "discount_pct", value: 2.7 },
      { label: "channel", value: 1.2 },
      { label: "product_category", value: 0.3 },
      { label: "revenue", value: 0 },
    ],
  },
  {
    id: "V-05",
    title: "Hiring Outcome Distribution",
    description: "Offer rate by candidate cohort.",
    insightId: "I-01",
    kind: "area",
    data: [
      { label: "Cohort A", value: 34 },
      { label: "Cohort B", value: 28 },
      { label: "Cohort C", value: 41 },
      { label: "Cohort D", value: 22 },
    ],
  },
];

export const mockChat: ChatMessage[] = [
  {
    id: "c-1",
    role: "assistant",
    content:
      "I'm grounded in **sales_transactions.csv** (1,000 rows · 10 columns). Ask me about regions, revenue trends, discounting, or data quality and I'll answer with evidence from the active report.",
    timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    latencyMs: 940,
    grounded: true,
  },
];

export const mockChatReplies: Record<string, string> = {
  takeaways:
    "**Key takeaways from this report:**\n\n- **West leads revenue** — $1.84M, 31.4% of total.\n- **Discounting is not buying volume** — units are flat above a 20% discount.\n- **Q4 is decisive** — Nov + Dec carry 24.1% of annual revenue.\n\n> Evidence: sales_by_region, discount_vs_units, monthly_revenue nodes of the verified pipeline output.",
  region:
    "**West** has the highest sales volume.\n\n- West: **$1.84M** (31.4%)\n- East: $1.42M (24.2%)\n- North: $1.18M (20.1%)\n\n> Evidence: West region generated $1.84M in sales, representing 31.4% of total revenue.",
  quality:
    "There is **one material data quality issue**.\n\n- `discount_pct` is missing in **27 of 1,000 rows** (2.7%)\n- `channel` missing in 12 rows (1.2%)\n- Overall quality score: **98.5%**\n\n> Treating missing discounts as zero would bias margin analysis downward.",
  default:
    "Based on the active dataset report:\n\n- Revenue is **concentrated in the West region** and in **Q4**.\n- Discount depth beyond 20% shows **no statistically meaningful volume lift**.\n- Data completeness is **98.5%**, with `discount_pct` the only notable gap.\n\n> All figures are read from the verified pipeline output for sales_transactions.csv.",
};

export const mockHealth: ServiceHealth[] = [
  { name: "Backend API", status: "connected", latencyMs: 42, lastChecked: "just now" },
  { name: "Database", status: "connected", latencyMs: 18, lastChecked: "just now" },
  { name: "LLM Provider", status: "connected", latencyMs: 612, lastChecked: "12s ago" },
  { name: "Sandbox", status: "degraded", latencyMs: 1840, lastChecked: "30s ago" },
  { name: "Report Service", status: "connected", latencyMs: 88, lastChecked: "1m ago" },
];

export const mockLogs: ExecutionLog[] = [
  {
    id: "L-1",
    node: "Planner",
    attempt: 1,
    snippet: "plan = planner.invoke(profile_summary)",
    code:
      "plan = planner.invoke({\n    \"profile\": profile_summary,\n    \"objective\": \"Explain revenue drivers and data quality risks\",\n})\n\nfor step in plan.steps:\n    print(step.id, step.description)",
    stdout: "1 Aggregate revenue by region\n2 Trend revenue by month\n3 Test discount depth vs units\n4 Quantify missing data",
    stderr: "",
    durationMs: 3120,
    status: "success",
  },
  {
    id: "L-2",
    node: "Executor",
    attempt: 1,
    snippet: "df.groupby('region')['revenue'].sum()",
    code:
      "import pandas as pd\n\ndf = pd.read_csv('sales_transactions.csv')\nby_region = df.groupby('region')['revenue'].sum().sort_values(ascending=False)\nprint(by_region)",
    stdout: "region\nWest       1840214.55\nEast       1419880.10\nNorth      1180442.75\nSouth       960113.20\nCentral     460330.40",
    stderr: "",
    durationMs: 1840,
    status: "success",
  },
  {
    id: "L-3",
    node: "Executor",
    attempt: 2,
    snippet: "sns.regplot(x='discount_pct', y='units', data=df)",
    code:
      "import seaborn as sns\n\nsns.regplot(x='discount_pct', y='units', data=df)\nplt.savefig('output/analysis/discount_units.png')",
    stderr: "NameError: name 'plt' is not defined",
    stdout: "",
    durationMs: 640,
    status: "failed",
  },
  {
    id: "L-4",
    node: "Reflector",
    attempt: 1,
    snippet: "reflection = reflector.repair(last_error)",
    code:
      "reflection = reflector.repair(\n    code=last_code,\n    error=last_error,\n)\nprint(reflection.diagnosis)",
    stdout: "Missing matplotlib import. Adding `import matplotlib.pyplot as plt` before plotting.",
    stderr: "",
    durationMs: 2210,
    status: "success",
  },
  {
    id: "L-5",
    node: "Executor",
    attempt: 3,
    snippet: "plt.savefig('output/analysis/discount_units.png')",
    code:
      "import matplotlib.pyplot as plt\nimport seaborn as sns\n\nsns.regplot(x='discount_pct', y='units', data=df)\nplt.savefig('output/analysis/discount_units.png')\nprint('saved')",
    stdout: "saved",
    stderr: "",
    durationMs: 2960,
    status: "success",
  },
];

export const mockTelemetry: TelemetryCall[] = [
  { id: "T-1", task: "Planning", model: "llama-3.3-70b", inputTokens: 2140, outputTokens: 612, latencyMs: 1820, cost: 0.0042 },
  { id: "T-2", task: "Code Generation", model: "llama-3.3-70b", inputTokens: 3480, outputTokens: 1284, latencyMs: 2960, cost: 0.0091 },
  { id: "T-3", task: "Reflection", model: "llama-3.3-70b", inputTokens: 1820, outputTokens: 402, latencyMs: 1240, cost: 0.0031 },
  { id: "T-4", task: "Insight Synthesis", model: "llama-3.3-70b", inputTokens: 5120, outputTokens: 2204, latencyMs: 4310, cost: 0.0148 },
];

export const mockAgentState = {
  dataset: {
    filename: "sales_transactions.csv",
    rows: 1000,
    columns: 10,
    quality_score: 98.5,
  },
  pipeline: {
    status: "completed",
    attempt: 1,
    duration_ms: 21540,
    nodes: ["profiler", "planner", "executor", "reflector", "insight", "report"],
  },
  config: {
    model: "llama-3.3-70b",
    temperature: 0.2,
    timeout_s: 120,
    max_retries: 3,
  },
  insights: mockInsights.map((i) => ({
    id: i.id,
    title: i.title,
    severity: i.severity,
    confidence: i.confidence,
    target_metric: i.targetMetric,
  })),
  recommendations: mockRecommendations.map((r) => ({
    id: r.id,
    action: r.action,
    insight_id: r.insightId,
  })),
};
