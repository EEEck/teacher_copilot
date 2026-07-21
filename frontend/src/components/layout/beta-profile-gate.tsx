"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { client } from "@/lib/api";
import {
  betaProfileGateExemptPath,
  betaProfileRedirectPath,
} from "@/lib/beta-profile";

export function BetaProfileGate() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (betaProfileGateExemptPath(pathname)) return;

    let cancelled = false;
    client
      .betaMe()
      .then((identity) => {
        if (cancelled || identity.profile_complete) return;
        const search = searchParams.toString();
        const suffix = search ? `?${search}` : "";
        router.replace(betaProfileRedirectPath(pathname, suffix));
      })
      .catch(() => {
        // Not logged in or beta session unavailable — other flows handle auth.
      });

    return () => {
      cancelled = true;
    };
  }, [pathname, router, searchParams]);

  return null;
}
