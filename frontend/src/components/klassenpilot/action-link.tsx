import Link from "next/link";
import { forwardRef } from "react";
import type { VariantProps } from "class-variance-authority";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;
type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>;

export const ActionLink = forwardRef<
  HTMLAnchorElement,
  {
    href: string;
    children: React.ReactNode;
    /** @deprecated Prefer `variant="default"` — kept for older call sites. */
    primary?: boolean;
    variant?: ButtonVariant;
    /** Prefer `lg` for section-level workflow CTAs (e.g. class home Actions). */
    size?: ButtonSize;
    className?: string;
    title?: string;
  }
>(function ActionLink(
  { href, children, primary, variant, size = "default", className, title },
  ref,
) {
  const resolved: ButtonVariant =
    variant ?? (primary ? "default" : "outline");

  return (
    <Link
      ref={ref}
      href={href}
      title={title}
      className={cn(buttonVariants({ variant: resolved, size }), className)}
    >
      {children}
    </Link>
  );
});

export function ActionButton(props: React.ComponentProps<typeof Button>) {
  return <Button {...props} />;
}
