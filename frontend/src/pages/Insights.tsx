import { useState } from "react";
import { motion } from "motion/react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CheckCircle2, Clock, Download, FileText, Quote, TrendingUp, ZoomIn } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { MockModeBanner } from "@/components/common/MockModeBanner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Severity, Visualization } from "@/types";

const severityTone: Record<Severity, string> = {
  critical: "border-destructive/40 bg-destructive/12 text-destructive",
  high: "border-warning/40 bg-warning/12 text-warning",
  medium: "border-info/40 bg-info/12 text-info",
  low: "border-success/40 bg-success/12 text-success",
};

const axis = { stroke: "var(--muted-foreground)", fontSize: 11 };
const tooltipStyle = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  color: "var(--popover-foreground)",
  fontSize: 12,
};

function MiniChart({ viz, height = 180 }: { viz: Visualization; height?: number }) {
  const common = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
      <XAxis dataKey="label" tick={axis} tickLine={false} axisLine={false} />
      <YAxis tick={axis} tickLine={false} axisLine={false} width={38} />
      <RTooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--muted)", opacity: 0.25 }} />
    </>
  );
  return (
    <ResponsiveContainer width="100%" height={height}>
      {viz.kind === "line" ? (
        <LineChart data={viz.data}>
          {common}
          <Line type="monotone" dataKey="value" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} />
        </LineChart>
      ) : viz.kind === "area" ? (
        <AreaChart data={viz.data}>
          {common}
          <Area type="monotone" dataKey="value" stroke="var(--chart-2)" fill="var(--chart-2)" fillOpacity={0.18} strokeWidth={2} />
        </AreaChart>
      ) : (
        <BarChart data={viz.data}>
          {common}
          <Bar dataKey="value" fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}

export function Insights() {
  const { insights, recommendations, visualizations, profile, mockMode, pipelineDurationMs, lastRunAt } = useStore();
  const [lightbox, setLightbox] = useState<Visualization | null>(null);

  return (
    <div>
      {mockMode && <MockModeBanner context="this executive report" />}

      <PageHeader
        eyebrow="Executive Insights"
        title="Revenue & Data Quality Briefing"
        description={`Synthesized by the Executive Insight Agent from verified pipeline output for ${profile.filename}.`}
        actions={
          <>
            <Button variant="secondary" onClick={() => toast.success("Download started", { description: "report.html" })}>
              <FileText className="size-4" aria-hidden />
              HTML Report
            </Button>
            <Button
              className="bg-[image:var(--gradient-primary)] text-primary-foreground shadow-glow"
              onClick={() => toast.success("Download started", { description: "report.pdf" })}
            >
              <Download className="size-4" aria-hidden />
              PDF Report
            </Button>
          </>
        }
      />

      <div className="glass mb-8 flex flex-wrap items-center gap-x-8 gap-y-3 rounded-xl px-5 py-4 shadow-elegant">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-success" aria-hidden />
          <span className="text-sm font-medium">Report status</span>
          <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
            OK
          </Badge>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="size-4" aria-hidden />
          Generated {new Date(lastRunAt).toLocaleString()}
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <TrendingUp className="size-4" aria-hidden />
          Pipeline duration{" "}
          <span className="font-mono text-foreground tabular-nums">{(pipelineDurationMs / 1000).toFixed(1)}s</span>
        </div>
      </div>

      <section aria-labelledby="insights-h" className="mb-10">
        <h3 id="insights-h" className="mb-4 text-lg font-semibold tracking-tight">
          Key insights
        </h3>
        <div className="grid gap-4 lg:grid-cols-2">
          {insights.map((ins, i) => (
            <motion.article
              key={ins.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.06 }}
              className="glass flex flex-col rounded-xl p-5 shadow-elegant transition-colors hover:border-primary/30"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className={cn("capitalize", severityTone[ins.severity])}>
                  {ins.severity}
                </Badge>
                <Badge variant="outline" className="border-border text-muted-foreground">
                  {ins.confidence}% confidence
                </Badge>
                <Badge variant="outline" className="border-accent/40 bg-accent/10 font-mono text-[10px] text-accent">
                  {ins.targetMetric}
                </Badge>
                <span className="ml-auto font-mono text-xs text-muted-foreground">{ins.id}</span>
              </div>
              <h4 className="mt-3 text-base font-semibold leading-snug">{ins.title}</h4>
              <p className="mt-2 flex-1 text-sm text-muted-foreground">{ins.explanation}</p>
              <div className="mt-4 rounded-lg border-l-2 border-accent bg-surface-2/50 p-3">
                <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
                  <Quote className="size-3" aria-hidden />
                  Verbatim evidence
                </p>
                <p className="font-mono text-xs leading-relaxed text-foreground">{ins.evidence}</p>
              </div>
            </motion.article>
          ))}
        </div>
      </section>

      <section aria-labelledby="recs-h" className="mb-10">
        <h3 id="recs-h" className="mb-4 text-lg font-semibold tracking-tight">
          Strategic recommendations
        </h3>
        <Card className="glass border-border bg-transparent shadow-elegant">
          <CardContent className="divide-y divide-border p-0">
            {recommendations.map((rec) => (
              <div key={rec.id} className="flex gap-4 p-5">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/12 font-mono text-xs font-semibold text-primary">
                  {rec.id}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={cn("capitalize", severityTone[rec.severity])}>
                      {rec.severity} priority
                    </Badge>
                    <a
                      href={`#${rec.insightId}`}
                      className="font-mono text-[11px] text-accent underline-offset-4 hover:underline"
                    >
                      related · {rec.insightId}
                    </a>
                  </div>
                  <p className="mt-2 text-sm font-medium">{rec.action}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground/80">Expected impact:</span> {rec.impact}
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="viz-h">
        <h3 id="viz-h" className="mb-1 text-lg font-semibold tracking-tight">
          Generated visualizations
        </h3>
        <p className="mb-4 text-sm text-muted-foreground">Charts produced by the sandboxed analysis code.</p>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visualizations.map((viz, i) => (
            <motion.figure
              key={viz.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.05 }}
              className="group glass overflow-hidden rounded-xl p-4 shadow-elegant transition-colors hover:border-primary/30"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <figcaption className="truncate text-sm font-medium">{viz.title}</figcaption>
                  <p className="truncate text-xs text-muted-foreground">{viz.description}</p>
                </div>
                <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Button variant="ghost" size="icon" aria-label={`Expand ${viz.title}`} onClick={() => setLightbox(viz)}>
                    <ZoomIn className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Download ${viz.title}`}
                    onClick={() => toast.success("Chart downloaded", { description: `${viz.title}.png` })}
                  >
                    <Download className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="mt-3 transition-transform duration-300 group-hover:scale-[1.02]">
                <MiniChart viz={viz} />
              </div>
              <Separator className="my-3" />
              <p className="font-mono text-[10px] text-muted-foreground">linked insight · {viz.insightId}</p>
            </motion.figure>
          ))}
        </div>
      </section>

      <Dialog open={!!lightbox} onOpenChange={(o) => !o && setLightbox(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{lightbox?.title}</DialogTitle>
            <CardDescription>{lightbox?.description}</CardDescription>
          </DialogHeader>
          {lightbox && <MiniChart viz={lightbox} height={380} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
