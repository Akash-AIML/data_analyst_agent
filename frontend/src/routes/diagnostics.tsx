import { createFileRoute } from "@tanstack/react-router";
import { Diagnostics } from "@/pages/Diagnostics";

export const Route = createFileRoute("/diagnostics")({
  head: () => ({
    meta: [
      { title: "Agent Diagnostics — AI Data Analyst" },
      {
        name: "description",
        content:
          "Service health checks, sandbox execution logs with retries, LLM telemetry and the raw agent state graph.",
      },
      { property: "og:title", content: "Agent Diagnostics — AI Data Analyst" },
      {
        property: "og:description",
        content: "Inspect system health, execution traces and token cost for every agent run.",
      },
    ],
  }),
  component: Diagnostics,
});
