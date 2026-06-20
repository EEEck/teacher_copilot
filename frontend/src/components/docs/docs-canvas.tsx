import { cn } from "@/lib/utils";

/** Docs use a wider frame than the rest of the app; see layout.tsx. */
export function DocsCanvas({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("docs-canvas min-h-[calc(100vh-3.5rem)]", className)}>{children}</div>;
}

/**
 * Breaks out of the app shell max-width so docs can use more horizontal space
 * on large monitors, capped at 90rem (~1440px).
 */
export function DocsContentFrame({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative left-1/2 w-[min(calc(100vw-3rem),90rem)] max-w-none -translate-x-1/2",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function DocsSheet({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "docs-sheet overflow-hidden rounded-xl border border-border bg-card shadow-sm",
        className,
      )}
    >
      <div className="h-1 bg-primary" aria-hidden="true" />
      {children}
    </div>
  );
}
