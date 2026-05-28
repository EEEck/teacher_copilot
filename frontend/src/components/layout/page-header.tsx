import Link from "next/link";
import { cn } from "@/lib/utils";

export function PageHeader({
  backHref,
  backLabel = "Back",
  title,
  description,
  className,
}: {
  backHref?: string;
  backLabel?: string;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("mb-8", className)}>
      {backHref && (
        <Link href={backHref} className="text-sm text-primary hover:underline">
          ← {backLabel}
        </Link>
      )}
      <h1 className="mt-2 text-3xl font-bold tracking-tight">{title}</h1>
      {description && <p className="mt-2 text-muted-foreground">{description}</p>}
    </div>
  );
}
