"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { MessageSquarePlus } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { client } from "@/lib/api";

export default function BetaFeedbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNeedsLogin(false);
    setUnavailable(false);
    setSent(false);
    try {
      await client.betaFeedback(message, "/beta/feedback");
      setSent(true);
      setMessage("");
    } catch (e) {
      const text = e instanceof Error ? e.message : "Could not send feedback";
      if (text.includes("API 401")) {
        setNeedsLogin(true);
        setError("Beta login required to send feedback.");
      } else if (text.includes("API 404")) {
        setUnavailable(true);
        setError("Feedback is only available in beta mode.");
      } else {
        setError(text);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        onBack={() => router.back()}
        backLabel="Back"
        title="Give feedback"
        description="What helped, what was confusing, or what you wish worked differently. Short notes are fine."
      />
      <Card className="mx-auto w-full max-w-lg">
        <CardHeader className="sr-only">
          <CardTitle>Give feedback</CardTitle>
        </CardHeader>
        <CardContent>
          {sent && (
            <Alert className="mb-4 border-border bg-muted text-foreground">
              <AlertDescription>Thanks — your note was saved for the beta.</AlertDescription>
            </Alert>
          )}
          <form className="grid gap-4" onSubmit={onSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="feedback-message">Your feedback</Label>
              <Textarea
                id="feedback-message"
                autoFocus
                rows={6}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Tell us what mattered in this session…"
                disabled={submitting}
              />
            </div>
            {error && (
              <Alert variant={unavailable || needsLogin ? "default" : "destructive"}>
                <AlertDescription>
                  {needsLogin ? (
                    <>
                      {error}{" "}
                      <Link href="/beta/login" className="font-medium text-primary hover:underline">
                        Enter invite code
                      </Link>
                    </>
                  ) : (
                    error
                  )}
                </AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={submitting || !message.trim()}>
              <MessageSquarePlus />
              {submitting ? "Sending…" : "Send feedback"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
