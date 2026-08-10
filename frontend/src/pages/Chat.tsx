import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Bot, CornerDownLeft, Loader2, RotateCcw, ShieldCheck, User } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { MockModeBanner } from "@/components/common/MockModeBanner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { mockChatReplies } from "@/data/mock";
import { llmModels, useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

const suggestions = [
  { label: "Summarize the key takeaways", key: "takeaways" },
  { label: "Which region has the highest sales?", key: "region" },
  { label: "Are there data quality issues?", key: "quality" },
  { label: "What should we do next quarter?", key: "default" },
];

function pickReply(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("takeaway") || t.includes("summar")) return mockChatReplies["takeaways"] ?? "";
  if (t.includes("region") || t.includes("highest") || t.includes("sales")) return mockChatReplies["region"] ?? "";
  if (t.includes("quality") || t.includes("missing") || t.includes("clean")) return mockChatReplies["quality"] ?? "";
  return mockChatReplies["default"] ?? "";
}

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
  const { chat, appendChat, clearChat, mockMode, model, profile } = useStore();
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat, thinking]);

  useEffect(() => () => clearTimeout(timer.current), []);

  function send(text: string) {
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
    timer.current = setTimeout(() => {
      appendChat({
        id: `a-${Date.now()}`,
        role: "assistant",
        content: pickReply(trimmed),
        timestamp: new Date().toISOString(),
        latencyMs: Date.now() - started,
        grounded: true,
      });
      setThinking(false);
    }, 1100);
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
                      : "border-accent/30 bg-accent/12 text-accent",
                  )}
                  aria-hidden
                >
                  {m.role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
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
                  Reading the verified report…
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
                  onClick={() => send(s.label)}
                  className="rounded-full border border-border bg-surface-2/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
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
                    send(input);
                  }
                }}
                aria-label="Message the analyst"
                placeholder={`Ask about ${profile.filename}…`}
                className="min-h-[88px] resize-none pr-28"
              />
              <Button
                onClick={() => send(input)}
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
                ["Dataset", profile.filename],
                ["Rows", profile.rows.toLocaleString()],
                ["Columns", String(profile.columns)],
                ["Quality", `${profile.qualityScore}%`],
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
