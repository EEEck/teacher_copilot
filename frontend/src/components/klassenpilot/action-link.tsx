import Link from "next/link";
import type { VariantProps } from "class-variance-authority";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;
type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>;

export function ActionLink({
  href,
  children,
  primary,
  variant,
  size = "default",
  className,
  title,
}: {
  href: string;
  children: React.ReactNode;
  /** @deprecated Prefer `variant="default"` — kept for older call sites. */
  primary?: boolean;
  variant?: ButtonVariant;
  /** Prefer `lg` for section-level workflow CTAs (e.g. class home Actions). */
  size?: ButtonSize;
  className?: string;
  title?: string;
}) {
  const resolved: ButtonVariant =
    variant ?? (primary ? "default" : "outline");

  return (
    <Link
      href={href}
      title={title}
      className={cn(buttonVariants({ variant: resolved, size }), className)}
    >
      {children}
    </Link>
  );
}

export function ActionButton(props: React.ComponentProps<typeof Button>) {
  return <Button {...props} />;
}
