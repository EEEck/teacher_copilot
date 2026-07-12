# KlassenPilot Frontend Design

Lightweight design rules for app screens and [assistant-ui](https://github.com/assistant-ui/assistant-ui) chat. One token file drives everything: [`src/app/globals.css`](src/app/globals.css).

## Principles

1. **White is the default canvas** — page, cards, composer, assistant messages.
2. **`muted` is for fills** — user chat bubbles, highlight callouts, code blocks (assistant-ui convention).
3. **Green is scarce** — brand logo, send button, one primary CTA per action group.
4. **Borders + shadow for structure** — `border-border shadow-sm`, not gray card backgrounds.
5. **Tokens, not hex in components** — use `bg-card`, `bg-muted`, `text-primary`, etc.

## Component layers

| Layer | Path | Role |
|-------|------|------|
| Tokens | `src/app/globals.css` | shadcn semantic CSS variables |
| Primitives | `src/components/ui/` | Button, Card, Alert, SegmentedToggle, … |
| Features | `src/features/` | Cross-route draft/job ownership (workflow drafts) |
| Chat | `src/components/assistant-ui/` | Thread, markdown (from assistant-ui registry) |
| Domain | `src/components/klassenpilot/` | Timeline, checklist, wiki cards, pending jobs |
| Pages | `src/app/` | Routes compose domain + ui + chat |

Update assistant-ui components: `npx assistant-ui add thread -o -p src/components/assistant-ui`

## Palette (primitives)

| Name | Hex | Token |
|------|-----|-------|
| Background | `#FFFFFF` | `--background`, `--card` |
| Text | `#0A0D0A` | `--foreground` |
| Brand | `#014421` | `--primary`, `--ring` |
| Muted text | `#526359` | `--muted-foreground` |
| Panel gray | `#F7F9F7` | `--muted` |
| Border | `#DDE5DE` | `--border` |
| Error | `#B42318` | `--destructive` |

## Surfaces

| Variant | Classes | Use |
|---------|---------|-----|
| **Default** | `Card` (default) → `bg-card` white | Class list, stat cards, timeline, diary checklist |
| **Highlight** | `Card variant="highlight"` → `bg-muted` | Top misconceptions, info alerts |
| **Chat canvas** | `bg-background` | Thread root, composer (assistant-ui) |
| **User bubble** | `bg-muted` | User messages in Thread (do not override) |

## Review Surfaces

Memory review, plan save review, and Memory Sweep are operational surfaces, not
marketing cards. Put the plain-language brief first, then expose detailed diffs
or raw review cards as drill-down. Keep action rows stable while teachers make
decisions: one primary submit button, uniform secondary actions, and no nested
cards inside the brief.

Current helpers:

- `components/klassenpilot/review/review-brief.tsx` for wiki-file review.
- `components/klassenpilot/memory-sweep-brief.tsx` for sweep decisions
  (default Simple triage; `SegmentedToggle` Simple / Detailed for full cards).
- `lib/review-brief.ts` and `lib/sweep-brief.ts` for grouping and labels.

## Background jobs

Durable backend work that outlives the current page (chat turns, Memory Sweep
generation) uses a small fixed Running box (`running-tasks-box.tsx`): numbered
zebra rows, thin separators, one dismiss control. Prefer that over toasts-only
feedback while a job is still running.

## Buttons

| Variant | Look | Use |
|---------|------|-----|
| `default` | Green fill | Primary CTA, chat send button |
| `outline` | White + border | Secondary actions (“Create lesson plan”) |
| `destructive` | Red tint | Delete / errors |

**Rule:** One green `default` button per action row. Use `ActionLink` with `primary` prop for the main action.

## Segmented controls

Use [`SegmentedToggle`](src/components/ui/segmented-toggle.tsx) for mutually exclusive modes (e.g. Edit / Preview, Memory Sweep Simple / Detailed). Do not copy toggle classes into feature components.

| Part | Tokens / classes |
|------|------------------|
| Track | `rounded-md`, `border-border`, `p-0.5` |
| Active segment | `rounded`, `bg-muted`, `font-medium`, `text-foreground` |
| Inactive segment | `text-muted-foreground` |
| Avoid | `bg-accent`, `text-accent-foreground`, or `Button variant="default"` (no green on segments) |

```tsx
import { SegmentedToggle } from "@/components/ui/segmented-toggle";

<SegmentedToggle
  value={mode}
  onValueChange={setMode}
  options={[
    { value: "preview", label: "Preview" },
    { value: "edit", label: "Edit" },
  ]}
  size="sm"
  aria-label="View mode"
/>
```

## assistant-ui alignment

The Thread reads the same tokens as the app:

- Thread / composer: `bg-background`
- User messages: `bg-muted`
- Send: `Button variant="default"` → `bg-primary`
- Focus rings: `ring-ring` (brand green)

Customize brand by editing `--primary` and `--ring` in `globals.css` only.

## Out of scope (v1.0)

- Dark mode
- Separate chat color theme
- Storybook / Figma token pipeline
