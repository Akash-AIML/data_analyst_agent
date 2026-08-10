import { AnimatePresence, motion } from "motion/react";
import { Check, CircleDashed, FileText, Loader2, Lightbulb, ScanSearch, Terminal, TriangleAlert, Workflow } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { PipelineStage } from "@/types";

const stageIcons: Record<string, typeof ScanSearch> = {
  profiling: ScanSearch,
  plan: Workflow,
  execute: Terminal,
  insight: Lightbulb,
  report: FileText,
};

export function PipelineProgress({ stages }: { stages: PipelineStage[] }) {
  const done = stages.filter((s) => s.status === "completed").length;
  const overall = Math.round((stages.reduce((acc, s) => acc + s.progress, 0) / (stages.length * 100)) * 100);

  return (
    <div className="glass rounded-xl p-5 shadow-elegant sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Live Pipeline Execution</h3>
          <p className="text-xs text-muted-foreground">
            {done} of {stages.length} stages complete
          </p>
        </div>
        <span className="font-mono text-2xl font-semibold tabular-nums text-accent">{overall}%</span>
      </div>
      <Progress value={overall} className="mb-6 h-1.5" />

      <ol className="space-y-3">
        {stages.map((stage, i) => {
          const Icon = stageIcons[stage.id] ?? CircleDashed;
          return (
            <motion.li
              key={stage.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
              className={cn(
                "flex gap-4 rounded-lg border p-4 transition-colors",
                stage.status === "running"
                  ? "border-primary/40 bg-primary/[0.06]"
                  : stage.status === "completed"
                    ? "border-success/25 bg-success/[0.04]"
                    : stage.status === "failed"
                      ? "border-destructive/35 bg-destructive/[0.06]"
                      : "border-border bg-surface/30",
              )}
            >
              <span
                className={cn(
                  "grid size-9 shrink-0 place-items-center rounded-lg",
                  stage.status === "completed"
                    ? "bg-success/15 text-success"
                    : stage.status === "running"
                      ? "bg-primary/15 text-primary"
                      : stage.status === "failed"
                        ? "bg-destructive/15 text-destructive"
                        : "bg-secondary text-muted-foreground",
                )}
              >
                <AnimatePresence mode="wait" initial={false}>
                  {stage.status === "completed" ? (
                    <motion.span key="c" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
                      <Check className="size-4" aria-hidden />
                    </motion.span>
                  ) : stage.status === "running" ? (
                    <Loader2 key="r" className="size-4 animate-spin" aria-hidden />
                  ) : stage.status === "failed" ? (
                    <TriangleAlert key="f" className="size-4" aria-hidden />
                  ) : (
                    <Icon key="p" className="size-4" aria-hidden />
                  )}
                </AnimatePresence>
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">
                    {i + 1}. {stage.title}
                  </p>
                  <Badge variant="outline" className="border-border text-[10px] text-muted-foreground">
                    {stage.subtitle}
                  </Badge>
                  <span className="ml-auto font-mono text-xs text-muted-foreground tabular-nums">
                    {stage.status === "completed"
                      ? `${(stage.durationMs / 1000).toFixed(1)}s`
                      : stage.status === "running"
                        ? "running…"
                        : "—"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{stage.description}</p>
                {stage.status !== "pending" && <Progress value={stage.progress} className="mt-3 h-1" />}
                <span className="sr-only">Status: {stage.status}</span>
              </div>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
