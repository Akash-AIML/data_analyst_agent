import type { ReactNode } from "react";
import { useState } from "react";
import { Header } from "./Header";
import { MobileNav, Sidebar } from "@/components/navigation/Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="relative flex min-h-screen bg-background">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      >
        <div className="absolute -left-40 -top-40 size-[36rem] rounded-full bg-primary/12 blur-[140px]" />
        <div className="absolute -right-40 top-1/3 size-[32rem] rounded-full bg-accent/10 blur-[150px]" />
        <div className="absolute bottom-0 left-1/3 size-[28rem] rounded-full bg-success/[0.06] blur-[150px]" />
      </div>

      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <MobileNav />
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
