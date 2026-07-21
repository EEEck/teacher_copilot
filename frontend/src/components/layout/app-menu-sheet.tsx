"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BookOpen,
  LogOut,
  MenuIcon,
  MessageSquare,
  Settings,
  UserRound,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { client, type BetaIdentity } from "@/lib/api";
import {
  betaProfileInitial,
  formatBetaRoleLine,
  hasBetaHeaderIdentity,
} from "@/lib/beta-profile";
import { cn } from "@/lib/utils";

function MenuNavLink({
  href,
  icon: Icon,
  children,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <SheetClose asChild>
      <Link
        href={href}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-foreground",
          "hover:bg-muted",
        )}
      >
        <Icon className="size-4 text-muted-foreground" />
        {children}
      </Link>
    </SheetClose>
  );
}

export function AppMenuSheet() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [identity, setIdentity] = useState<BetaIdentity | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    client
      .betaMe()
      .then((payload) => {
        if (!cancelled) setIdentity(payload);
      })
      .catch(() => {
        if (!cancelled) setIdentity(null);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const profileComplete = hasBetaHeaderIdentity(identity);
  const hasSession = identity !== null;
  const initial = betaProfileInitial(identity?.display_name);

  async function onLogout() {
    setLoggingOut(true);
    try {
      await client.betaLogout();
      setIdentity(null);
      setOpen(false);
      router.replace("/beta/login");
      router.refresh();
    } finally {
      setLoggingOut(false);
    }
  }

  const triggerLabel = profileComplete
    ? `Open menu for ${identity!.display_name}`
    : "Open menu";

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          type="button"
          variant={profileComplete ? "outline" : "ghost"}
          size="icon"
          aria-label={triggerLabel}
          className={cn(
            profileComplete &&
              "size-9 rounded-full border-border bg-muted/60 text-sm font-semibold text-primary hover:border-primary/30 hover:bg-muted",
          )}
        >
          {profileComplete ? initial : <MenuIcon className="size-5" />}
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-xs">
        <SheetHeader className="border-b border-border px-4 py-4 text-left">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          {hasSession ? (
            profileComplete ? (
              <div className="flex items-center gap-3 pr-8">
                <div
                  aria-hidden
                  className="flex size-12 shrink-0 items-center justify-center rounded-full border border-border bg-muted/60 text-lg font-semibold text-primary"
                >
                  {initial}
                </div>
                <div className="min-w-0">
                  <p className="truncate font-semibold text-foreground">
                    {identity!.display_name}
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {formatBetaRoleLine(identity!)}
                  </p>
                </div>
              </div>
            ) : (
              <SheetClose asChild>
                <Link
                  href="/beta/profile"
                  className="-mx-1 flex items-center gap-3 rounded-lg px-1 py-0.5 pr-8 hover:bg-muted/60"
                >
                  <div
                    aria-hidden
                    className="flex size-12 shrink-0 items-center justify-center rounded-full border border-border bg-muted/60 text-lg font-semibold text-primary"
                  >
                    {initial}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-foreground">Set up profile</p>
                    <p className="mt-0.5 text-sm text-muted-foreground">New tester</p>
                  </div>
                </Link>
              </SheetClose>
            )
          ) : (
            <p className="pr-8 font-heading text-base font-medium text-foreground">Menu</p>
          )}
        </SheetHeader>

        <nav className="flex flex-1 flex-col gap-0.5 px-3 py-3">
          {hasSession && (
            <MenuNavLink href="/beta/profile" icon={UserRound}>
              Profile
            </MenuNavLink>
          )}
          <MenuNavLink href="/docs" icon={BookOpen}>
            Docs
          </MenuNavLink>
          <MenuNavLink href="/beta/feedback" icon={MessageSquare}>
            Feedback
          </MenuNavLink>
          <MenuNavLink href="/settings" icon={Settings}>
            Settings
          </MenuNavLink>
        </nav>

        {hasSession && (
          <SheetFooter className="border-t border-border p-3">
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-start gap-3 px-3 text-foreground"
              disabled={loggingOut}
              onClick={() => void onLogout()}
            >
              <LogOut className="size-4 text-muted-foreground" />
              {loggingOut ? "Signing out…" : "Log out"}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}
