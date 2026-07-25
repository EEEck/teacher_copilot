# Teacher wiki package

Deterministic markdown wiki for KlassenPilot: compile lesson diaries, human-in-the-loop commit, index rebuild, and REST/dashboard read APIs.

## Layout

| Module | Responsibility |
|--------|----------------|
| `constants.py` | Class registry, section headings, log/index regexes, `dedupe_wiki_proposals` |
| `parsing.py` | Pure diary/lesson/log markdown parsers (no I/O) |
| `paths_io.py` | Paths, read/write, `resolve_path`, `read_wiki_page` |
| `search.py` | Deterministic class relevance corpus, BM25-style `find_in_memory`, `list_class_pages` |
| `registry.py` | Class list and metadata |
| `read_api.py` | Timeline, snapshot, lesson detail, revise |
| `diary.py` | Diary completeness checklist |
| `rollups.py` | Roll-up compile helpers (course state, students, timeline) |
| `commit.py` | `compile_from_diary`, `commit_ingest`, lesson plans |
| `memory.py` | Compact class memory pages, local copilot profile helpers, compaction commits |
| `context_packs.py` | Agent prompt context bundles and read-only workflow query packs |
| `subject_frameworks.py` | Shared subject teaching-framework pages (immutable guidance, not write targets) |
| `trusted_sources.py` | Trusted-source library: class allow-list, compact source TOC/profile, and list/search/read access |
| `indexing.py` | `log.md`, `index.md` rebuild |
| `store.py` | `WikiStore` facade delegating to modules |

`wiki_store.py` at package parent re-exports `WikiStore` and constants for backward compatibility.

## Boundaries

- **This package** — trusted writes after teacher approval, deterministic compile, index/log maintenance.
- **`tools.py`** — read-only agent tools (`recall_lesson`, `find_in_memory`, `read_memory_page`).
- **Dashboard** — uses REST (`get_timeline`, `get_snapshot`); does not require agent tools.

Agents should read `index.md` first (via prompt context or tools), then open specific pages.

## Facade Conventions

Application services should call public `WikiStore` methods for cross-package
operations. Keep private `_...` facade methods available for wiki package
internals and compatibility, but do not add new service-layer calls to them.
For example, services use `extract_title()` and `extract_date_from_diary()`
instead of `_extract_title()` / `_extract_date_from_diary()`.
