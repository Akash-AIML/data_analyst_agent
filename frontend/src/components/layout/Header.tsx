import { Activity, Bell, Database, Settings } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { llmModels, useStore, type LlmModel } from "@/lib/store";

export function Header() {
  const { profile, model, setModel, mockMode } = useStore();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/70 px-4 backdrop-blur-xl lg:px-6">
      <div className="flex items-center gap-3">
        <div className="grid size-8 place-items-center rounded-lg bg-[image:var(--gradient-primary)] shadow-glow md:hidden">
          <Activity className="size-4 text-primary-foreground" aria-hidden />
        </div>
        <h1 className="text-sm font-semibold tracking-tight sm:text-base">AI Data Analyst Agent</h1>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="hidden items-center gap-2 rounded-full border border-border bg-surface/60 py-1.5 pl-3 pr-3.5 text-xs lg:flex">
          <Database className="size-3.5 text-accent" aria-hidden />
          <span className="font-medium">{profile.filename}</span>
          <span className="text-muted-foreground">{profile.rows.toLocaleString()} rows</span>
        </div>

        <Select value={model} onValueChange={(v) => setModel(v as LlmModel)}>
          <SelectTrigger className="h-9 w-[140px] border-border bg-surface/60 text-xs" aria-label="LLM model">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {llmModels.map((m) => (
              <SelectItem key={m.id} value={m.id} className="text-xs">
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Badge
          variant="outline"
          className={
            mockMode
              ? "hidden gap-1.5 border-warning/40 bg-warning/10 text-warning sm:flex"
              : "hidden gap-1.5 border-success/40 bg-success/10 text-success sm:flex"
          }
        >
          <span className="size-1.5 rounded-full bg-current" aria-hidden />
          {mockMode ? "Demo Mode" : "API Ready"}
        </Badge>

        <TooltipProvider delayDuration={80}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Notifications" className="hidden sm:inline-flex">
                <Bell className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Notifications</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Settings" className="hidden sm:inline-flex">
                <Settings className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Settings</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </header>
  );
}
