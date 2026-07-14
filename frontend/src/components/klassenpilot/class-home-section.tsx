import type { ReactNode } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Shared section chrome for class home (dashboard / actions / timeline). */
export function ClassHomeSection({
  id,
  title,
  description,
  titleHover,
  actions,
  children,
  className,
}: {
  id?: string;
  title: string;
  description?: string;
  /** Optional hover explanation on the section title. */
  titleHover?: string;
  /** Optional header actions (e.g. timeline + CTA). */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const headingClass =
    "text-xl font-semibold tracking-tight text-foreground md:text-2xl";

  const heading = titleHover ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <h2 className={cn(headingClass, "w-fit cursor-default")} tabIndex={0}>
          {title}
        </h2>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        align="start"
        className="max-w-sm text-pretty leading-relaxed"
      >
        {titleHover}
      </TooltipContent>
    </Tooltip>
  ) : (
    <h2 className={headingClass}>{title}</h2>
  );

  return (
    <section id={id} className={cn("mb-10 scroll-mt-6", className)}>
      <header className="mb-4 flex items-start justify-between gap-3 border-b border-border pb-3">
        <div className="min-w-0">
          {heading}
          {description ? (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}
