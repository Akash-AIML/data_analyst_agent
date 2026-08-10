import { motion } from "motion/react";
import { Play, ShoppingCart, TrendingUp, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { sampleDatasets } from "@/data/mock";
import type { SampleDataset } from "@/types";

const icons = {
  sales: TrendingUp,
  hiring: Users,
  churn: ShoppingCart,
} as const;

export function SampleDatasets({
  onRun,
  disabled,
}: {
  onRun: (d: SampleDataset) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {sampleDatasets.map((d, i) => {
        const Icon = icons[d.icon];
        return (
          <motion.article
            key={d.id}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: i * 0.07 }}
            whileHover={{ y: -4 }}
            className="group glass flex flex-col rounded-xl p-5 shadow-elegant transition-colors hover:border-primary/35"
          >
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-lg bg-primary/12 text-primary transition-colors group-hover:bg-primary/20">
                <Icon className="size-5" aria-hidden />
              </span>
              <div>
                <h4 className="font-medium leading-tight">{d.name}</h4>
                <p className="text-[11px] text-muted-foreground">
                  ~{d.rows.toLocaleString()} rows · {d.columns} columns
                </p>
              </div>
            </div>
            <p className="mt-3 flex-1 text-sm text-muted-foreground">{d.description}</p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-4 w-full"
              disabled={disabled}
              onClick={() => onRun(d)}
            >
              <Play className="size-3.5" aria-hidden />
              Run Analysis
            </Button>
          </motion.article>
        );
      })}
    </div>
  );
}
