# Beta mini-profile (level 1)

Short design for tester identity chrome in beta mode — not full account ops.

## Goals

- After invite login, testers **must** set a display name once before using the app.
- Header shows a **letter avatar** (first letter of display name) linking to profile.
- Profile page feels like a small account surface: name + honest lightweight stats from existing beta telemetry.
- No fake product analytics; omit metrics rather than invent them.

## Data model

Extend `tester` in `beta.sqlite3`:

| Field | Purpose |
|-------|---------|
| `display_label` | Tester-chosen display name (existing column; provision may pre-seed but does not complete onboarding) |
| `profile_completed_at` | Non-null when tester submitted onboarding |

`profile_complete` = `profile_completed_at IS NOT NULL`.

## API

Extend `GET /api/beta/me` and login response (`BetaIdentityResponse`):

- `display_name`, `profile_complete`, `member_since` (tester `created_at`)
- `stats`: `{ feedback_notes, workflow_sessions, wiki_commits }` from existing beta tables

New `PATCH /api/beta/profile` body `{ display_name }` — sets name, marks profile complete, returns updated identity.

## UX flow

1. `/beta/login` → invite code → if `!profile_complete` → `/beta/profile?next=…`
2. Profile onboarding: single required name field → save → redirect to `next` or `/`
3. App shell: `BetaProfileGate` redirects incomplete sessions away from app routes
4. Header: letter avatar dropdown → Profile, Log out; hamburger keeps Docs / Feedback / Settings

## Out of scope

- School/subject forms, avatar upload, settings migration, Railway deploy docs.
