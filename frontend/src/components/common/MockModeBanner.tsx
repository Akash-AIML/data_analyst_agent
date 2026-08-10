import { TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function MockModeBanner({ context }: { context: string }) {
  return (
    <div
      role="status"
      className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-warning/25 bg-warning/[0.07] px-4 py-3"
    >
      <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden />
      <p className="text-sm text-foreground">
        <span className="font-medium">Demo mode.</span>{" "}
        <span className="text-muted-foreground">
          The analysis backend isn&apos;t reachable, so {context} is rendered from realistic mock data.
        </span>
      </p>
      <Badge variant="outline" className="ml-auto border-warning/40 bg-warning/10 text-warning">
        Mock data
      </Badge>
    </div>
  );
}
