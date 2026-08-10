import { createFileRoute } from "@tanstack/react-router";
import { Chat } from "@/pages/Chat";

export const Route = createFileRoute("/chat")({
  head: () => ({
    meta: [
      { title: "Analyst Chat — AI Data Analyst" },
      {
        name: "description",
        content:
          "Ask questions about your dataset and get grounded answers constrained to the verified pipeline report.",
      },
      { property: "og:title", content: "Analyst Chat — AI Data Analyst" },
      {
        property: "og:description",
        content: "A grounded conversational analyst that cites evidence from your report.",
      },
    ],
  }),
  component: Chat,
});
