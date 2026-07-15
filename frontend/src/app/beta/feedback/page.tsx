"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { MessageSquarePlus } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { client } from "@/lib/api";

export default function BetaFeedbackPage() {
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
    <main className="mx-auto flex min-h-[60vh] max-w-lg items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Give feedback</CardTitle>
          <p className="text-sm text-muted-foreground">
            What helped, what was confusing, or what you wish worked differently. Short notes are
            fine.
          </p>
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
    </main>
  );
}
