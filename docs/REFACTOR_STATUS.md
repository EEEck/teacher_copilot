# Architecture refactor — complete

**Branch:** `cursor/llm-wiki-integration`  
**Status:** MVP refactor **done** (2026-05-29). Further work is product features (exams, E2E, production deploy), not another structural rewrite.

## Delivered

| Phase | Outcome |
|-------|---------|
| **0** | Typed API errors, safe prompt rendering, offline pytest + agent stub |
| **1** | `ArtifactSessionService` + `ArtifactSpec`; unified frontend session page/runtime; async structured chat turns |
| **2** | SSE streaming (reasoning + tools); Design B draft from `final`; session recovery in UI |
| **3** | `wiki/` package + `WikiStore` facade (`0b56b08`) |
| **4** | Shared `MarkdownEditorPanel`; OpenAI bootstrap documented; **sessions stay in RAM** (see below) |
| **5** | Ingest HITL: only `approved: true` paths written; read API + viewer; post-commit UX; Cursor-style file review + editable commit (`9f6914e`) |

## Intentionally not in the prototype

- **SQLite / DB session store** — ingest/plan sessions are in-memory. Restarting the backend clears server session IDs; the client keeps draft markdown and starts a new session. Add persistence when you need multi-worker or durable server-side chat history.
- **Playwright E2E** — deferred; use `.\scripts\test.ps1` (pytest + tsc + Vitest).
- **New artifact types** (exam, student report) — seams exist (`ArtifactSpec`); implementations are follow-on work.

## Verify locally

```powershell
.\scripts\test.ps1
```

Expect ~46 backend tests and frontend Vitest (`sse-chat` parser).

## North star (unchanged)

New capability = one `ArtifactSpec` + mode footer — not new duplicated pages/services/providers.
