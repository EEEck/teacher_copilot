import Link from "next/link";
import { cn } from "@/lib/utils";

export function PageHeader({
  backHref,
  backLabel = "Back",
  title,
  description,
  variant = "default",
  className,
}: {
  backHref?: string;
  backLabel?: string;
  title: string;
  description?: string;
  variant?: "default" | "compact";
  className?: string;
}) {
  const compact = variant === "compact";
  return (
    <div className={cn(compact ? "mb-1.5" : "mb-8", className)}>
      {backHref && (
        <Link
          href={backHref}
          className={cn(
            "text-primary hover:underline",
            compact ? "text-xs" : "text-sm",
          )}
        >
          ← {backLabel}
        </Link>
      )}
      <h1
        className={cn(
          "tracking-tight",
          compact ? "mt-0.5 text-lg font-semibold leading-tight" : "mt-2 text-3xl font-bold",
        )}
      >
        {title}
      </h1>
      {description && (
        <p
          className={cn(
            "text-muted-foreground",
            compact ? "mt-0 text-xs leading-snug" : "mt-2",
          )}
        >
          {description}
        </p>
      )}
    </div>
  );
}
