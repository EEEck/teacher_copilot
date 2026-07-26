"use client";

import { LoaderCircleIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

function formatLessonDate(isoDate: string): string {
  const trimmed = isoDate.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const date = new Date(`${trimmed}T12:00:00`);
  if (Number.isNaN(date.getTime())) return trimmed;
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

/**
 * Footer-inline amber confirm for plan save — sits where the teacher clicked
 * Ready to save. Update Memory keeps the heavier in-chat ReviewBrief.
 */
export function PlanSaveConfirm({
  lessonDate,
  onLessonDateChange,
  onConfirm,
  onCancel,
  saving,
  className,
}: {
  lessonDate: string;
  onLessonDateChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  saving?: boolean;
  className?: string;
}) {
  const label = formatLessonDate(lessonDate);

  return (
    <Alert
      role="status"
      className={cn(
        "border-amber-200 bg-amber-50 text-amber-950 shadow-sm",
        className,
      )}
    >
      <AlertDescription className="text-amber-950">
        <div className="flex flex-col gap-3">
          <div className="min-w-0 space-y-0.5">
            <div className="text-sm font-semibold text-amber-950">
              Confirm save
            </div>
            <p className="text-sm text-amber-950/90">
              Save this plan to{" "}
              <span className="font-medium text-amber-950">{label || "…"}</span>.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label
                htmlFor="lesson-date-confirm"
                className="text-amber-950"
              >
                Lesson date
              </Label>
              <Input
                id="lesson-date-confirm"
                type="date"
                value={lessonDate}
                onChange={(e) => onLessonDateChange(e.target.value)}
                className="w-[180px] border-amber-200 bg-background"
                disabled={saving}
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              className="text-amber-900 hover:bg-amber-100/80 hover:text-amber-950"
              onClick={onCancel}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="attention"
              size="lg"
              onClick={onConfirm}
              disabled={saving || !lessonDate.trim()}
            >
              {saving ? (
                <>
                  <LoaderCircleIcon className="animate-spin" />
                  Saving…
                </>
              ) : (
                "Save plan"
              )}
            </Button>
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
}
