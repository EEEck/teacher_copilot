"use client";

import { useId, type ReactNode } from "react";
import { AlertTriangle, ListChecks, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";

export type AgentMarkMood = "default" | "sleeping" | "thinking" | "doh" | "happy";
export type AgentMarkWorkflow = "memory" | "plan" | "sweep";

export const AGENT_MARK_MOODS = [
  "default",
  "sleeping",
  "thinking",
  "doh",
  "happy",
] as const satisfies readonly AgentMarkMood[];

export const AGENT_MARK_WORKFLOWS = [
  "memory",
  "plan",
  "sweep",
] as const satisfies readonly AgentMarkWorkflow[];

export type AgentMarkProps = {
  className?: string;
  /** Pixel face size or presets (sm≈72, md≈96, lg≈120). Mesh orbit makes the total mark larger. Ignored when `boxSize` is set. */
  size?: "sm" | "md" | "lg" | number;
  /**
   * Fit the canonical Final Mark S (`size="lg"`) into this outer box (px).
   * Keeps agent-avatars proportions — use for FABs/chips next to fixed controls.
   */
  boxSize?: number;
  title?: string;
  mood?: AgentMarkMood;
  workflow?: AgentMarkWorkflow;
  /** Rare blink + soft lumen pulse. Off by default; respect prefers-reduced-motion. */
  alive?: boolean;
};

const FACE_PRESETS = {
  sm: 72,
  md: 96,
  lg: 120,
} as const;

/** Badge size relative to face — locked S uses 64 at face 120. */
const BADGE_RATIO = 64 / 120;

/** Natural outer box for `size="lg"` (face 120) — used by `boxSize` scaling. */
export const AGENT_MARK_LG_BOX_PX = (() => {
  const faceSize = FACE_PRESETS.lg;
  const badgeSize = Math.round(faceSize * BADGE_RATIO);
  const haloPad = faceSize * 0.16;
  const orbit = faceSize / 2 + haloPad * 0.35;
  const clipH = badgeSize;
  const clipW = (28 / 34) * badgeSize;
  return Math.ceil(orbit * 2 + Math.max(clipW, clipH) + 16);
})();

const WORKFLOW_LABEL: Record<AgentMarkWorkflow, string> = {
  memory: "Update memory",
  plan: "Create lesson plan",
  sweep: "Memory sweep",
};

function resolveFaceSize(size: AgentMarkProps["size"]): number {
  if (typeof size === "number") return size;
  return FACE_PRESETS[size ?? "md"];
}

/** Shared face core — pure-white sclera + dark pupils; moods swap lids/mouth. */
function FaceCore({
  size,
  mood = "default",
  overlay = "none",
  sleepZzz = true,
  alive = false,
}: {
  size: number;
  mood?: AgentMarkMood;
  overlay?: "none" | "bricks";
  sleepZzz?: boolean;
  alive?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const gradId = `kp-core-${uid}`;
  const brokenClipId = `kp-broken-clip-${uid}`;
  const broken = overlay === "bricks";
  const blink = alive && (mood === "default" || mood === "happy");

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
          <g
            fill="#0a1f14"
            fillOpacity="0.45"
            stroke="hsl(149 80% 55%)"
            strokeOpacity="0.7"
            strokeWidth="0.85"
          >
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

      {broken && (
        <g>
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
          <g fill="hsl(149 85% 60%)" fillOpacity="0.55">
            <rect x="14.5" y="40.5" width="1.6" height="1.6" rx="0.3" />
            <rect x="12.2" y="46" width="1.3" height="1.3" rx="0.3" />
            <rect x="17" y="48.5" width="1.4" height="1.4" rx="0.3" />
          </g>
        </g>
      )}

      {mood === "sleeping" && (
        <g>
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
              <text x="42" y="22" fill="#ffffff" fontSize="9" style={{ fill: "#ffffff" }}>
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
          <circle cx="27.2" cy="29.2" r="1.65" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="40.2" cy="29.2" r="1.65" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="26.5" cy="28.3" r="0.55" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="39.5" cy="28.3" r="0.55" fill="#ffffff" style={{ fill: "#ffffff" }} />
        </g>
      )}

      {mood === "doh" && (
        <g>
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
          <g className={blink ? "kp-agent-blink" : undefined}>
            <circle cx="25.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
            <circle cx="38.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
            <circle cx="26.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
            <circle cx="39.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
            <circle cx="25.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
            <circle cx="38.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
          </g>
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

      {mood === "default" && (
        <g className={blink ? "kp-agent-blink" : undefined}>
          <circle cx="25.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="29" r="4.4" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="26.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="39.3" cy="28.6" r="1.7" fill="#06110c" style={{ fill: "#06110c" }} />
          <circle cx="25.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
          <circle cx="38.5" cy="27.6" r="0.6" fill="#ffffff" style={{ fill: "#ffffff" }} />
        </g>
      )}
    </svg>
  );
}

function ClipboardBadge({
  size = 34,
  motif = "lines",
}: {
  size?: number;
  motif?: "lines" | "moon" | "spinner";
}) {
  const height = size;
  const width = (28 / 34) * size;
  return (
    <svg viewBox="0 0 28 34" className="drop-shadow-sm" width={width} height={height} aria-hidden>
      <rect x="4" y="6" width="20" height="26" rx="3" fill="#f7f9f7" stroke="#014421" strokeWidth="1.5" />
      <rect x="9" y="2" width="10" height="7" rx="2" fill="#014421" />
      {motif === "lines" && (
        <path
          d="M9 16h10M9 21h10M9 26h6"
          stroke="#014421"
          strokeWidth="1.4"
          strokeLinecap="round"
          opacity="0.55"
        />
      )}
      {motif === "moon" && (
        <g>
          <circle cx="14" cy="20.5" r="5.2" fill="#014421" fillOpacity="0.9" />
          <circle cx="16.2" cy="19.2" r="4.4" fill="#f7f9f7" />
          <circle cx="10.2" cy="26.2" r="0.7" fill="#014421" fillOpacity="0.45" />
          <circle cx="18.8" cy="26.8" r="0.55" fill="#014421" fillOpacity="0.35" />
          <circle cx="20.5" cy="24.2" r="0.45" fill="#014421" fillOpacity="0.3" />
        </g>
      )}
      {motif === "spinner" && (
        <g transform="translate(14 21)">
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
        className="absolute left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center text-primary"
        style={{ top: iconTop, width: icon, height: icon }}
      >
        {children}
      </span>
    </span>
  );
}

function PlanBadge({ size }: { size: number }) {
  const icon = Math.round(size * 0.44);
  return (
    <BadgeBoard size={size} iconTop="58%">
      <ListChecks width={icon} height={icon} strokeWidth={2.35} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

function SweepBadge({ size }: { size: number }) {
  const icon = Math.round(size * 0.42);
  return (
    <BadgeBoard size={size} iconTop="57%">
      <RefreshCw width={icon} height={icon} strokeWidth={2.4} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

function WarningBadge({ size }: { size: number }) {
  const icon = Math.round(size * 0.42);
  return (
    <BadgeBoard size={size} iconTop="57%">
      <AlertTriangle width={icon} height={icon} strokeWidth={2.4} absoluteStrokeWidth />
    </BadgeBoard>
  );
}

function WorkflowBadge({
  workflow,
  size,
  mood,
}: {
  workflow: AgentMarkWorkflow;
  size: number;
  mood: AgentMarkMood;
}) {
  if (mood === "doh") return <WarningBadge size={size} />;
  if (workflow === "plan") return <PlanBadge size={size} />;
  if (workflow === "sweep") return <SweepBadge size={size} />;
  const motif =
    mood === "sleeping" ? "moon" : mood === "thinking" ? "spinner" : "lines";
  return <ClipboardBadge size={size} motif={motif} />;
}

/**
 * Locked KlassenPilot agent mark (Final Mark S): mesh hex + lumen nodes + soft halo,
 * pure-white eyes above the blur, clipboard workflow badge.
 *
 * Plug-and-play:
 * ```tsx
 * import { EEEck, EEEckThinking, AgentMark } from "@/components/klassenpilot/agent-mark";
 * <EEEck size="lg" />
 * <EEEckThinking boxSize={76} />           // same proportions as /dev/agent-avatars, scaled
 * <AgentMark mood="happy" workflow="plan" alive />
 * ```
 */
export function AgentMark({
  className,
  size = "md",
  boxSize,
  title = "KlassenPilot agent",
  mood: moodProp,
  workflow = "memory",
  alive = false,
}: AgentMarkProps) {
  // boxSize always composes at lg so FAB/chip marks match agent-avatars proportions.
  if (boxSize != null && boxSize > 0) {
    const scale = boxSize / AGENT_MARK_LG_BOX_PX;
    return (
      <span
        className={cn(
          "inline-flex shrink-0 items-center justify-center overflow-visible",
          className,
        )}
        style={{ width: boxSize, height: boxSize }}
      >
        <span
          className="pointer-events-none inline-flex origin-center"
          style={{ transform: `scale(${scale})` }}
        >
          <AgentMarkGlyph
            size="lg"
            title={title}
            mood={moodProp}
            workflow={workflow}
            alive={alive}
          />
        </span>
      </span>
    );
  }

  return (
    <AgentMarkGlyph
      className={className}
      size={size}
      title={title}
      mood={moodProp}
      workflow={workflow}
      alive={alive}
    />
  );
}

function AgentMarkGlyph({
  className,
  size = "md",
  title = "KlassenPilot agent",
  mood: moodProp,
  workflow = "memory",
  alive = false,
}: Omit<AgentMarkProps, "boxSize">) {
  const isSweep = workflow === "sweep";
  const mood = moodProp ?? (isSweep ? "sleeping" : "default");
  const faceOverlay = isSweep ? "bricks" : "none";
  const sleepZzz = !isSweep;
  const faceSize = resolveFaceSize(size);
  const badgeSize = Math.round(faceSize * BADGE_RATIO);

  const haloPad = faceSize * 0.16;
  const clipH = badgeSize;
  const clipW = (28 / 34) * badgeSize;
  const orbit = faceSize / 2 + haloPad * 0.35;
  const markSize = Math.ceil(orbit * 2 + Math.max(clipW, clipH) + 16);
  const r = markSize / 2;
  const BADGE_INDEX = 2;

  const positions = Array.from({ length: 6 }, (_, i) => {
    const angle = (-90 + i * 60) * (Math.PI / 180);
    return {
      x: r + orbit * Math.cos(angle),
      y: r + orbit * Math.sin(angle),
    };
  });

  const meshPairs: [number, number][] = [];
  for (let i = 0; i < positions.length; i++) {
    for (let j = i + 1; j < positions.length; j++) {
      meshPairs.push([i, j]);
    }
  }

  return (
    <span
      role="img"
      aria-label={title}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: markSize, height: markSize }}
    >
      <svg className="absolute inset-0" width={markSize} height={markSize} aria-hidden>
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
      </svg>

      <span
        className="relative z-[1] inline-flex items-center justify-center overflow-visible"
        style={{ width: faceSize, height: faceSize }}
      >
        <span className="absolute inset-[-16%] -z-10 rounded-full bg-primary/20 blur-[7px]" aria-hidden />
        <span className="absolute inset-[-3%] -z-10 rounded-full bg-primary/30 blur-[2px]" aria-hidden />
        <FaceCore
          size={faceSize}
          mood={mood}
          overlay={faceOverlay}
          sleepZzz={sleepZzz}
          alive={alive}
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
              <WorkflowBadge workflow={workflow} size={badgeSize} mood={mood} />
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
            <span
              className={cn(
                "relative flex h-3 w-3 items-center justify-center",
                alive && "kp-agent-node-pulse",
              )}
              style={alive ? { animationDelay: `${i * 0.45}s` } : undefined}
            >
              <span className="absolute inset-0 rounded-full bg-primary/25 blur-[3px]" />
              <span className="relative h-2 w-2 rounded-full bg-[#e8f5ec] ring-1 ring-primary/50" />
            </span>
          </span>
        );
      })}
    </span>
  );
}

/** Props for named EEEck mood shortcuts (mood is fixed). */
export type EEEckProps = Omit<AgentMarkProps, "mood" | "title"> & {
  title?: string;
};

function eeeck(
  mood: AgentMarkMood,
  { title = "EEEck", size = "lg", ...rest }: EEEckProps,
) {
  return <AgentMark {...rest} size={size} mood={mood} title={title} />;
}

/** Default EEEck — Final Mark S (`size="lg"`). Pass `boxSize` for FAB/chip fit. */
export function EEEck(props: EEEckProps) {
  return eeeck("default", props);
}

export function EEEckSleeping(props: EEEckProps) {
  return eeeck("sleeping", props);
}

export function EEEckThinking(props: EEEckProps) {
  return eeeck("thinking", props);
}

export function EEEckDoh(props: EEEckProps) {
  return eeeck("doh", props);
}

export function EEEckHappy(props: EEEckProps) {
  return eeeck("happy", props);
}

/** Pick a mood component by id — handy for dynamic UI. */
export const EEECK_BY_MOOD: Record<AgentMarkMood, typeof EEEck> = {
  default: EEEck,
  sleeping: EEEckSleeping,
  thinking: EEEckThinking,
  doh: EEEckDoh,
  happy: EEEckHappy,
};
