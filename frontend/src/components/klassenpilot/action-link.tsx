import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ActionLink({
  href,
  children,
  primary,
}: {
  href: string;
  children: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(buttonVariants({ variant: primary ? "default" : "outline", size: "default" }))}
    >
      {children}
    </Link>
  );
}

export function ActionButton(props: React.ComponentProps<typeof Button>) {
  return <Button {...props} />;
}
