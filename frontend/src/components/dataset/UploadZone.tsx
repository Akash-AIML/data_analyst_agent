import { useCallback, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { FileSpreadsheet, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_BYTES = 50 * 1024 * 1024;

export interface SelectedFile {
  name: string;
  size: number;
  rows: number | null;
  preview: { headers: string[]; rows: string[][] } | null;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function UploadZone({
  file,
  onSelect,
  onClear,
}: {
  file: SelectedFile | null;
  onSelect: (f: SelectedFile) => void;
  onClear: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [parsing, setParsing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (f: File) => {
      if (!f.name.toLowerCase().endsWith(".csv") && f.type !== "text/csv") {
        toast.error("Unsupported file", { description: "Please upload a .csv file." });
        return;
      }
      if (f.size > MAX_BYTES) {
        toast.error("File too large", { description: "Maximum supported size is 50MB." });
        return;
      }
      setParsing(true);
      const reader = new FileReader();
      reader.onload = () => {
        const text = String(reader.result ?? "");
        const lines = text.split(/\r?\n/).filter(Boolean);
        const headers = lines[0]?.split(",").map((h) => h.trim()) ?? [];
        const rows = lines.slice(1, 6).map((l) => l.split(","));
        setParsing(false);
        onSelect({
          name: f.name,
          size: f.size,
          rows: Math.max(lines.length - 1, 0),
          preview: headers.length ? { headers, rows } : null,
        });
        toast.success("CSV ready", { description: `${f.name} loaded successfully.` });
      };
      reader.onerror = () => {
        setParsing(false);
        toast.error("Could not read file");
      };
      reader.readAsText(f.slice(0, 200_000));
    },
    [onSelect],
  );

  return (
    <div>
      <AnimatePresence mode="wait">
        {!file ? (
          <motion.div
            key="drop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const f = e.dataTransfer.files?.[0];
              if (f) handleFile(f);
            }}
            className={cn(
              "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-all",
              dragging
                ? "border-primary bg-primary/[0.07] shadow-glow"
                : "border-border bg-surface/40 hover:border-primary/40 hover:bg-surface/60",
            )}
          >
            <motion.div
              animate={{ scale: dragging ? 1.08 : 1, y: dragging ? -4 : 0 }}
              transition={{ type: "spring", stiffness: 260, damping: 18 }}
              className="grid size-14 place-items-center rounded-2xl bg-[image:var(--gradient-primary)] shadow-glow"
            >
              <UploadCloud className="size-6 text-primary-foreground" aria-hidden />
            </motion.div>
            <p className="mt-5 text-lg font-medium">Drop your CSV here</p>
            <p className="mt-1 text-sm text-muted-foreground">or browse from your computer</p>
            <Button
              variant="secondary"
              className="mt-5"
              onClick={() => inputRef.current?.click()}
              disabled={parsing}
            >
              {parsing ? "Reading file…" : "Browse files"}
            </Button>
            <p className="mt-4 text-xs text-muted-foreground">CSV files up to 50MB</p>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="Upload CSV file"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
                e.target.value = "";
              }}
            />
          </motion.div>
        ) : (
          <motion.div
            key="file"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="glass rounded-2xl p-5"
          >
            <div className="flex items-start gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent/12 text-accent">
                <FileSpreadsheet className="size-5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{file.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatBytes(file.size)}
                  {file.rows !== null && ` · ${file.rows.toLocaleString()} rows detected`} · Ready to analyze
                </p>
              </div>
              <Button variant="ghost" size="icon" aria-label="Remove file" onClick={onClear}>
                <X className="size-4" />
              </Button>
            </div>

            {file.preview && file.preview.rows.length > 0 && (
              <div className="mt-5">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Preview · first 5 rows
                </p>
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-2/60">
                      <tr>
                        {file.preview.headers.map((h) => (
                          <th key={h} className="whitespace-nowrap px-3 py-2 font-medium text-muted-foreground">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {file.preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border">
                          {r.map((c, j) => (
                            <td key={j} className="whitespace-nowrap px-3 py-2">
                              {c}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
