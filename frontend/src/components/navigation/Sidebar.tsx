import { Link, useRouterState } from "@tanstack/react-router";
import {
  BarChart3,
  ChevronLeft,
  Lightbulb,
  MessageSquare,
  PanelLeft,
  Rocket,
  Wrench,
  Sparkle,
} from "lucide-react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const nav = [
  { to: "/", label: "Pipeline Launcher", icon: Rocket },
  { to: "/profile", label: "Dataset Profile & EDA", icon: BarChart3 },
  { to: "/insights", label: "Executive Insights", icon: Lightbulb },
  { to: "/chat", label: "Analyst Chat", icon: MessageSquare },
  { to: "/diagnostics", label: "Agent Diagnostics", icon: Wrench },
] as const;

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <TooltipProvider delayDuration={80}>
      <motion.aside
        animate={{ width: collapsed ? 76 : 268 }}
        transition={{ type: "spring", stiffness: 260, damping: 30 }}
        className="sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar/80 backdrop-blur-xl md:flex"
      >
        <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
          <div className="relative grid size-9 shrink-0 place-items-center rounded-xl bg-[image:var(--gradient-primary)] shadow-glow">
            <Sparkle className="size-4 text-primary-foreground" aria-hidden />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight">AI Data Analyst</p>
              <p className="truncate text-[11px] text-muted-foreground">Multi-agent platform</p>
            </div>
          )}
        </div>

        <nav className="flex-1 space-y-1 p-3" aria-label="Main">
          {nav.map((item) => {
            const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            const link = (
              <Link
                key={item.to}
                to={item.to}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                  collapsed && "justify-center px-0",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-primary"
                  />
                )}
                <item.icon className="size-[18px] shrink-0" aria-hidden />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
            return collapsed ? (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <div className={cn("flex items-center gap-3 rounded-lg px-2 py-2", collapsed && "justify-center px-0")}>
            <div className="grid size-9 shrink-0 place-items-center rounded-full bg-secondary text-xs font-semibold">
              KA
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">Kamalesh A.</p>
                <p className="truncate text-[11px] text-muted-foreground">Analytics Workspace</p>
              </div>
            )}
          </div>
          <button
            onClick={onToggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-sidebar-border py-2 text-xs text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {collapsed ? <PanelLeft className="size-4" /> : <ChevronLeft className="size-4" />}
            {!collapsed && "Collapse"}
          </button>
        </div>
      </motion.aside>
    </TooltipProvider>
  );
}

export function MobileNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      className="sticky top-16 z-20 flex gap-1 overflow-x-auto border-b border-border bg-background/80 px-3 py-2 backdrop-blur-xl md:hidden"
      aria-label="Main mobile"
    >
      {nav.map((item) => {
        const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium",
              active ? "bg-secondary text-foreground" : "text-muted-foreground",
            )}
          >
            <item.icon className="size-4" aria-hidden />
            {item.label.split(" ")[0]}
          </Link>
        );
      })}
    </nav>
  );
}
