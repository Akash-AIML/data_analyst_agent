import { createFileRoute } from "@tanstack/react-router";
import { Launcher } from "@/pages/Launcher";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Pipeline Launcher — AI Data Analyst" },
      {
        name: "description",
        content:
          "Upload a dataset, configure the agents, and launch the profiling, code analysis and executive insight pipeline.",
      },
      { property: "og:title", content: "Pipeline Launcher — AI Data Analyst" },
      {
        property: "og:description",
        content: "Launch an autonomous multi-agent analysis run over your dataset in seconds.",
      },
    ],
  }),
  component: Launcher,
});
