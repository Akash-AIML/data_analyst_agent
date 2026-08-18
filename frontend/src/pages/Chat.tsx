import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Bot, CornerDownLeft, Loader2, RotateCcw, ShieldCheck, User, WifiOff } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { MockModeBanner } from "@/components/common/MockModeBanner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { llmModels, useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";
import { toast } from "sonner";

const API_BASE =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) || "http://localhost:8000";

const suggestions = [
  { label: "Summarize the key takeaways", key: "takeaways" },
  { label: "Which region has the highest sales?", key: "region" },
  { label: "Are there data quality issues?", key: "quality" },
  { label: "List all features / columns", key: "features" },
];

/** Minimal, safe renderer for the bold / bullet / quote markdown used in replies. */
function RichText({ content }: { content: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {content.split("\n").map((line, i) => {
        if (!line.trim()) return null;
        const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, j) => {
          if (p.startsWith("**")) return <strong key={j} className="font-semibold text-foreground">{p.slice(2, -2)}</strong>;
          if (p.startsWith("`")) return <code key={j} className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[11px] text-accent">{p.slice(1, -1)}</code>;
          return <span key={j}>{p}</span>;
        });
        if (line.startsWith(">"))
          return (
            <p key={i} className="border-l-2 border-accent bg-surface-2/50 py-2 pl-3 text-xs text-muted-foreground">
              {parts}
            </p>
          );
        if (line.startsWith("- "))
          return (
            <p key={i} className="flex gap-2 pl-1">
              <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
              <span>{parts}</span>
            </p>
          );
        return <p key={i}>{parts}</p>;
      })}
    </div>
  );
}

export function Chat() {
  const store = useStore();
  const chat = store.chat || [];
  const appendChat = store.appendChat || (() => {});
  const clearChat = store.clearChat || (() => {});
  const mockMode = store.mockMode;
  const model = store.model;
  const profile = store.profile;
  const insights = store.insights || [];
  const recommendations = store.recommendations || [];
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat, thinking]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || thinking) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
    };
    appendChat(userMsg);
    setInput("");
    setThinking(true);

    const started = Date.now();

    // Build grounding context from live store state
    const rawDescriptiveStats = profile?.descriptive_stats || profile?.descriptiveStats || {};
    const columnsList = (profile?.columnStats || []).map((c) => c.name);
    const columnStats = (profile?.columnStats || []).map((c) => {
      const rawCol = rawDescriptiveStats[c.name] || {};
      return {
        name: c.name,
        type: c.type,
        mean: c.mean ?? rawCol.mean ?? null,
        median: c.median ?? rawCol.median ?? null,
        std: c.std ?? rawCol.std ?? null,
        mode: c.mode ?? rawCol.mode ?? null,
        min: c.min ?? rawCol.min ?? null,
        max: c.max ?? rawCol.max ?? null,
        missing: c.missing,
        distinct: c.distinct,
      };
    });
    const chatContext = {
      filename: profile?.filename ?? "dataset.csv",
      rows: profile?.rows ?? 0,
      columns: profile?.columns ?? 0,
      quality_score: profile?.qualityScore ?? 0,
      columns_list: columnsList,
      column_stats: columnStats,
      descriptive_stats: rawDescriptiveStats,
      insights: insights.map((ins) => ({
        title: ins.title,
        explanation: ins.explanation,
        evidence: ins.evidence,
        severity: ins.severity,
        confidence: ins.confidence,
        target_metric: ins.targetMetric,
      })),
      recommendations: recommendations.map((rec) => ({
        action: rec.action,
        impact: rec.impact,
        severity: rec.severity,
      })),
    };

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 60000);
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, context: chatContext }),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      appendChat({
        id: data.id || `a-${Date.now()}`,
        role: "assistant",
        content: data.content || "(no response)",
        timestamp: new Date().toISOString(),
        latencyMs: data.latencyMs ?? Date.now() - started,
        grounded: data.grounded ?? true,
      });
    } catch (err) {
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      const errMsg = isAbort ? "Request timed out." : (err instanceof Error ? err.message : "Unknown error");

      // Show toast for transient errors
      toast.error("Chat failed", { description: errMsg });

      // Inline fallback: synthesize an answer from store state
      let fallback = "";
      if (columnsList.length) {
        const featureList = columnsList.join(", ");
        if (trimmed.toLowerCase().includes("feature") || trimmed.toLowerCase().includes("column")) {
          fallback = `**${profile?.filename}** has **${profile?.columns}** columns:\n- ${columnsList.join("\n- ")}`;
        } else if (insights.length) {
          fallback = `**Top insights from ${profile?.filename}:**\n` + insights.slice(0, 4).map(
            (ins) => `- **${ins.title}** — ${ins.explanation}`
          ).join("\n");
        } else {
          fallback = `Dataset **${profile?.filename}** · ${profile?.rows?.toLocaleString()} rows · ${profile?.columns} columns.\nFeatures: ${featureList}.\n\n> Backend is unreachable — run a pipeline first.`;
        }
      } else {
        fallback = `> Backend unavailable (${errMsg}). Run a pipeline on the Launcher page first, then try again.`;
      }

      appendChat({
        id: `a-${Date.now()}`,
        role: "assistant",
        content: fallback,
        timestamp: new Date().toISOString(),
        latencyMs: Date.now() - started,
        grounded: false,
      });
    } finally {
      setThinking(false);
    }
  }

  const modelLabel = llmModels.find((m) => m.id === model)?.slug ?? model;

  return (
    <div className="flex min-h-[calc(100vh-8rem)] flex-col">
      {mockMode && <MockModeBanner context="this conversation" />}
      <PageHeader
        eyebrow="Analyst Chat"
        title="Ask the grounded analyst"
        description="Every answer is constrained to the verified pipeline output — no speculation beyond the active report."
        actions={
          <Button variant="secondary" onClick={clearChat}>
            <RotateCcw className="size-4" aria-hidden />
            Reset thread
          </Button>
        }
      />

      <div className="grid flex-1 gap-6 lg:grid-cols-[1fr_300px]">
        <Card className="glass flex min-h-[520px] flex-col border-border bg-transparent shadow-elegant">
          <CardContent className="flex-1 space-y-6 overflow-y-auto p-6">
            {chat.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}
              >
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-lg border",
                    m.role === "user"
                      ? "border-primary/30 bg-primary/12 text-primary"
                      : m.grounded
                        ? "border-accent/30 bg-accent/12 text-accent"
                        : "border-orange-400/30 bg-orange-400/12 text-orange-400",
                  )}
                  aria-hidden
                >
                  {m.role === "user" ? <User className="size-4" /> : m.grounded ? <Bot className="size-4" /> : <WifiOff className="size-4" />}
                </span>
                <div className={cn("max-w-[80%] min-w-0", m.role === "user" && "text-right")}>
                  {m.role === "user" ? (
                    <p className="inline-block rounded-xl rounded-tr-sm bg-primary px-4 py-2.5 text-left text-sm text-primary-foreground">
                      {m.content}
                    </p>
                  ) : (
                    <RichText content={m.content} />
                  )}
                  <p className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    {m.role === "assistant" && m.grounded && (
                      <span className="inline-flex items-center gap-1 text-success">
                        <ShieldCheck className="size-3" aria-hidden />
                        grounded
                      </span>
                    )}
                    {m.role === "assistant" && !m.grounded && (
                      <span className="inline-flex items-center gap-1 text-orange-400">
                        <WifiOff className="size-3" aria-hidden />
                        offline
                      </span>
                    )}
                    {m.latencyMs != null && <span className="font-mono">{m.latencyMs}ms</span>}
                  </p>
                </div>
              </motion.div>
            ))}

            {thinking && (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="grid size-8 place-items-center rounded-lg border border-accent/30 bg-accent/12 text-accent" aria-hidden>
                  <Bot className="size-4" />
                </span>
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  Calling the LLM with pipeline context…
                </span>
              </div>
            )}
            <div ref={endRef} />
          </CardContent>

          <div className="border-t border-border p-4">
            <div className="mb-3 flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s.key}
                  onClick={() => void send(s.label)}
                  disabled={thinking}
                  className="rounded-full border border-border bg-surface-2/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-40"
                >
                  {s.label}
                </button>
              ))}
            </div>
            <div className="relative">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send(input);
                  }
                }}
                aria-label="Message the analyst"
                placeholder={`Ask about ${profile?.filename ?? "dataset.csv"}…`}
                className="min-h-[88px] resize-none pr-28"
              />
              <Button
                onClick={() => void send(input)}
                disabled={!input.trim() || thinking}
                className="absolute bottom-3 right-3 bg-[image:var(--gradient-primary)] text-primary-foreground shadow-glow"
                size="sm"
              >
                Send
                <CornerDownLeft className="size-3.5" aria-hidden />
              </Button>
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              Enter to send · Shift + Enter for a new line · answering with{" "}
              <span className="font-mono text-foreground/70">{modelLabel}</span>
            </p>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="glass border-border bg-transparent">
            <CardHeader>
              <CardTitle className="text-sm">Grounding context</CardTitle>
              <CardDescription>What the analyst can see.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {[
                ["Dataset", profile?.filename ?? "dataset.csv"],
                ["Rows", profile?.rows ? profile.rows.toLocaleString() : "—"],
                ["Columns", profile?.columns ? String(profile.columns) : "—"],
                ["Quality", profile?.qualityScore ? `${profile.qualityScore}%` : "—"],
                ["Features", profile?.columnStats?.length ? String(profile.columnStats.length) : "—"],
                ["Insights", String(insights.length)],
                ["Model", modelLabel],
              ].map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="truncate font-mono text-xs">{v}</span>
                </div>
              ))}
              <Badge variant="outline" className="w-full justify-center border-success/40 bg-success/10 text-success">
                Retrieval scoped to report
              </Badge>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
