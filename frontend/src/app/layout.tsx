import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { PendingTurnNotifier } from "@/components/klassenpilot/pending-turn-notifier";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: "KlassenPilot",
  description: "Private teacher copilot for Gymnasium teachers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("font-sans", geist.variable)}>
      <body>
        <TooltipProvider>
          <AppShell>{children}</AppShell>
          <PendingTurnNotifier />
          <Toaster />
        </TooltipProvider>
      </body>
    </html>
  );
}
