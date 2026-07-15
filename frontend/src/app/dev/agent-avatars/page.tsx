"use client";

import { useId, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Brain,
  CalendarDays,
  ClipboardList,
  ListChecks,
  MessageCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";

import {
  AgentMark,
  type AgentMarkMood,
  type AgentMarkWorkflow,
} from "@/components/klassenpilot/agent-mark";
import { cn } from "@/lib/utils";

type VariantId =
  | "A"
  | "B"
  | "C"
  | "D"
  | "E"
  | "F"
  | "G"
  | "H"
  | "I"
  | "J"
  | "K"
  | "L"
  | "M"
  | "N"
  | "O"
  | "P"
  | "Q"
  | "R"
  | "S"
  | "sleep"
  | "think"
  | "doh"
  | "happy"
  | "wf-memory"
  | "wf-plan"
  | "wf-sweep";

const ACTIONS = [
  { id: "plan", label: "Plan", icon: "P" },
  { id: "remember", label: "Remember", icon: "R" },
  { id: "discuss", label: "Discuss", icon: "D" },
  { id: "notes", label: "Notes", icon: "N" },
] as const;

/** Hex ring: Plan · Remember · Discuss · Clipboard · AI · Self-improving */
const HEX_NODES = [
  { id: "plan", label: "Plan", Icon: CalendarDays },
  { id: "remember", label: "Remember", Icon: Brain },
  { id: "discuss", label: "Discuss", Icon: MessageCircle },
  { id: "clipboard", label: "Notes / clipboard", Icon: ClipboardList },
  { id: "ai", label: "AI", Icon: Sparkles },
  { id: "improve", label: "Self-improving", Icon: RefreshCw },
] as const;

type FaceMood = "default" | "sleeping" | "thinking" | "doh" | "happy";

type WorkflowKind = "memory" | "plan" | "sweep";

/** Shared face core — S final eyes by default; moods swap lids/mouth. */
function FaceCore({
  size = 88,
  whiteEyes = false,
  mood = "default",
  overlay = "none",
  sleepZzz = true,
}: {
  size?: number;
  /** Pure-white sclera + dark pupils (S final). */
  whiteEyes?: boolean;
  mood?: FaceMood;
  /** Optional face overlay — bricks = A-like bright green lattice as masonry. */
  overlay?: "none" | "bricks";
  /** Rising ZZZ for idle sleep; off for workflow marks that reuse sleeping lids. */
  sleepZzz?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const gradId = `kp-core-${uid}`;
  const brokenClipId = `kp-broken-clip-${uid}`;
  const useWhite = whiteEyes || mood !== "default";
  const broken = overlay === "bricks";

  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className="relative z-[1] overflow-visible"
      aria-hidden
    >
      <defs>
        <radialGradient id={gradId} cx="50%" cy="42%" r="55%">
          <stop offset="0%" stopColor="#0d2e1c" />
          <stop offset="70%" stopColor="#014421" />
          <stop offset="100%" stopColor="#02150c" />
        </radialGradient>
        {/* Left edge broken along brick courses — right side stays round */}
        <clipPath id={brokenClipId}>
          <path d="M32 10 A22 22 0 0 1 32 54 L28 54 L28 50.5 L22 50.5 L22 44 L17 44 L17 37.5 L21 37.5 L21 31 L15 31 L15 24.5 L20 24.5 L20 18 L25 18 L25 12.5 L32 10 Z" />
        </clipPath>
      </defs>

      <circle
        cx="32"
        cy="32"
        r="22"
        fill={`url(#${gradId})`}
        clipPath={broken ? `url(#${brokenClipId})` : undefined}
      />
      {!broken && (
        <circle
          cx="32"
          cy="32"
          r="22"
          fill="none"
          stroke="hsl(149 70% 42%)"
          strokeOpacity="0.55"
          strokeWidth="1.25"
        />
      )}
      {broken && (
        <path
          d="M32 10 A22 22 0 0 1 32 54"
          fill="none"
          stroke="hsl(149 70% 42%)"
          strokeOpacity="0.55"
          strokeWidth="1.25"
        />
      )}

      {broken && (
        <g clipPath={`url(#${brokenClipId})`}>
          {/* Brick fills — masonry courses */}
          <g fill="#0a1f14" fillOpacity="0.45" stroke="hsl(149 80% 55%)" strokeOpacity="0.7" strokeWidth="0.85">
            <rect x="25" y="12" width="14" height="6" rx="1.1" />
            <rect x="39" y="12" width="12" height="6" rx="1.1" />
            <rect x="20" y="18.2" width="12" height="6" rx="1.1" />
            <rect x="32.2" y="18.2" width="13" height="6" rx="1.1" />
            <rect x="45.4" y="18.2" width="8" height="6" rx="1.1" />
            <rect x="21" y="24.7" width="11" height="6" rx="1.1" />
            <rect x="32.2" y="24.7" width="12" height="6" rx="1.1" />
            <rect x="44.4" y="24.7" width="9" height="6" rx="1.1" />
            <rect x="15.2" y="31.2" width="10" height="6" rx="1.1" />
            <rect x="25.4" y="31.2" width="12" height="6" rx="1.1" />
            <rect x="37.6" y="31.2" width="12" height="6" rx="1.1" />
            <rect x="21" y="37.7" width="12" height="6" rx="1.1" />
            <rect x="33.2" y="37.7" width="12" height="6" rx="1.1" />
            <rect x="45.4" y="37.7" width="8" height="6" rx="1.1" />
            <rect x="22.2" y="44.2" width="11" height="6" rx="1.1" />
            <rect x="33.4" y="44.2" width="13" height="6" rx="1.1" />
            <rect x="28" y="50.5" width="12" height="5" rx="1" />
          </g>
          <g fill="hsl(149 85% 60%)" fillOpacity="0.7">
            <circle cx="32" cy="18.2" r="0.95" />
            <circle cx="39" cy="24.7" r="0.95" />
            <circle cx="25.4" cy="31.2" r="0.95" />
            <circle cx="37.6" cy="37.7" r="0.95" />
            <circle cx="33.4" cy="44.2" r="0.95" />
          </g>
        </g>
      )}

      {/* Flying bricks assembling into the broken left edge */}
      {broken && (
        <g>
          {/* Motion trails */}
          <g stroke="hsl(149 80% 55%)" strokeLinecap="round" opacity="0.55">
            <path d="M1 21.5 H7.5" strokeWidth="1.4" />
            <path d="M0 28.5 H6" strokeWidth="1.2" opacity="0.7" />
            <path d="M2 36 H8" strokeWidth="1.3" />
          </g>
          <g fill="#014421" stroke="hsl(149 80% 55%)" strokeWidth="0.9">
            <rect x="7" y="19.2" width="7.2" height="4.4" rx="1" />
            <rect x="5.5" y="26.4" width="6.6" height="4.2" rx="1" opacity="0.92" />
            <rect x="8" y="33.8" width="7" height="4.3" rx="1" opacity="0.95" />
          </g>
          {/* Tiny debris chips */}
          <g fill="hsl(149 85% 60%)" fillOpacity="0.55">
            <rect x="14.5" y="40.5" width="1.6" height="1.6" rx="0.3" />
            <rect x="12.2" y="46" width="1.3" height="1.3" rx="0.3" />
            <rect x="17" y="48.5" width="1.4" height="1.4" rx="0.3" />
          </g>
        </g>
      )}
      {mood === "sleeping" && (
        <g>
          {/* Closed lids only — no mouth/nose */}
          <g
            fill="none"
            stroke="#ffffff"
            strokeWidth="2.4"
            strokeLinecap="round"
            style={{ stroke: "#ffffff" }}
          >
            <path d="M21.2 29.2c2.4 2.6 5.6 2.6 8 0" />
            <path d="M34.8 29.2c2.4 2.6 5.6 2.6 8 0" />
          </g>
          {sleepZzz && (
            <g fontFamily="ui-sans-serif, system-ui, sans-serif" fontWeight="700">
              <text
                x="42"
                y="22"
                fill="#ffffff"
                fontSize="9"
                style={{ fill: "#ffffff" }}
              >
                z
              </text>
              <text x="49" y="13" fill="#014421" fontSize="12" fillOpacity="0.9">
                z
              </text>
              <text x="57" y="3" fill="#014421" fontSize="15">
                Z
              </text>
            </g>
          )}
        </g>
      )}

      {mood === "thinking" && (
        <g>
          {/* Straight brows \ / — furrowed focus, not / \ concerned */}
          <g fill="#ffffff" style={{ fill: "#ffffff" }}>
            <rect
              x="20.2"
              y="22.6"
              width="8.2"
              height="1.7"
              rx="0.85"
              transform="rotate(18 24.3 23.45)"
            />
            <rect
              x="35.6"
              y="22.6"
              width="8.2"
              height="1.7"
              rx="0.85"
              transform="rotate(-18 39.7 23.45)"
            />
          </g>
          <circle cx="25.5" cy="29.5" r="4.3" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29.5" r="4.3" fill="#ffffff" style={{ fill: "#ffffff" }} />
          {/* Pupils looking right — attentive / working */}
          <circle cx="27.2" cy="29.2" r="1.65" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="40.2" cy="29.2" r="1.65" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="26.5" cy="28.3" r="0.55" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="39.5" cy="28.3" r="0.55" fill="#ffffff" style={{ fill: "#ffffff" }} />
        </g>
      )}

      {mood === "doh" && (
        <g>
          {/* X eyes only — no mouth */}
          <circle cx="25.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <g stroke="#06110c" strokeWidth="1.8" strokeLinecap="round" style={{ stroke: "#06110c" }}>
            <path d="M23.2 26.8l4.6 4.6M27.8 26.8l-4.6 4.6" />
            <path d="M36.2 26.8l4.6 4.6M40.8 26.8l-4.6 4.6" />
          </g>
        </g>
      )}

      {mood === "happy" && (
        <g>
          <circle cx="25.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="26.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="39.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="25.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <path
            d="M24.5 38.5c2.8 4.2 12.2 4.2 15 0"
            fill="none"
            stroke="#ffffff"
            strokeWidth="2"
            strokeLinecap="round"
            style={{ stroke: "#ffffff" }}
          />
        </g>
      )}

      {mood === "default" && useWhite && (
        <g>
          <circle cx="25.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="26.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="39.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="25.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
        </g>
      )}

      {mood === "default" && !useWhite && (
        <g>
          <circle cx="25.5" cy="29" r="3.1" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29" r="3.1" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="26.2" cy="28.4" r="1.05" fill="#014421" fillOpacity="0.35" />
          <circle cx="39.2" cy="28.4" r="1.05" fill="#014421" fillOpacity="0.35" />
        </g>
      )}
    </svg>
  );
}

function ClipboardBadge({
  className,
  size = 34,
  motif = "lines",
}: {
  className?: string;
  /** Overall height; width scales with the 28×34 artboard. Default 34. */
  size?: number;
  /** What’s drawn on the board instead of / besides note lines. */
  motif?: "lines" | "moon" | "spinner";
}) {
  const height = size;
  const width = (28 / 34) * size;
  return (
    <svg
      viewBox="0 0 28 34"
      className={cn("drop-shadow-sm", className)}
      width={width}
      height={height}
      aria-hidden
    >
      <rect x="4" y="6" width="20" height="26" rx="3" fill="#f7f9f7" stroke="#014421" strokeWidth="1.5" />
      <rect x="9" y="2" width="10" height="7" rx="2" fill="#014421" />
      {motif === "lines" && (
        <path d="M9 16h10M9 21h10M9 26h6" stroke="#014421" strokeWidth="1.4" strokeLinecap="round" opacity="0.55" />
      )}
      {motif === "moon" && (
        <g>
          {/* Crescent moon — clear sleep cue at small size */}
          <circle cx="14" cy="20.5" r="5.2" fill="#014421" fillOpacity="0.9" />
          <circle cx="16.2" cy="19.2" r="4.4" fill="#f7f9f7" />
          <circle cx="10.2" cy="26.2" r="0.7" fill="#014421" fillOpacity="0.45" />
          <circle cx="18.8" cy="26.8" r="0.55" fill="#014421" fillOpacity="0.35" />
          <circle cx="20.5" cy="24.2" r="0.45" fill="#014421" fillOpacity="0.3" />
        </g>
      )}
      {motif === "spinner" && (
        <g transform="translate(14 21)">
          {/* 8-spoke spinner — opacity fades clockwise */}
          {Array.from({ length: 8 }, (_, i) => {
            const angle = -90 + i * 45;
            const opacity = 1 - i * 0.11;
            return (
              <rect
                key={i}
                x={-1.05}
                y={-6.8}
                width={2.1}
                height={3.4}
                rx={1.05}
                fill="#014421"
                fillOpacity={Math.max(0.18, opacity)}
                transform={`rotate(${angle})`}
              />
            );
          })}
        </g>
      )}
    </svg>
  );
}

/** Shared clipboard board frame for workflow badges. */
function BadgeBoard({
  size,
  children,
  iconTop = "56%",
}: {
  size: number;
  children: ReactNode;
  iconTop?: string;
}) {
  const height = size;
  const width = (28 / 34) * size;
  const icon = Math.round(size * 0.44);
  return (
    <span className="relative inline-flex drop-shadow-sm" style={{ width, height }} aria-hidden>
      <svg viewBox="0 0 28 34" width={width} height={height} className="absolute inset-0">
        <rect x="3.5" y="5" width="21" height="25.5" rx="3" fill="#f7f9f7" stroke="#014421" strokeWidth="1.5" />
        <rect x="9" y="2" width="10" height="6.5" rx="2" fill="#014421" />
      </svg>
      <span
        className="absolute left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center text-[#014421]"
        style={{ top: iconTop, width: icon, height: icon }}
      >
        {children}
      </span>
    </span>
  );
}

/** Lesson-plan workflow badge — sharp Lucide checklist. */
function PlanBadge({ size = 64 }: { size?: number }) {
  const icon = Math.round(size * 0.44);
  return (
    <BadgeBoard size={size} iconTop="58%">
      <ListChecks width={icon} height={icon} strokeWidth={2.35} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

/** Memory-sweep workflow badge — sharp Lucide update / refresh. */
function SweepBadge({ size = 64 }: { size?: number }) {
  const icon = Math.round(size * 0.42);
  return (
    <BadgeBoard size={size} iconTop="57%">
      <RefreshCw width={icon} height={icon} strokeWidth={2.4} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

/** Error mood badge — sharp Lucide warning triangle. */
function WarningBadge({ size = 64 }: { size?: number }) {
  const icon = Math.round(size * 0.42);
  return (
    <BadgeBoard size={size} iconTop="57%">
      <AlertTriangle width={icon} height={icon} strokeWidth={2.4} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

function WorkflowBadge({
  workflow,
  size = 64,
  mood = "default",
}: {
  workflow: WorkflowKind;
  size?: number;
  mood?: FaceMood;
}) {
  if (mood === "doh") return <WarningBadge size={size} />;
  if (workflow === "plan") return <PlanBadge size={size} />;
  if (workflow === "sweep") return <SweepBadge size={size} />;
  const motif =
    mood === "sleeping"
      ? "moon"
      : mood === "thinking"
        ? "spinner"
        : "lines";
  return <ClipboardBadge size={size} motif={motif} />;
}

const WORKFLOW_LABEL: Record<WorkflowKind, string> = {
  memory: "Update memory",
  plan: "Create lesson plan",
  sweep: "Memory sweep",
};

/** A — Original: halo + crystalline wireframe (liked baseline). */
function AvatarA({ size = 120 }: { size?: number }) {
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <span className="absolute inset-[-16%] rounded-full bg-primary/20 blur-[7px]" aria-hidden />
      <span className="absolute inset-[-3%] rounded-full bg-primary/30 blur-[2px]" aria-hidden />
      <svg viewBox="0 0 64 64" className="relative h-full w-full" aria-hidden>
        <defs>
          <radialGradient id="a-core" cx="50%" cy="42%" r="55%">
            <stop offset="0%" stopColor="#0d2e1c" />
            <stop offset="70%" stopColor="#014421" />
            <stop offset="100%" stopColor="#02150c" />
          </radialGradient>
        </defs>
        <circle cx="32" cy="32" r="22" fill="url(#a-core)" />
        <circle cx="32" cy="32" r="22" fill="none" stroke="hsl(149 70% 42%)" strokeOpacity="0.55" strokeWidth="1.25" />
        <g fill="none" stroke="hsl(149 80% 55%)" strokeOpacity="0.45" strokeWidth="0.9" strokeLinejoin="round">
          <path d="M32 12 L48 22 L48 42 L32 52 L16 42 L16 22 Z" />
          <path d="M32 12 L32 52" />
          <path d="M16 22 L48 42" />
          <path d="M48 22 L16 42" />
        </g>
        <g fill="hsl(149 85% 60%)" fillOpacity="0.7">
          <circle cx="32" cy="12" r="1.2" />
          <circle cx="48" cy="22" r="1.2" />
          <circle cx="48" cy="42" r="1.2" />
          <circle cx="32" cy="52" r="1.2" />
          <circle cx="16" cy="42" r="1.2" />
          <circle cx="16" cy="22" r="1.2" />
        </g>
        <circle cx="25.5" cy="29" r="3.1" fill="#ffffff" />
        <circle cx="38.5" cy="29" r="3.1" fill="#ffffff" />
        <circle cx="26.2" cy="28.4" r="1.05" fill="#014421" fillOpacity="0.35" />
        <circle cx="39.2" cy="28.4" r="1.05" fill="#014421" fillOpacity="0.35" />
      </svg>
    </span>
  );
}

/** B — Original face + clipboard (no FJ wireframe). */
function AvatarB({ size = 120 }: { size?: number }) {
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <span className="absolute inset-[-14%] rounded-full bg-primary/18 blur-[6px]" aria-hidden />
      <FaceCore size={size * 0.72} />
      <span className="absolute -bottom-0.5 -right-0.5 rotate-6">
        <ClipboardBadge />
      </span>
    </span>
  );
}

type ActionTileTone = "card" | "muted" | "primary" | "accent";

const ACTION_TILE: Record<ActionTileTone, string> = {
  card: "border-border bg-card text-primary shadow-sm",
  muted: "border-border/80 bg-muted text-foreground shadow-sm",
  primary: "border-primary bg-primary text-primary-foreground shadow-sm",
  accent: "border-primary/20 bg-accent text-accent-foreground shadow-sm",
};

/** Shared C-family: A's face+halo scale; action tiles outside or tucked in halo. */
function AvatarOrbit({
  faceSize = 120,
  tile = "card",
  proximity = "outside",
}: {
  faceSize?: number;
  tile?: ActionTileTone;
  /** outside = beyond halo; halo* = inside glow near clipboard distance */
  proximity?: "outside" | "halo" | "halo-tight" | "halo-loose";
}) {
  const tilePx = proximity === "outside" ? 32 : 28;
  const haloPad = faceSize * 0.16;
  // Core disc radius in px (r=22 of 64 viewBox)
  const coreRadius = faceSize * (22 / 64);

  let orbit: number;
  if (proximity === "outside") {
    const gap = 10;
    orbit = faceSize / 2 + haloPad + gap + tilePx / 2;
  } else if (proximity === "halo-tight") {
    // Just outside the dark core, deep in the halo — clipboard-close
    orbit = coreRadius + tilePx * 0.35;
  } else if (proximity === "halo-loose") {
    // Near outer edge of halo, still inside glow
    orbit = faceSize / 2 + haloPad * 0.35;
  } else {
    // Mid glow ring — similar reach to clipboard corner
    orbit = faceSize * 0.44;
  }

  const size = Math.ceil(orbit * 2 + tilePx + 12);
  const r = size / 2;
  const positions = ACTIONS.map((_, i) => {
    const angle = (-90 + i * 90) * (Math.PI / 180);
    return {
      x: r + orbit * Math.cos(angle),
      y: r + orbit * Math.sin(angle),
    };
  });

  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="absolute inset-0" width={size} height={size} aria-hidden>
        <polygon
          points={positions.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="hsl(149 40% 35%)"
          strokeOpacity="0.35"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>

      <span
        className="relative z-[1] inline-flex items-center justify-center"
        style={{ width: faceSize, height: faceSize }}
      >
        <span className="absolute inset-[-16%] rounded-full bg-primary/20 blur-[7px]" aria-hidden />
        <span className="absolute inset-[-3%] rounded-full bg-primary/30 blur-[2px]" aria-hidden />
        <FaceCore size={faceSize} />
        <span className="absolute -bottom-0.5 -right-0.5 z-[2] rotate-6">
          <ClipboardBadge />
        </span>
      </span>

      {ACTIONS.map((action, i) => (
        <span
          key={action.id}
          title={action.label}
          className={cn(
            "absolute z-[1] flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-lg border text-[10px] font-semibold",
            proximity === "outside" ? "h-8 w-8" : "h-7 w-7",
            ACTION_TILE[tile],
          )}
          style={{ left: positions[i].x, top: positions[i].y }}
        >
          {action.icon}
        </span>
      ))}
    </span>
  );
}

/**
 * Hex orbit (6 nodes like A's crystalline hex): icons instead of letters.
 * Clipboard is a ring node (replaces N). No separate face clipboard badge.
 */
function AvatarHexOrbit({
  faceSize = 120,
  tile = "muted",
  proximity = "halo-loose",
  emphasizeClipboard = false,
}: {
  faceSize?: number;
  tile?: ActionTileTone;
  proximity?: "halo" | "halo-tight" | "halo-loose";
  emphasizeClipboard?: boolean;
}) {
  const tilePx = 30;
  const haloPad = faceSize * 0.16;
  const coreRadius = faceSize * (22 / 64);

  let orbit: number;
  if (proximity === "halo-tight") {
    orbit = coreRadius + tilePx * 0.4;
  } else if (proximity === "halo-loose") {
    orbit = faceSize / 2 + haloPad * 0.35;
  } else {
    orbit = faceSize * 0.44;
  }

  const size = Math.ceil(orbit * 2 + tilePx + 14);
  const r = size / 2;
  // Flat-top hex starting at top — same spirit as A's hex wireframe
  const positions = HEX_NODES.map((_, i) => {
    const angle = (-90 + i * 60) * (Math.PI / 180);
    return {
      x: r + orbit * Math.cos(angle),
      y: r + orbit * Math.sin(angle),
    };
  });

  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="absolute inset-0" width={size} height={size} aria-hidden>
        <polygon
          points={positions.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="hsl(149 40% 35%)"
          strokeOpacity="0.4"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>

      <span
        className="relative z-[1] inline-flex items-center justify-center"
        style={{ width: faceSize, height: faceSize }}
      >
        <span className="absolute inset-[-16%] rounded-full bg-primary/20 blur-[7px]" aria-hidden />
        <span className="absolute inset-[-3%] rounded-full bg-primary/30 blur-[2px]" aria-hidden />
        <FaceCore size={faceSize} />
      </span>

      {HEX_NODES.map((node, i) => {
        const isClipboard = node.id === "clipboard";
        return (
          <span
            key={node.id}
            title={node.label}
            className={cn(
              "absolute z-[1] flex h-[30px] w-[30px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-lg border",
              emphasizeClipboard && isClipboard
                ? "border-primary/40 bg-accent text-accent-foreground shadow-sm"
                : ACTION_TILE[tile],
            )}
            style={{ left: positions[i].x, top: positions[i].y }}
          >
            <node.Icon className="size-3.5" strokeWidth={2} aria-hidden />
            <span className="sr-only">{node.label}</span>
          </span>
        );
      })}
    </span>
  );
}

type QuietNodeStyle = "lumen" | "facet" | "loop";

/**
 * Quieter hex: one full-size workflow badge at the old Discuss (chat) slot;
 * other five nodes are deep-tech / self-improve marks — not letter icons.
 * Final mark S = mesh + white eyes + memory clipboard size 64.
 */
function AvatarHexQuiet({
  faceSize = 120,
  proximity = "halo-loose",
  nodeStyle = "lumen",
  connect = "ring",
  clipboardSize,
  badgeSize,
  whiteEyes = false,
  mood = "default",
  workflow = "memory",
  faceOverlay = "none",
  sleepZzz = true,
}: {
  faceSize?: number;
  proximity?: "halo" | "halo-tight" | "halo-loose";
  nodeStyle?: QuietNodeStyle;
  /** ring = hex perimeter; mesh = all-to-all node links */
  connect?: "ring" | "mesh";
  /** Preferred badge size; clipboardSize kept as alias for older cards. */
  badgeSize?: number;
  clipboardSize?: number;
  whiteEyes?: boolean;
  mood?: FaceMood;
  workflow?: WorkflowKind;
  faceOverlay?: "none" | "bricks";
  sleepZzz?: boolean;
}) {
  const resolvedBadge = badgeSize ?? clipboardSize ?? 34;
  const haloPad = faceSize * 0.16;
  const coreRadius = faceSize * (22 / 64);
  const clipH = resolvedBadge;
  const clipW = (28 / 34) * resolvedBadge;

  let orbit: number;
  if (proximity === "halo-tight") {
    orbit = coreRadius + 14;
  } else if (proximity === "halo-loose") {
    orbit = faceSize / 2 + haloPad * 0.35;
  } else {
    orbit = faceSize * 0.44;
  }

  const size = Math.ceil(orbit * 2 + Math.max(clipW, clipH) + 16);
  const r = size / 2;

  const BADGE_INDEX = 2;
  const positions = Array.from({ length: 6 }, (_, i) => {
    const angle = (-90 + i * 60) * (Math.PI / 180);
    return {
      x: r + orbit * Math.cos(angle),
      y: r + orbit * Math.sin(angle),
    };
  });

  const meshPairs: [number, number][] = [];
  if (connect === "mesh") {
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        meshPairs.push([i, j]);
      }
    }
  }

  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="absolute inset-0" width={size} height={size} aria-hidden>
        {connect === "ring" ? (
          <polygon
            points={positions.map((p) => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke="hsl(149 40% 35%)"
            strokeOpacity="0.38"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        ) : (
          <g stroke="hsl(149 40% 35%)" strokeOpacity="0.28" strokeWidth="1">
            {meshPairs.map(([i, j]) => (
              <line
                key={`${i}-${j}`}
                x1={positions[i].x}
                y1={positions[i].y}
                x2={positions[j].x}
                y2={positions[j].y}
              />
            ))}
          </g>
        )}
      </svg>

      <span
        className="relative z-[1] inline-flex items-center justify-center overflow-visible"
        style={{ width: faceSize, height: faceSize }}
      >
        <span className="absolute inset-[-16%] -z-10 rounded-full bg-primary/20 blur-[7px]" aria-hidden />
        <span className="absolute inset-[-3%] -z-10 rounded-full bg-primary/30 blur-[2px]" aria-hidden />
        <FaceCore
          size={faceSize}
          whiteEyes={whiteEyes}
          mood={mood}
          overlay={faceOverlay}
          sleepZzz={sleepZzz}
        />
      </span>

      {positions.map((pos, i) => {
        if (i === BADGE_INDEX) {
          return (
            <span
              key="workflow-badge"
              title={WORKFLOW_LABEL[workflow]}
              className="absolute z-[2] -translate-x-1/2 -translate-y-1/2 rotate-6"
              style={{ left: pos.x, top: pos.y }}
            >
              <WorkflowBadge workflow={workflow} size={resolvedBadge} mood={mood} />
            </span>
          );
        }

        return (
          <span
            key={`node-${i}`}
            className="absolute z-[1] -translate-x-1/2 -translate-y-1/2"
            style={{ left: pos.x, top: pos.y }}
            aria-hidden
          >
            {nodeStyle === "lumen" && (
              <span className="relative flex h-3 w-3 items-center justify-center">
                <span className="absolute inset-0 rounded-full bg-primary/25 blur-[3px]" />
                <span className="relative h-2 w-2 rounded-full bg-[#e8f5ec] ring-1 ring-primary/50" />
              </span>
            )}
            {nodeStyle === "facet" && (
              <svg width="14" height="14" viewBox="0 0 14 14">
                <polygon
                  points="7,1 12.5,4.2 12.5,9.8 7,13 1.5,9.8 1.5,4.2"
                  fill="hsl(120 14% 97%)"
                  stroke="#014421"
                  strokeOpacity="0.55"
                  strokeWidth="1"
                />
                <circle cx="7" cy="7" r="1.3" fill="#014421" fillOpacity="0.45" />
              </svg>
            )}
            {nodeStyle === "loop" && (
              <svg width="16" height="16" viewBox="0 0 16 16">
                <circle
                  cx="8"
                  cy="8"
                  r="5.5"
                  fill="none"
                  stroke="#014421"
                  strokeOpacity="0.35"
                  strokeWidth="1.2"
                  strokeDasharray="3 2.5"
                />
                <circle cx="8" cy="8" r="2.2" fill="#e8f5ec" stroke="#014421" strokeOpacity="0.5" strokeWidth="1" />
              </svg>
            )}
          </span>
        );
      })}
    </span>
  );
}

/** Locked Final Mark S — production AgentMark so exploration cards stay in sync. */
function FinalMarkS(props: {
  mood?: AgentMarkMood;
  workflow?: AgentMarkWorkflow;
}) {
  return <AgentMark size="lg" mood={props.mood} workflow={props.workflow} />;
}

/** D — Softer assistant: face, clipboard tucked, actions as linked pills on one arc. */
function AvatarD({ size = 160 }: { size?: number }) {
  return (
    <span className="relative inline-flex flex-col items-center" style={{ width: size }}>
      <span className="relative inline-flex items-center justify-center" style={{ width: size * 0.7, height: size * 0.7 }}>
        <span className="absolute inset-[-12%] rounded-full bg-primary/16 blur-[6px]" aria-hidden />
        <FaceCore size={size * 0.55} />
        <span className="absolute -bottom-1 -right-1 rotate-[8deg]">
          <ClipboardBadge />
        </span>
      </span>
      <div className="mt-3 flex items-center gap-0">
        {ACTIONS.map((action, i) => (
          <div key={action.id} className="flex items-center">
            <span className="flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2 text-[10px] font-medium text-foreground shadow-sm">
              <span className="text-primary">{action.icon}</span>
              {action.label}
            </span>
            {i < ACTIONS.length - 1 && (
              <span className="mx-0.5 h-px w-2 bg-primary/30" aria-hidden />
            )}
          </div>
        ))}
      </div>
    </span>
  );
}

const VARIANTS: {
  id: VariantId;
  title: string;
  note: string;
  render: () => ReactNode;
}[] = [
  {
    id: "A",
    title: "Original orb",
    note: "Halo + crystalline wireframe — closest to the first draft you liked.",
    render: () => <AvatarA />,
  },
  {
    id: "B",
    title: "Orb + clipboard",
    note: "Drops FJ wireframe. Clipboard reads as assistant / capture.",
    render: () => <AvatarB />,
  },
  {
    id: "C",
    title: "Halo + clipboard + orbit (card tiles)",
    note: "A’s face/halo proportions; four card tiles sit outside the halo.",
    render: () => <AvatarOrbit tile="card" />,
  },
  {
    id: "D",
    title: "Clipboard + action strip",
    note: "Less FJ orbit. Actions as a linked strip under the face.",
    render: () => <AvatarD />,
  },
  {
    id: "E",
    title: "Orbit · muted tiles",
    note: "Same as C, soft muted panel squares — quieter than white cards.",
    render: () => <AvatarOrbit tile="muted" />,
  },
  {
    id: "F",
    title: "Orbit · primary tiles",
    note: "Same as C, solid brand-green squares with white letters.",
    render: () => <AvatarOrbit tile="primary" />,
  },
  {
    id: "G",
    title: "Orbit · accent tiles",
    note: "Same as C, sage accent fill — soft green without solid primary.",
    render: () => <AvatarOrbit tile="accent" />,
  },
  {
    id: "H",
    title: "E + white eyes · tiles in halo",
    note: "Muted tiles tucked into the glow (clipboard distance). Eyes match A.",
    render: () => <AvatarOrbit tile="muted" proximity="halo" />,
  },
  {
    id: "I",
    title: "E · tiles tighter in halo",
    note: "Even closer to the face rim — deep inside the halo.",
    render: () => <AvatarOrbit tile="muted" proximity="halo-tight" />,
  },
  {
    id: "J",
    title: "E · tiles near halo edge",
    note: "Still inside the glow, slightly farther out than H.",
    render: () => <AvatarOrbit tile="muted" proximity="halo-loose" />,
  },
  {
    id: "K",
    title: "Hex icons · J spacing · muted",
    note: "6-node hex: Plan, Remember, Discuss, Clipboard, AI, Self-improve. Clipboard is a ring node.",
    render: () => <AvatarHexOrbit tile="muted" proximity="halo-loose" />,
  },
  {
    id: "L",
    title: "Hex icons · mid halo",
    note: "Same hex ring, slightly tighter (H-like spacing).",
    render: () => <AvatarHexOrbit tile="muted" proximity="halo" />,
  },
  {
    id: "M",
    title: "Hex icons · clipboard accent",
    note: "Same as K; clipboard node softly highlighted as the capture/notes home.",
    render: () => (
      <AvatarHexOrbit tile="muted" proximity="halo-loose" emphasizeClipboard />
    ),
  },
  {
    id: "N",
    title: "Hex quiet · lumen nodes",
    note: "Full-size clipboard at chat slot. Other five = soft luminous vertices (deep tech).",
    render: () => <AvatarHexQuiet proximity="halo-loose" nodeStyle="lumen" clipboardSize={42} />,
  },
  {
    id: "O",
    title: "Hex quiet · facet nodes",
    note: "Same layout; tiny hex facets on the ring — crystalline / deep tech.",
    render: () => <AvatarHexQuiet proximity="halo-loose" nodeStyle="facet" clipboardSize={42} />,
  },
  {
    id: "P",
    title: "Hex quiet · loop nodes",
    note: "Same layout; nested dashed rings — self-improving loop marks.",
    render: () => <AvatarHexQuiet proximity="halo-loose" nodeStyle="loop" clipboardSize={42} />,
  },
  {
    id: "Q",
    title: "N + all-to-all mesh",
    note: "Same as N (lumen + clipboard), but every node links to every other node.",
    render: () => (
      <AvatarHexQuiet
        proximity="halo-loose"
        nodeStyle="lumen"
        connect="mesh"
        clipboardSize={42}
      />
    ),
  },
  {
    id: "R",
    title: "Q + bigger clipboard + pure white eyes",
    note: "Same mesh as Q; clipboard larger (52 vs 42); larger pure-white eye discs.",
    render: () => (
      <AvatarHexQuiet
        proximity="halo-loose"
        nodeStyle="lumen"
        connect="mesh"
        clipboardSize={52}
        whiteEyes
      />
    ),
  },
  {
    id: "S",
    title: "Final mark",
    note: "Locked: mesh + true white eyes + memory clipboard (64).",
    render: () => <FinalMarkS />,
  },
];

const EXPRESSION_VARIANTS: {
  id: VariantId;
  title: string;
  note: string;
  render: () => ReactNode;
}[] = [
  {
    id: "sleep",
    title: "Sleeping",
    note: "Idle / waiting. Closed lids; ZZZ drawn on the face (first Z white); moon on clipboard.",
    render: () => <FinalMarkS mood="sleeping" />,
  },
  {
    id: "think",
    title: "Working on request",
    note: "Straight inward brows, pupils looking right, spinner on clipboard. No dots.",
    render: () => <FinalMarkS mood="thinking" />,
  },
  {
    id: "doh",
    title: "Doh · error",
    note: "X eyes, no mouth. Warning triangle with ! on the clipboard.",
    render: () => <FinalMarkS mood="doh" />,
  },
  {
    id: "happy",
    title: "Happy",
    note: "Success / saved. Bright eyes + smile.",
    render: () => <FinalMarkS mood="happy" />,
  },
];

const WORKFLOW_VARIANTS: {
  id: VariantId;
  title: string;
  note: string;
  render: () => ReactNode;
}[] = [
  {
    id: "wf-memory",
    title: "Update memory",
    note: "Clipboard badge — capture lesson results into wiki memory.",
    render: () => <FinalMarkS workflow="memory" />,
  },
  {
    id: "wf-plan",
    title: "Create lesson plan",
    note: "Checklist / plan sheet on the badge — draft the next lesson or assessment.",
    render: () => <FinalMarkS workflow="plan" />,
  },
  {
    id: "wf-sweep",
    title: "Memory sweep",
    note: "Sleeping lids (no ZZZ); left side broken as bricks with flying bricks assembling in; update mark on clipboard.",
    render: () => <FinalMarkS workflow="sweep" />,
  },
];

type CardSpec = {
  id: VariantId;
  title: string;
  note: string;
  render: () => ReactNode;
};

function VariantCard({
  v,
  picked,
  onPick,
}: {
  v: CardSpec;
  picked: VariantId;
  onPick: (id: VariantId) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(v.id)}
      className={cn(
        "flex flex-col items-center rounded-xl border bg-card p-6 text-left shadow-sm transition outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
        picked === v.id ? "border-primary/50 shadow-md" : "border-border hover:border-primary/30",
      )}
      aria-pressed={picked === v.id}
    >
      <div className="flex min-h-44 w-full items-center justify-center py-4">{v.render()}</div>
      <div className="mt-2 w-full border-t border-border pt-4">
        <div className="text-sm font-semibold text-foreground">
          {v.id}. {v.title}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{v.note}</p>
      </div>
    </button>
  );
}

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-12">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{eyebrow}</p>
      <h2 className="mt-1 text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  );
}

export default function AgentAvatarVariantsPage() {
  const [picked, setPicked] = useState<VariantId>("S");
  const all = [...VARIANTS, ...EXPRESSION_VARIANTS, ...WORKFLOW_VARIANTS];
  const current = all.find((v) => v.id === picked);

  return (
    <div className="notepad-canvas min-h-[calc(100vh-3.5rem)] px-6 py-10">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Avatar exploration
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Agent mark variants</h1>
          <p className="mt-3 text-muted-foreground">
            <span className="font-medium text-foreground">S</span> is the locked final mark. Below:
            expression states for runtime feedback, then workflow badges (clipboard = update memory).
          </p>
          {current && (
            <p className="mt-3 text-sm text-foreground">
              Current pick: <span className="font-semibold">{picked}</span> — {current.title}
            </p>
          )}
        </header>

        <Section eyebrow="Final" title="Locked mark (S)">
          <VariantCard v={VARIANTS[VARIANTS.length - 1]} picked={picked} onPick={setPicked} />
        </Section>

        <Section eyebrow="Expressions" title="Runtime moods">
          {EXPRESSION_VARIANTS.map((v) => (
            <VariantCard key={v.id} v={v} picked={picked} onPick={setPicked} />
          ))}
        </Section>

        <Section eyebrow="Workflows" title="Badge swaps by workflow">
          {WORKFLOW_VARIANTS.map((v) => (
            <VariantCard key={v.id} v={v} picked={picked} onPick={setPicked} />
          ))}
        </Section>

        <Section eyebrow="Archive" title="Earlier exploration (A–R)">
          {VARIANTS.slice(0, -1).map((v) => (
            <VariantCard key={v.id} v={v} picked={picked} onPick={setPicked} />
          ))}
        </Section>
      </div>
    </div>
  );
}
