import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Shared section chrome for class home (dashboard / actions / timeline). */
export function ClassHomeSection({
  id,
  title,
  description,
  children,
  className,
}: {
  id?: string;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={cn("mb-10 scroll-mt-6", className)}>
      <header className="mb-4 border-b border-border pb-3">
        <h2 className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
          {title}
        </h2>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}
