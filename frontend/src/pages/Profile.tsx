import { useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  ArrowUpDown,
  Columns3,
  Database,
  Download,
  ExternalLink,
  Gauge,
  Maximize2,
  Rows3,
  Search,
} from "lucide-react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
} from "recharts";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { MockModeBanner } from "@/components/common/MockModeBanner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ColumnStat } from "@/types";
import { toast } from "sonner";
import { downloadReport } from "@/services/api";


const typeTone: Record<ColumnStat["type"], string> = {
  numeric: "border-primary/40 bg-primary/10 text-primary",
  categorical: "border-accent/40 bg-accent/10 text-accent",
  datetime: "border-info/40 bg-info/10 text-info",
  boolean: "border-success/40 bg-success/10 text-success",
  other: "border-border bg-secondary text-muted-foreground",
};

const chartColors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

type SortKey = keyof Pick<ColumnStat, "name" | "type" | "missing" | "distinct">;

import { mockProfile } from "@/data/mock";

/** Trigger a blob-based download (works cross-origin, unlike `<a download>`). */
async function triggerDownload(
  url: string,
  filename: string,
  setDownloading: (v: boolean) => void,
) {
  if (!url) {
    toast.error("No report available — run a pipeline first.");
    return;
  }
  setDownloading(true);
  try {
    await downloadReport(url, filename);
    toast.success("Download complete!");
  } catch (err) {
    toast.error("Download failed", {
      description: err instanceof Error ? err.message : "Unknown error",
    });
  } finally {
    setDownloading(false);
  }
}

export function Profile() {
  const store = useStore();
  const profile = store.profile || mockProfile;
  const mockMode = store.mockMode;
  const columnStats = profile.columnStats || mockProfile.columnStats;
  const profileReportUrl = store.profileReportUrl;
  const reportUrl = store.reportUrl;
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [fullscreen, setFullscreen] = useState(false);
  const [reportTab, setReportTab] = useState<"overview" | "sweetviz">("overview");
  const [downloading, setDownloading] = useState(false);

  const donut = useMemo(
    () =>
      [
        { name: "Numeric", value: profile.numeric },
        { name: "Categorical", value: profile.categorical },
        { name: "Datetime", value: profile.datetime },
        { name: "Boolean", value: profile.boolean },
        { name: "Other", value: profile.other },
      ].filter((d) => (d.value ?? 0) > 0),
    [profile],
  );

  const rows = useMemo(() => {
    const filtered = (columnStats || []).filter((c) =>
      c.name.toLowerCase().includes(query.trim().toLowerCase()),
    );
    return [...filtered].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [columnStats, query, sort]);

  function toggleSort(key: SortKey) {
    setSort((s) => ({ key, dir: s.key === key && s.dir === "asc" ? "desc" : "asc" }));
  }

  // Real profile stats from backend
  const missingValues: Record<string, number> = profile.missingValues || {};
  const totalMissing = Object.values(missingValues).reduce((a, b) => a + Number(b), 0);
  const totalCells = (profile.rows || 0) * (profile.columns || 1);
  const missingPct = totalCells > 0 ? ((totalMissing / totalCells) * 100).toFixed(2) : "0.00";
  const duplicates = profile.duplicates ?? 0;
  const constantColumns = (profile.constantColumns || []) as string[];
  const highCardColumns = (profile.highCardinalityColumns || []) as string[];

  // Sweetviz / profile report iframe
  const activeReportUrl = profileReportUrl || reportUrl;
  const profileFilename = profile.filename || "dataset";

  const sweetvizContent = activeReportUrl ? (
    <div className="relative w-full" style={{ height: "70vh" }}>
      <iframe
        src={activeReportUrl}
        className="h-full w-full rounded-lg border-0"
        title={`Sweetviz Report — ${profileFilename}`}
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  ) : (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="text-sm font-semibold">Sweetviz Report · {profileFilename}</p>
          <p className="text-xs text-muted-foreground">Run a pipeline to generate the report</p>
        </div>
        <Badge variant="outline" className="border-warning/40 bg-warning/10 text-warning">
          No report yet
        </Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { k: "Rows", v: (profile.rows || 0).toLocaleString() },
          { k: "Columns", v: String(profile.columns || 0) },
          { k: "Duplicates", v: String(duplicates) },
          { k: "Missing cells", v: `${totalMissing} (${missingPct}%)` },
          { k: "Numeric features", v: String(profile.numeric || 0) },
          { k: "Categorical features", v: String(profile.categorical || 0) },
        ].map((s) => (
          <div key={s.k} className="rounded-lg border border-border bg-surface/40 p-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{s.k}</p>
            <p className="mt-1 font-mono text-lg tabular-nums">{s.v}</p>
          </div>
        ))}
      </div>
      {columnStats.length > 0 && (
        <div className="space-y-2">
          {columnStats.slice(0, 6).map((c) => (
            <div key={c.name} className="flex items-center gap-3">
              <span className="w-40 shrink-0 truncate font-mono text-xs text-muted-foreground">{c.name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-[image:var(--gradient-primary)]"
                  style={{ width: `${Math.min(100, ((c.distinct ?? 0) / Math.max(profile.rows || 1, 1)) * 100 + 6)}%` }}
                />
              </div>
              <span className="w-16 text-right font-mono text-xs tabular-nums">{c.distinct ?? "—"}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div>
      {mockMode && <MockModeBanner context="this dataset profile" />}
      <PageHeader
        eyebrow="Dataset Profile & EDA"
        title={profileFilename}
        description="Automated exploratory analysis produced by the Profiler Agent, with column-level statistics and quality signals."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Rows3} label="Total Rows" value={(profile.rows || 0).toLocaleString()} hint="Ingested records" delay={0} />
        <MetricCard icon={Columns3} label="Total Columns" value={String(profile.columns || 0)} hint="Detected features" tone="accent" delay={0.05} />
        <MetricCard
          icon={Gauge}
          label="Data Quality Score"
          value={`${profile.qualityScore || 0}%`}
          hint="Completeness · validity · consistency"
          tone="success"
          delay={0.1}
        />
        <MetricCard
          icon={Database}
          label="Numeric vs Categorical"
          value={`${profile.numeric || 0} / ${profile.categorical || 0}`}
          hint="Feature composition"
          tone="warning"
          delay={0.15}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        <Card className="glass border-border bg-transparent shadow-elegant">
          <CardHeader>
            <CardTitle className="text-base">Column Classification</CardTitle>
            <CardDescription>Distribution of detected column types.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="relative h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={donut} dataKey="value" nameKey="name" innerRadius={68} outerRadius={98} paddingAngle={3} stroke="none">
                    {donut.map((_, i) => (
                      <Cell key={i} fill={chartColors[i % chartColors.length]} />
                    ))}
                  </Pie>
                  <RTooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      color: "var(--popover-foreground)",
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-x-0 top-[42%] -translate-y-1/2 text-center">
                <p className="font-mono text-3xl font-semibold tabular-nums">{profile.columns || 0}</p>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">columns</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass border-border bg-transparent shadow-elegant">
          <CardHeader className="gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base">Column Directory</CardTitle>
              <CardDescription>Search and sort every detected column.</CardDescription>
            </div>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search columns…"
                aria-label="Search columns"
                className="pl-9"
              />
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-[360px] overflow-auto rounded-lg border border-border">
              <Table>
                <TableHeader className="sticky top-0 z-10 bg-surface-2/90 backdrop-blur">
                  <TableRow>
                    {([
                      ["name", "Column"],
                      ["type", "Type"],
                      ["missing", "Missing"],
                      ["distinct", "Distinct"],
                    ] as [SortKey, string][]).map(([key, label]) => (
                      <TableHead key={key}>
                        <button
                          onClick={() => toggleSort(key)}
                          className="inline-flex items-center gap-1 text-xs hover:text-foreground"
                        >
                          {label}
                          <ArrowUpDown className="size-3" aria-hidden />
                        </button>
                      </TableHead>
                    ))}
                    <TableHead className="text-xs">Mean</TableHead>
                    <TableHead className="text-xs">Min</TableHead>
                    <TableHead className="text-xs">Max</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                        {columnStats.length === 0 ? "Run a pipeline to populate column stats." : `No columns match "${query}".`}
                      </TableCell>
                    </TableRow>
                  )}
                  {rows.map((c) => (
                    <TableRow key={c.name}>
                      <TableCell className="font-mono text-xs">{c.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[10px] capitalize", typeTone[c.type])}>
                          {c.type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "font-mono text-xs tabular-nums",
                            c.missing > 0 ? "text-warning" : "text-muted-foreground",
                          )}
                        >
                          {c.missing}
                        </span>
                      </TableCell>
                      <TableCell className="font-mono text-xs tabular-nums">{c.distinct}</TableCell>
                      <TableCell className="font-mono text-xs tabular-nums">{c.mean != null ? Number(c.mean).toFixed(3) : "—"}</TableCell>
                      <TableCell className="font-mono text-xs tabular-nums">{c.min != null ? c.min : "—"}</TableCell>
                      <TableCell className="font-mono text-xs tabular-nums">{c.max != null ? c.max : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mt-6">
        <Tabs value={reportTab} onValueChange={(v) => setReportTab(v as any)}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="sweetviz">Sweetviz Report</TabsTrigger>
            </TabsList>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { setReportTab("sweetviz"); setFullscreen(true); }}
                disabled={!activeReportUrl}
              >
                <Maximize2 className="size-3.5" aria-hidden />
                Fullscreen
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!activeReportUrl || downloading}
                onClick={() => {
                  if (activeReportUrl) window.open(activeReportUrl, "_blank");
                  else toast.error("No report available — run a pipeline first.");
                }}
              >
                <ExternalLink className="size-3.5" aria-hidden />
                Open report
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!activeReportUrl || downloading}
                onClick={() =>
                  void triggerDownload(
                    activeReportUrl!,
                    `${profileFilename.replace(/\.csv$/i, "")}_profile_report.html`,
                    setDownloading,
                  )
                }
              >
                {downloading ? (
                  <><span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />Downloading…</>
                ) : (
                  <><Download className="size-3.5" aria-hidden />HTML Report</>
                )}
              </Button>
            </div>
          </div>

          <TabsContent value="overview" className="mt-4">
            <Card className="glass border-border bg-transparent">
              <CardContent className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  {
                    k: "Duplicate rows",
                    v: String(duplicates),
                    tone: duplicates === 0 ? "text-success" : "text-warning",
                  },
                  {
                    k: "Missing cells",
                    v: totalMissing > 0 ? `${totalMissing} (${missingPct}%)` : "0 (0.00%)",
                    tone: totalMissing > 0 ? "text-warning" : "text-success",
                  },
                  {
                    k: "Constant columns",
                    v: String(constantColumns.length),
                    tone: constantColumns.length === 0 ? "text-success" : "text-warning",
                  },
                  {
                    k: "High-cardinality",
                    v: String(highCardColumns.length),
                    tone: highCardColumns.length === 0 ? "text-success" : "text-info",
                  },
                ].map((s) => (
                  <div key={s.k} className="rounded-lg border border-border bg-surface/40 p-4">
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{s.k}</p>
                    <p className={cn("mt-1 font-mono text-lg tabular-nums", s.tone)}>{s.v}</p>
                  </div>
                ))}
              </CardContent>
              {Object.keys(missingValues).length > 0 && (
                <CardContent className="border-t border-border pt-4">
                  <p className="mb-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Columns with missing values</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(missingValues).map(([col, count]) => (
                      <Badge key={col} variant="outline" className="border-warning/40 bg-warning/10 text-warning font-mono text-[11px]">
                        {col}: {count} null{Number(count) !== 1 ? "s" : ""}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="sweetviz" className="mt-4">
            <Card className="glass overflow-hidden border-border bg-transparent">
              {sweetvizContent}
            </Card>
          </TabsContent>
        </Tabs>
      </motion.div>

      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="max-h-[95vh] max-w-7xl overflow-hidden p-0">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>Sweetviz Report — {profileFilename}</DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-6" style={{ height: "82vh" }}>
            {activeReportUrl ? (
              <iframe
                src={activeReportUrl}
                className="h-full w-full rounded-lg border border-border"
                title={`Sweetviz Report fullscreen — ${profileFilename}`}
                sandbox="allow-scripts allow-same-origin"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Run a pipeline to generate a Sweetviz report.
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
