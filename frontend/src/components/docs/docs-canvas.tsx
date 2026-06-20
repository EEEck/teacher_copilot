import { cn } from "@/lib/utils";

export function DocsCanvas({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("docs-canvas min-h-[calc(100vh-3.5rem)]", className)}>{children}</div>;
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
