import { useState } from "react";
import { motion } from "motion/react";
import { useNavigate } from "@tanstack/react-router";
import { Rocket, Loader2, Wifi, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { UploadZone, type SelectedFile } from "@/components/dataset/UploadZone";
import { SampleDatasets } from "@/components/dataset/SampleDatasets";
import { PipelineConfigCard } from "@/components/pipeline/PipelineConfigCard";
import { PipelineProgress } from "@/components/pipeline/PipelineProgress";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useStore } from "@/lib/store";
import type { SampleDataset } from "@/types";

export function Launcher() {
  const { stages, pipelineStatus, runPipeline, mockMode, profile } = useStore();
  const [file, setFile] = useState<SelectedFile | null>(null);
  const navigate = useNavigate();
  const running = pipelineStatus === "running";

  function launch(filename: string, rows?: number | null) {
    runPipeline(filename);
    toast.success("Pipeline launched", {
      description: `${filename}${rows ? ` · ${rows.toLocaleString()} rows` : ""} queued through 5 agent stages.`,
      action: { label: "View insights", onClick: () => void navigate({ to: "/insights" }) },
    });
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Pipeline Launcher"
        title="AI Data Analyst"
        description="Upload a dataset and let the multi-agent pipeline profile, analyze, validate, and explain it."
        actions={
          <Badge
            variant="outline"
            className={
              mockMode
                ? "gap-1.5 border-warning/40 bg-warning/10 py-1.5 text-warning"
                : "gap-1.5 border-success/40 bg-success/10 py-1.5 text-success"
            }
          >
            {mockMode ? <WifiOff className="size-3.5" aria-hidden /> : <Wifi className="size-3.5" aria-hidden />}
            {mockMode ? "Backend offline — demo data" : "Backend connected"}
          </Badge>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-6">
          <UploadZone file={file} onSelect={setFile} onClear={() => setFile(null)} />

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Button
              size="lg"
              disabled={running}
              onClick={() => launch(file?.name ?? profile.filename, file?.rows)}
              className="group relative w-full overflow-hidden bg-[image:var(--gradient-primary)] py-6 text-base font-semibold text-primary-foreground shadow-glow transition-transform hover:scale-[1.01] disabled:opacity-70"
            >
              {running ? (
                <>
                  <Loader2 className="size-5 animate-spin" aria-hidden />
                  Running pipeline…
                </>
              ) : (
                <>
                  <Rocket className="size-5 transition-transform group-hover:-translate-y-0.5" aria-hidden />
                  Launch Analysis Pipeline
                </>
              )}
            </Button>
          </motion.div>

          <PipelineProgress stages={stages} />
        </div>

        <PipelineConfigCard />
      </div>

      <section aria-labelledby="samples">
        <h3 id="samples" className="mb-1 text-lg font-semibold tracking-tight">
          Sample datasets
        </h3>
        <p className="mb-5 text-sm text-muted-foreground">
          Start instantly with a curated dataset — one click runs the full agent pipeline.
        </p>
        <SampleDatasets
          disabled={running}
          onRun={(d: SampleDataset) => launch(d.filename, d.rows)}
        />
      </section>
    </div>
  );
}
