import type { BetaIdentity } from "@/lib/api";

export function betaProfileInitial(name: string | null | undefined): string {
  const trimmed = (name ?? "").trim();
  if (!trimmed) return "?";
  return trimmed.charAt(0).toUpperCase();
}

export function formatBetaMemberSince(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso.replace("Z", "+00:00"));
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function betaProfileGateExemptPath(pathname: string): boolean {
  return (
    pathname === "/beta/login" ||
    pathname.startsWith("/beta/profile")
  );
}

export function betaProfileRedirectPath(
  pathname: string,
  search = "",
): string {
  const next = `${pathname}${search}`;
  return `/beta/profile?next=${encodeURIComponent(next)}`;
}

export function resolveBetaReturnPath(next: string | null): string {
  if (next?.startsWith("/") && !next.startsWith("//") && !next.startsWith("/beta/login")) {
    return next;
  }
  return "/";
}

export function hasBetaHeaderIdentity(identity: BetaIdentity | null): identity is BetaIdentity {
  return Boolean(identity?.profile_complete && identity.display_name.trim());
}

export function formatBetaRoleLine(
  identity: Pick<BetaIdentity, "role" | "member_since">,
): string {
  const role = identity.role === "tester" ? "Beta tester" : identity.role;
  if (identity.member_since) {
    return `${role} · joined ${formatBetaMemberSince(identity.member_since)}`;
  }
  return role;
}
