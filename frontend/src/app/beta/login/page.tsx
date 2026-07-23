"use client";

import { LogIn } from "lucide-react";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { client } from "@/lib/api";
import { betaProfileRedirectPath, resolveBetaReturnPath } from "@/lib/beta-profile";

export default function BetaLoginPage() {
  return (
    <Suspense fallback={<main className="mx-auto flex min-h-[60vh] max-w-md items-center text-sm text-muted-foreground">Loading…</main>}>
      <BetaLoginPageContent />
    </Suspense>
  );
}

function BetaLoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const identity = await client.betaLogin(inviteCode);
      const returnTo = resolveBetaReturnPath(searchParams.get("next"));
      if (!identity.profile_complete) {
        router.replace(betaProfileRedirectPath(returnTo));
      } else {
        router.replace(returnTo);
      }
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invite code failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Beta login</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={onSubmit}>
            <label className="grid gap-2 text-sm font-medium">
              Invite code
              <Input
                autoComplete="one-time-code"
                autoFocus
                value={inviteCode}
                onChange={(event) => setInviteCode(event.target.value)}
              />
            </label>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={submitting || !inviteCode.trim()}>
              <LogIn />
              {submitting ? "Checking..." : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
