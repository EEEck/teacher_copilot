"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, UserRound } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client, type BetaIdentity } from "@/lib/api";
import {
  betaProfileInitial,
  formatBetaMemberSince,
  resolveBetaReturnPath,
} from "@/lib/beta-profile";

function ProfileStat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
        {value}
      </p>
    </div>
  );
}

export default function BetaProfilePage() {
  return (
    <Suspense fallback={<div className="mx-auto w-full max-w-lg text-sm text-muted-foreground">Loading profile…</div>}>
      <BetaProfilePageContent />
    </Suspense>
  );
}

function BetaProfilePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [identity, setIdentity] = useState<BetaIdentity | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const onboarding = identity ? !identity.profile_complete : false;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .betaMe()
      .then((payload) => {
        if (cancelled) return;
        setIdentity(payload);
        setDisplayName(payload.display_name);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : "Could not load profile";
        if (message.includes("API 401")) {
          router.replace(`/beta/login?next=${encodeURIComponent("/beta/profile")}`);
          return;
        }
        setError(message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await client.betaUpdateProfile(displayName);
      setIdentity(updated);
      setDisplayName(updated.display_name);
      setSaved(true);
      if (!updated.profile_complete) return;
      if (onboarding) {
        router.replace(resolveBetaReturnPath(searchParams.get("next")));
        router.refresh();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save profile");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-lg">
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">Loading profile…</CardContent>
        </Card>
      </div>
    );
  }

  if (!identity) {
    return (
      <div className="mx-auto w-full max-w-lg">
        <Card>
          <CardContent className="p-6">
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : (
              <p className="text-sm text-muted-foreground">Profile unavailable.</p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  const initial = betaProfileInitial(identity.display_name);
  const stats = identity.stats;

  return (
    <div className="mx-auto w-full max-w-2xl">
      <PageHeader
        onBack={onboarding ? undefined : () => router.back()}
        backLabel="Back"
        title={onboarding ? "Set up your profile" : "Your profile"}
        description={
          onboarding
            ? "Choose how your name appears in the beta. You need this once before continuing."
            : "Your beta identity and a few lightweight activity counts from this workspace."
        }
      />

      {onboarding && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>
            Welcome to the KlassenPilot beta. Add your display name to continue.
          </AlertDescription>
        </Alert>
      )}

      {saved && !onboarding && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <CheckCircle2 className="size-4" />
          <AlertDescription>Profile updated.</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center gap-4 space-y-0">
            <div
              aria-hidden
              className="flex size-14 shrink-0 items-center justify-center rounded-full border border-border bg-muted/60 text-xl font-semibold text-primary"
            >
              {initial}
            </div>
            <div className="min-w-0">
              <CardTitle className="truncate">
                {identity.profile_complete ? identity.display_name : "New tester"}
              </CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {identity.role === "tester" ? "Beta tester" : identity.role}
                {identity.member_since
                  ? ` · joined ${formatBetaMemberSince(identity.member_since)}`
                  : null}
              </p>
            </div>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={onSubmit}>
              <div className="grid gap-2">
                <Label htmlFor="display-name">Display name</Label>
                <Input
                  id="display-name"
                  autoComplete="nickname"
                  autoFocus={onboarding}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="How should we greet you?"
                  disabled={submitting}
                />
              </div>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <Button type="submit" disabled={submitting || !displayName.trim()}>
                <UserRound />
                {submitting
                  ? "Saving…"
                  : onboarding
                    ? "Continue to app"
                    : "Save profile"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {identity.profile_complete && stats && (
          <section aria-labelledby="beta-profile-stats-heading">
            <h2
              id="beta-profile-stats-heading"
              className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
            >
              In this beta workspace
            </h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <ProfileStat label="Feedback notes" value={stats.feedback_notes} />
              <ProfileStat label="Workflow sessions" value={stats.workflow_sessions} />
              <ProfileStat label="Wiki commits" value={stats.wiki_commits} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
