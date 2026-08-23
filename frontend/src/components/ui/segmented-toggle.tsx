"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type SegmentedToggleOption = {
  value: string;
  label: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  disabled?: boolean;
  disabledReason?: string;
};

export type SegmentedToggleProps = {
  value: string;
  onValueChange: (value: string) => void;
  options: SegmentedToggleOption[];
  size?: "sm" | "default";
  className?: string;
  "aria-label"?: string;
};

/** Muted gray segmented control — rounded-md track, no brand green. */
export function SegmentedToggle({
  value,
  onValueChange,
  options,
  size = "sm",
  className,
  "aria-label": ariaLabel,
}: SegmentedToggleProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn("inline-flex rounded-md border border-border p-0.5", className)}
    >
      {options.map((option) => {
        const Icon = option.icon;
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            aria-disabled={option.disabled || undefined}
            disabled={option.disabled}
            title={option.disabledReason}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "inline-flex items-center justify-center gap-1 rounded font-medium transition-colors",
              size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
              selected ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
              option.disabled && "cursor-not-allowed opacity-60 hover:text-muted-foreground",
            )}
          >
            {Icon && <Icon className={size === "sm" ? "size-3.5" : "size-4"} />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
