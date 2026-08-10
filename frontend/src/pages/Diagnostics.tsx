import { useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Coins,
  Copy,
  Cpu,
  WifiOff,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { MockModeBanner } from "@/components/common/MockModeBanner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { mockAgentState, mockLogs, mockTelemetry } from "@/data/mock";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { HealthStatus } from "@/types";

const healthMeta: Record<HealthStatus, { icon: typeof CheckCircle2; tone: string; label: string }> = {
  connected: { icon: CheckCircle2, tone: "text-success", label: "Connected" },
  degraded: { icon: AlertTriangle, tone: "text-warning", label: "Degraded" },
  offline: { icon: WifiOff, tone: "text-destructive", label: "Offline" },
};

export function Diagnostics() {
  const { health, mockMode, pipelineDurationMs } = useStore();
  const [open, setOpen] = useState<string | null>(mockLogs[0]?.id ?? null);

  const totals = useMemo(() => {
    const cost = mockTelemetry.reduce((a, t) => a + t.cost, 0);
    const tokens = mockTelemetry.reduce((a, t) => a + t.inputTokens + t.outputTokens, 0);
    const latency = mockTelemetry.reduce((a, t) => a + t.latencyMs, 0) / mockTelemetry.length;
    return { cost, tokens, latency };
  }, []);

  const stateJson = JSON.stringify(mockAgentState, null, 2);

  function copyJson() {
    void navigator.clipboard?.writeText(stateJson);
    toast.success("Agent state copied to clipboard");
  }

  return (
    <div>
      {mockMode && <MockModeBanner context="these diagnostics" />}
      <PageHeader
        eyebrow="Agent Diagnostics"
        title="System health & execution trace"
        description="Live service checks, sandbox execution logs with retries, and the raw agent state graph."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Clock} label="Pipeline Duration" value={`${(pipelineDurationMs / 1000).toFixed(1)}s`} hint="Last full run" delay={0} />
        <MetricCard icon={Cpu} label="Total Tokens" value={totals.tokens.toLocaleString()} hint="Input + output" tone="accent" delay={0.05} />
        <MetricCard icon={Activity} label="Avg LLM Latency" value={`${Math.round(totals.latency)}ms`} hint="Across 4 calls" tone="warning" delay={0.1} />
        <MetricCard icon={Coins} label="Estimated Cost" value={`$${totals.cost.toFixed(4)}`} hint="This run" tone="success" delay={0.15} />
      </div>

      <section className="mt-6">
        <h3 className="mb-3 text-lg font-semibold tracking-tight">Service health</h3>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {health.map((svc, i) => {
            const meta = healthMeta[svc.status];
            const Icon = meta.icon;
            return (
              <motion.div
                key={svc.name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="glass rounded-xl p-4 shadow-elegant"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{svc.name}</p>
                  <Icon className={cn("size-4", meta.tone)} aria-hidden />
                </div>
                <p className={cn("mt-1 text-xs", meta.tone)}>{meta.label}</p>
                <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span className="font-mono tabular-nums">{svc.latencyMs}ms</span>
                  <span>{svc.lastChecked}</span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </section>

      <Tabs defaultValue="logs" className="mt-8">
        <TabsList>
          <TabsTrigger value="logs">Execution Logs</TabsTrigger>
          <TabsTrigger value="telemetry">LLM Telemetry</TabsTrigger>
          <TabsTrigger value="state">Agent State</TabsTrigger>
        </TabsList>

        <TabsContent value="logs" className="mt-4 space-y-3">
          {mockLogs.map((log) => (
            <Collapsible
              key={log.id}
              open={open === log.id}
              onOpenChange={(o) => setOpen(o ? log.id : null)}
              className="glass overflow-hidden rounded-xl shadow-elegant"
            >
              <CollapsibleTrigger className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-surface-2/40">
                <ChevronRight
                  className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open === log.id && "rotate-90")}
                  aria-hidden
                />
                <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary">
                  {log.node}
                </Badge>
                <Badge variant="outline" className="border-border text-muted-foreground">
                  attempt {log.attempt}
                </Badge>
                <code className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">{log.snippet}</code>
                <span className="hidden font-mono text-xs tabular-nums text-muted-foreground sm:inline">
                  {log.durationMs}ms
                </span>
                {log.status === "success" ? (
                  <CheckCircle2 className="size-4 shrink-0 text-success" aria-label="Success" />
                ) : (
                  <XCircle className="size-4 shrink-0 text-destructive" aria-label="Failed" />
                )}
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="space-y-3 border-t border-border p-4">
                  <div>
                    <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Generated code</p>
                    <pre className="overflow-x-auto rounded-lg border border-border bg-surface/60 p-3 font-mono text-xs leading-relaxed">
                      {log.code}
                    </pre>
                  </div>
                  {log.stdout && (
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-success">stdout</p>
                      <pre className="overflow-x-auto rounded-lg border border-success/20 bg-success/5 p-3 font-mono text-xs leading-relaxed">
                        {log.stdout}
                      </pre>
                    </div>
                  )}
                  {log.stderr && (
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-destructive">stderr</p>
                      <pre className="overflow-x-auto rounded-lg border border-destructive/25 bg-destructive/5 p-3 font-mono text-xs leading-relaxed text-destructive">
                        {log.stderr}
                      </pre>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>
          ))}
        </TabsContent>

        <TabsContent value="telemetry" className="mt-4">
          <Card className="glass border-border bg-transparent shadow-elegant">
            <CardHeader>
              <CardTitle className="text-base">LLM call breakdown</CardTitle>
              <CardDescription>Token usage, latency and cost per agent task.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Task</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Input</TableHead>
                    <TableHead className="text-right">Output</TableHead>
                    <TableHead className="text-right">Latency</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockTelemetry.map((t) => (
                    <TableRow key={t.id}>
                      <TableCell className="text-sm font-medium">{t.task}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{t.model}</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">{t.inputTokens.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">{t.outputTokens.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">{t.latencyMs}ms</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums text-accent">${t.cost.toFixed(4)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell colSpan={4} className="text-sm font-semibold">
                      Total
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {mockTelemetry.reduce((a, t) => a + t.latencyMs, 0)}ms
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs font-semibold tabular-nums text-accent">
                      ${totals.cost.toFixed(4)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="state" className="mt-4">
          <Card className="glass border-border bg-transparent shadow-elegant">
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Raw agent state</CardTitle>
                <CardDescription>Serialized graph state after the final node.</CardDescription>
              </div>
              <Button variant="secondary" size="sm" onClick={copyJson}>
                <Copy className="size-3.5" aria-hidden />
                Copy JSON
              </Button>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[460px] overflow-auto rounded-lg border border-border bg-surface/60 p-4 font-mono text-xs leading-relaxed">
                {stateJson}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
