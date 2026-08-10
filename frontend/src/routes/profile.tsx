import { createFileRoute } from "@tanstack/react-router";
import { Profile } from "@/pages/Profile";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Dataset Profile & EDA — AI Data Analyst" },
      {
        name: "description",
        content:
          "Automated exploratory data analysis: row and column metrics, quality score, column directory and Sweetviz report.",
      },
      { property: "og:title", content: "Dataset Profile & EDA — AI Data Analyst" },
      {
        property: "og:description",
        content: "Column-level statistics, data quality scoring and an embedded profiling report.",
      },
    ],
  }),
  component: Profile,
});
