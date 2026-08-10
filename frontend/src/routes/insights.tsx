import { createFileRoute } from "@tanstack/react-router";
import { Insights } from "@/pages/Insights";

export const Route = createFileRoute("/insights")({
  head: () => ({
    meta: [
      { title: "Executive Insights — AI Data Analyst" },
      {
        name: "description",
        content:
          "Severity-ranked findings, verbatim evidence, strategic recommendations and generated charts from the analysis run.",
      },
      { property: "og:title", content: "Executive Insights — AI Data Analyst" },
      {
        property: "og:description",
        content: "An executive briefing synthesized from verified pipeline output.",
      },
    ],
  }),
  component: Insights,
});
