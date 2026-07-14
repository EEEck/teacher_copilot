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
  children,
  className,
}: {
  id?: string;
  title: string;
  description?: string;
  /** Optional hover explanation on the section title. */
  titleHover?: string;
  children: ReactNode;
  className?: string;
}) {
  const headingClass =
    "text-xl font-semibold tracking-tight text-foreground md:text-2xl";

  return (
    <section id={id} className={cn("mb-10 scroll-mt-6", className)}>
      <header className="mb-4 border-b border-border pb-3">
        {titleHover ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <h2
                className={cn(
                  headingClass,
                  "w-fit cursor-help underline-offset-4 hover:underline",
                )}
                tabIndex={0}
              >
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
        )}
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}
