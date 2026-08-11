import { Sliders } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { useStore } from "@/lib/store";

function Row({
  label,
  value,
  hint,
  children,
}: {
  label: string;
  value: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="font-mono text-sm text-accent tabular-nums">{value}</span>
      </div>
      <div className="mt-3">{children}</div>
      <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

export function PipelineConfigCard() {
  const { config, setConfig } = useStore();
  const activeConfig = { maxRetries: 3, temperature: 0.1, timeout: 60, ...(config || {}) };

  return (
    <Card className="glass border-border bg-transparent shadow-elegant">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sliders className="size-4 text-primary" aria-hidden />
          Pipeline Configuration
        </CardTitle>
        <CardDescription>Tune retry behaviour, creativity, and execution limits.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Row label="Max Retries" value={String(activeConfig.maxRetries)} hint="Reflector attempts before a node is marked failed.">
          <Slider
            value={[activeConfig.maxRetries]}
            min={1}
            max={6}
            step={1}
            aria-label="Max retries"
            onValueChange={(v) => setConfig?.({ maxRetries: v[0] ?? activeConfig.maxRetries })}
          />
        </Row>
        <Separator />
        <Row label="Temperature" value={activeConfig.temperature.toFixed(2)} hint="Lower values keep analysis deterministic and grounded.">
          <Slider
            value={[activeConfig.temperature]}
            min={0}
            max={1}
            step={0.05}
            aria-label="Temperature"
            onValueChange={(v) => setConfig?.({ temperature: v[0] ?? activeConfig.temperature })}
          />
        </Row>
        <Separator />
        <Row label="Execution Timeout" value={`${activeConfig.timeout}s`} hint="Hard limit for sandboxed Python execution per node.">
          <Slider
            value={[activeConfig.timeout]}
            min={30}
            max={300}
            step={10}
            aria-label="Execution timeout in seconds"
            onValueChange={(v) => setConfig?.({ timeout: v[0] ?? activeConfig.timeout })}
          />
        </Row>
      </CardContent>
    </Card>
  );
}

