# Memory V4 Codex Hardening Design

Status: proposed design for review
Date: 2026-07-17
Scope: durable-memory capture, ledger admission, Memory Sweep, and curated
memory Markdown pages
Out of scope: storing or replaying the full chat transcript

## 0. Central design in one page

KlassenPilot should treat durable memory as a controlled promotion pipeline,
not as an automatic side effect of chat:

```text
teacher language
    -> semantic interpretation by the model
    -> deterministic provenance and policy checks
    -> review-only candidate ledger
    -> second semantic review by Memory Sweep
    -> teacher approval
    -> curated Markdown memory pages
```

The curated wiki is the durable memory. The ledger is only a staging and
evidence layer. A candidate can be useful without being true, and a model can
classify a sentence plausibly without being authorized to write it. Keeping
those distinctions explicit is the main design safety property.

The model is responsible for understanding language: speech act, scope,
independent claims, and semantic consistency. The backend is responsible for
trust: where the evidence came from, whether the quote is real, whether the
target is allowed, whether the candidate is duplicated, and whether it can
enter the fast lane. Memory Sweep is a second model judgment, not a hidden
write path. The teacher remains the final authority before curated Markdown
changes.

## 0.1 Best-practice principles

These principles guide every change in this document:

1. **Separate interpretation from authorization.** A model may propose
   `store_request`; only backend policy can decide whether it is eligible for
   fast lane or durable review.
2. **Use explicit abstention.** `unknown`, `ignore`, and `needs_review` are
   successful outcomes. The model must not invent a known category to complete
   a schema.
3. **Never use keywords as permissions.** Words such as “always” or “from now
   on” can be evidence for the model, but they cannot authorize memory.
4. **Preserve evidence, not transcripts.** Store the selected teacher quote,
   origin reference, scope, and occasion metadata. Full chat-history storage is
   out of scope.
5. **Capture broadly, promote narrowly.** A weak signal may enter the
   review-only ledger; fast lane is reserved for clear, teacher-originated,
   well-grounded standing requests.
6. **Make the second review meaningful.** Memory Sweep must be able to
   downgrade, merge, reject, or mark a candidate already covered. It must not
   see only candidates that already passed every important gate.
7. **Prefer idempotent no-ops to clever merging.** Exact duplicates, repeated
   tool calls, and already-covered claims should be safe and boring.
8. **Bound operational load without corrupting meaning.** Use one capture batch
   per teacher message and group related claims. Numeric limits are safety
   valves, not semantic rules.
9. **Keep scope separate from target.** `block` or `class` describes validity;
   `teaching_patterns.md` or `copilot_profile.md` describes storage purpose.
10. **Teacher approval is the durable-write boundary.** No chat turn, capture
    hook, or Sweep call writes curated Markdown directly.

## 0.2 Four-stage control model

The central pipeline is more precise when split into four decisions:

```text
teacher message
    ↓
LLM extracts possible memory claims
    ↓
Admission: is this valid teacher-originated evidence?
    ↓
Priority: is it clearly explicit and worth showing early?
    ↓
ledger → Sweep: merge, downgrade, reject, or propose
    ↓
Apply: did the teacher approve the proposed curated-memory change?
    ↓
curated memory.md / profile Markdown
```

### Admission

Admission asks only whether the item is a defensible piece of teacher-originated
evidence. It checks origin, exact quote, supported target, non-empty claim,
scope shape, and duplicate identity. Admission does not mean the claim is true
or that it should be shown immediately.

### Priority

Priority asks whether the admitted item is clearly an explicit standing request
and deserves early attention. This is the fast lane. It is deliberately
selective and is never granted by a keyword, model self-confidence alone, or a
valid quote that does not support the claim.

### Sweep

Sweep is the second semantic judge. It considers the admitted evidence alongside
curated Markdown and related ledger signals. It can merge, downgrade, reject,
mark already covered, or propose a new/update operation. A singleton may be
low priority without being discarded before Sweep sees it.

### Apply

Apply is the only durable-write boundary. The teacher approves the proposed
operation, then deterministic code writes the bounded curated Markdown page and
closes the originating ledger evidence. A successful Sweep proposal is not an
applied memory change.

## 0.3 Shared memory-classification context package

Speech-act and scope classification must be context-aware. The model should
not classify a sentence in isolation when the meaning depends on an earlier
turn, an omitted referent, the current lesson block, or the workflow state.
At the same time, full transcript replay is out of scope. The solution is one
explicit, traceable context contract shared by Plan, Update Memory, and Class
Discussion.

The technical terms are **structured runtime state**, **state patch**, and
**compact context pack**. This is not an opaque conversation-summary blob:

```text
bounded recent conversation
    + workflow-specific structured runtime state
    + compact teacher/class memory
    + compact evidence briefs
    + existing review candidates
    + current artifact or task context when the workflow has one
    -> MemoryClassificationContext
```

The proposed shared package is conceptually:

```python
class MemoryClassificationContext(BaseModel):
    workflow: Literal["plan", "ingest", "discuss"]
    current_teacher_message: str          # verbatim and authoritative
    recent_conversation: list[ChatMessage] # last 8 teacher turns + replies
    teacher_context: str                  # compact global teacher layer
    active_class_core: str                # compact class/subject memory
    workflow_state: dict                  # typed Plan/Memory/Discussion state
    current_artifact: str = ""            # plan or diary, when applicable
    task_context: str = ""                # ingest continuity, when applicable
    evidence_briefs: list[EvidenceBrief] = []
    memory_candidates: list[MemoryCandidate] = []
```

Every section must retain a source label in the trace. Teacher text,
assistant text, wiki text, tool output, and runtime state are evidence of
different authority and must not be blended silently.

### Workflow-specific state

| Workflow | Structured runtime state in the classification pack |
|---|---|
| Plan | `PlanRuntime`: `SessionState`, `LessonPlanningState`, evidence briefs, raw refs, candidates |
| Update Memory | `MemoryRuntime`: target state, session state, lesson-result state, evidence briefs, raw refs, candidates |
| Discuss | `ClassDiscussionRuntime`: `ClassDiscussionState`, evidence briefs, raw refs, candidates |

`ClassDiscussionState` is the compact working memory for Discuss when there
is no plan or diary. Its fields are `current_focus`, `answered_questions`,
`key_observations`, `confusion_signals`, `open_questions`, and
`next_best_actions`. The model proposes a `ClassDiscussionStatePatch`; the
backend validates, deduplicates, and merges it into the runtime.

### Context and authority rules

The model receives the last eight teacher turns by default, including the
interleaved assistant replies. Eight is a context window, not a memory
boundary: important decisions, questions, evidence briefs, and workflow state
must survive in the typed runtime state.

The current teacher message is included separately and is authoritative for
quote provenance. The broader context helps the model interpret speech act,
scope, references such as “that”, and whether a request is standing or
temporary. It cannot authorize a quote that is absent from the current
teacher message.

The model returns semantic proposals (`speech_act`, `scope`, `scope_label`,
claim, and exact quote). The backend computes Admission and Priority. If the
context does not support a confident interpretation, the model must return
`unknown`; it must not be prompted to choose a known class merely to fill the
schema.

Implementation status: the bounded history, workflow runtime state, compact
memory, and evidence briefs already exist in the three workflow prompt
builders, but the conceptual `MemoryClassificationContext` has not yet been
extracted as one shared production assembler. Until that refactor lands, the
workflow-specific builders remain the source of truth and V4 must not claim
that a separate classifier service or full transcript store exists.

Raw tool output is not injected by default. It remains behind `raw_ref` and
can be fetched when exact wording or provenance is needed. The package is
therefore rich enough for classification without storing or replaying the
full chat transcript.

## 0.4 Why this document is V4, not V3

Memory V3 is the historical implementation/design line. It introduced the
review-only ledger, explicit `remember(...)`, backend-owned fast-lane checks,
occasion-based reinforcement, and teacher-approved curated-memory writes.

Memory V4 is the current hardening scope documented in `docs/mem_v4/`. It keeps
that lifecycle but addresses the V4 failure mode observed in the sandbox:
semantic classification was too weakly separated from admission, lexical
markers could override speech-act uncertainty, candidates were not always
bound to their source message, and held singleton evidence was invisible to
Memory Sweep.

The previous filename `mem_v3_codex.md` was therefore a naming mistake. It was
describing post-V3 work while living under the V3 directory. This document now
belongs in `docs/mem_v4/mem_v4_codex.md`.

## 1. Executive decision

Keep the current central lifecycle:

```text
teacher message
    -> model proposes zero or more memory claims
    -> backend validates origin, quote, target, scope, and duplicates
    -> review-only ledger
    -> Memory Sweep performs a second semantic review
    -> teacher approves or rejects
    -> backend writes curated memory Markdown
```

The hardening should remain small:

1. Replace marker-word authorization with explicit semantic fields.
2. Add an explicit `unknown` value for both speech act and scope.
3. Make uncertainty a normal outcome that can never enter the fast lane.
4. Bind every candidate to the teacher message that produced it.
5. Make Memory Sweep inspect staged singleton candidates, not only candidates
   that already passed the reinforcement gate.
6. Use one capture batch per teacher message so a long generated prompt cannot
   create an uncontrolled number of ledger rows.

This is intentionally not a new classifier service or multi-agent pipeline.
The existing chat model can perform the semantic classification. Python owns
the trust boundary and promotion rules.

## 2. The important distinction: staged versus needs review

These terms describe different things.

### `staged`

`staged` means that a candidate has passed basic structural checks and has been
placed in the review-only ledger. It is evidence for later consideration, not a
wiki write and not a claim that the candidate is true.

Example:

> “This class often needs a visual model before the equation.”

The model may classify this as an `observation` with `class` or `block` scope.
It can be staged as an inferred signal. If the same pattern appears across
independent lessons, the normal promotion gate can make it eligible for Sweep.

### `needs_review`

`needs_review` means that the system found a potentially relevant claim but does
not have enough confidence to treat its interpretation as reliable. It is an
uncertainty or conflict label, not a storage lifecycle label.

Examples:

- speech act is `unknown`;
- scope is `unknown`;
- the quote is present but does not clearly support the proposed claim;
- a message mixes a temporary lesson request with a standing preference;
- two clauses imply different scopes;
- the model proposes a target that does not match the scope;
- the candidate came from assistant/tool text rather than teacher text.

Both kinds remain review-only. The difference is operational:

```text
staged + ordinary confidence
    -> may accumulate evidence and later enter Sweep

staged + needs_review
    -> never fast lane; Sweep/teacher must resolve the ambiguity
```

If the implementation wants one database status, `needs_review` can be a
boolean/reason field on a staged row. Do not create a second hidden ledger or a
second promotion path.

## 3. Minimal semantic model

The model should classify a candidate using three independent dimensions:

```python
from typing import Literal

SpeechAct = Literal[
    "conduct_request",  # standing instruction for copilot behavior
    "store_request",    # explicit request to remember/change memory
    "observation",      # report of an event, pattern, or lesson result
    "unknown",          # model is unsure; never fast lane
]

MemoryScope = Literal[
    "turn",       # this answer/turn only; never durable
    "lesson",     # this lesson or immediate artifact
    "block",      # bounded teaching block, e.g. organic chemistry
    "class",      # recurring pattern for this class
    "global",     # teacher-wide or cross-class preference
    "unknown",    # model is unsure; never fast lane
]

Admission = Literal[
    "ignore",       # no durable-memory candidate
    "stage",        # valid review-only signal
    "needs_review", # ambiguous or conflicting; blocked from fast lane
]
```

`unknown` is best practice here. It gives the model a safe answer when the
message does not fit the taxonomy. Without it, the model is pressured to invent
`store_request` or `conduct_request` simply because the output schema demands a
known label. Unknown must be treated as abstention, not as a request to ask the
model again until it chooses a known category.

The classifier should also be allowed to return `ignore` for ordinary task
requests. That is better than pretending every candidate-shaped sentence is
memory-worthy.

### Why speech act and scope must be separate

Speech act answers: “What is the teacher doing with this sentence?”
Scope answers: “How long and how broadly should the statement remain valid?”

These are not interchangeable:

| Teacher text | Speech act | Scope | Likely target |
|---|---|---|---|
| “From now on, give me the short version first.” | `conduct_request` | `global` | `teacher_profile.md` |
| “For this class, start with a worked example.” | `conduct_request` | `class` | `copilot_profile.md` |
| “During the organic chemistry block, use molecule models.” | `conduct_request` or `store_request` | `block` | `teaching_patterns.md` or `planning_brief.md` |
| “This class needed more visual support today.” | `observation` | `lesson` or `class` | `teaching_patterns.md` |
| “Remember that the class is currently in organic chemistry.” | `store_request` | `block`/course-state | usually not profile memory; derive from canonical lesson state |
| “Can you make tomorrow’s worksheet shorter?” | ordinary task request | `turn` | `ignore` |

The storage target is a third concept. `class` scope does not automatically
mean the file named `class_state.md`; that page was retired. Current routing is
by purpose:

- teacher-wide behavior -> `teacher_profile.md`;
- class-specific copilot behavior -> `copilot_profile.md`;
- how this class learns -> `teaching_patterns.md`;
- class overrides of shared subject/grade pedagogy ->
  `teaching_framework_adjustments.md`;
- current bounded planning pressure -> `planning_brief.md`;
- current unit/taught sequence -> canonical `course_state.md` and
  `timeline.md`, not profile memory.

Shared `wiki/subjects/.../teaching_frameworks/` pages are immutable reference
material and are **not** capture or apply targets. Class refinements go only to
`teaching_framework_adjustments.md` (see
[`memory_hierarchy.md` §3](../memory_hierarchy.md#3-class-teaching-framework-adjustments)).

## 4. Lesson blocks such as organic chemistry

`block` should be a first-class scope. A block is a bounded sequence inside a
class, such as:

- organic chemistry;
- mechanics;
- a three-week exam-preparation sequence;
- a unit containing several lessons.

It is narrower than `class` and broader than `lesson`.

The candidate should carry a compact block label or canonical reference, not a
full transcript:

```python
class ScopeContext(BaseModel):
    kind: MemoryScope = "unknown"
    label: str = ""              # e.g. "organic chemistry"
    canonical_ref: str = ""      # e.g. timeline/course-state reference
```

Examples:

- “During the organic chemistry block, avoid abstract orbital explanations”
  should be `block`, not `class`, unless the teacher explicitly says the rule
  applies to the whole class.
- “This class generally learns better with visual models” should be `class`.
- “For today’s introduction to alkenes” should be `lesson`.
- “I always want a concise explanation first” should be `global`.

Block-scoped evidence should usually enter the regular ledger. It should not
fast-lane into global teacher preferences. A block preference can become a
class pattern only if later evidence or teacher confirmation broadens it.

The existing canonical course/timeline state remains the source of truth for
which block is current. The memory capture path may record a block label or
reference supplied by the runtime, but it should not invent a new course state
from a keyword.

## 5. Proposed model output

Do not add a separate classifier service yet. Change the structured capture
contract so the existing model returns an explicit admission proposal:

```python
class MemoryAdmissionProposal(BaseModel):
    """Untrusted model output; backend computes the final verdict."""

    decision: Literal["ignore", "candidate"] = "ignore"
    speech_act: SpeechAct = "unknown"
    scope: MemoryScope = "unknown"
    scope_label: str = ""
    target: str = ""
    section: str = "General"
    claim: str = ""
    exact_quote: str = ""
    routing_reason: str = ""
    confidence: Literal["low", "medium", "high"] = "low"


class MemoryAdmissionResult(BaseModel):
    """Backend-owned result used for ledger conversion."""

    admission: Literal["ignore", "stage", "needs_review"]
    fast_lane: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    proposal: MemoryAdmissionProposal
```

The model may say `high`; that does not make it high-confidence. The backend
can downgrade it. The model also cannot set `fast_lane`.

The model prompt should include these rules:

```text
Use unknown when the sentence does not clearly fit a category or scope.
Do not infer a standing preference from words such as always, usually,
generally, or from now on alone.
An observation containing always is still an observation.
Return ignore for ordinary task requests.
Quote the smallest exact span of the teacher's message that supports the claim.
Never quote assistant, tool, wiki, or student text as teacher evidence.
```

## 6. Backend admission policy

The backend should make the semantic result narrower, not more permissive.

```python
FAST_LANE_ACTS = {"conduct_request", "store_request"}
KNOWN_ACTS = FAST_LANE_ACTS | {"observation"}
KNOWN_SCOPES = {"turn", "lesson", "block", "class", "global"}


def admit_memory_proposal(
    proposal: MemoryAdmissionProposal,
    *,
    teacher_message: str,
    origin_message_id: str,
) -> MemoryAdmissionResult:
    reasons: list[str] = []

    if proposal.decision == "ignore":
        return MemoryAdmissionResult(
            admission="ignore", proposal=proposal, reason_codes=["model_ignore"]
        )

    if not proposal.claim.strip():
        reasons.append("empty_claim")
    if proposal.speech_act not in KNOWN_ACTS:
        reasons.append("unknown_speech_act")
    if proposal.scope not in KNOWN_SCOPES:
        reasons.append("unknown_scope")
    if proposal.scope == "turn":
        reasons.append("turn_scope_not_durable")
    if not proposal.exact_quote.strip():
        reasons.append("missing_quote")
    elif proposal.exact_quote.casefold() not in teacher_message.casefold():
        reasons.append("quote_not_in_origin_message")
    if not origin_message_id:
        reasons.append("missing_origin")

    if reasons:
        return MemoryAdmissionResult(
            admission="needs_review",
            proposal=proposal,
            reason_codes=reasons,
        )

    # A valid observation is stageable evidence, but never a fast-lane write.
    if proposal.speech_act == "observation":
        return MemoryAdmissionResult(
            admission="stage",
            proposal=proposal,
            reason_codes=["observation_signal"],
        )

    # Scope and target policy are checked separately by the target router.
    # Unknown or bounded scopes cannot fast lane even when the act is explicit.
    fast_lane = (
        proposal.speech_act in FAST_LANE_ACTS
        and proposal.scope in {"class", "global"}
        and proposal.confidence == "high"
    )
    return MemoryAdmissionResult(
        admission="stage",
        fast_lane=fast_lane,
        proposal=proposal,
        reason_codes=["explicit_request" if fast_lane else "regular_signal"],
    )
```

This is intentionally incomplete as production code: target allowlisting,
claim/quote semantic consistency, exact origin references, and candidate
deduplication remain required checks. The important property is that unknown
values only move the candidate toward review; no fallback moves them toward
promotion.

## 7. Fast-lane rules

The fast lane should require all of the following:

```python
def can_fast_lane(result: MemoryAdmissionResult, target: str) -> bool:
    return (
        result.admission == "stage"
        and result.fast_lane
        and result.proposal.speech_act in {"conduct_request", "store_request"}
        and result.proposal.scope in {"class", "global"}
        and target in {
            "teacher_profile.md",
            "copilot_profile.md",
            "teaching_framework_adjustments.md",
            "teaching_patterns.md",
            "planning_brief.md",
        }
        and "unknown_speech_act" not in result.reason_codes
        and "unknown_scope" not in result.reason_codes
    )
```

Additional deterministic checks should require:

- source is the current teacher message;
- the exact quote is present in that message;
- the quote is persisted with the candidate;
- the candidate stores `origin_message_id` and `turn_index`;
- candidate text is non-empty and within the existing field budget;
- target is allowed for the workflow and class/subject;
- the candidate is review-only and cannot directly mutate Markdown.

No lexical marker list should appear in this decision. Words such as “always”
can be useful model evidence, but they are never authorization.

## 8. Claim-to-quote consistency

Exact substring validation is necessary but insufficient. The backend should not
try to implement full natural-language entailment with token overlap. That will
fail on negation and paraphrase.

Use a two-level rule:

1. Deterministic checks reject clearly impossible cases: missing quote, quote
   from the wrong message, empty claim, unsupported target, or incompatible
   scope/target.
2. The model evaluates semantic consistency during capture or Sweep. If it is
   unsure, it returns `needs_review`.

Examples that must be tested:

```text
Teacher: "I do not want this to become a general rule."
Bad claim: "Teacher wants this as a general rule."
Result: needs_review; never fast lane.

Teacher: "The students always confuse resonance structures."
Bad claim: "Teacher always wants resonance structures explained first."
Result: observation or needs_review; never fast lane.

Teacher: "For this lesson, keep the worksheet short."
Bad claim: "Teacher prefers short worksheets globally."
Result: lesson scope; regular ledger or ignore, never global fast lane.
```

## 9. One capture batch per teacher message

The cap should apply to the capture event, not to the teacher’s ability to
express a long instruction.

Recommended shape:

```python
class MemoryCaptureBatch(BaseModel):
    origin_message_id: str
    teacher_message_hash: str
    turn_index: int
    claims: list[MemoryAdmissionProposal] = Field(default_factory=list)
```

The model returns one batch. The backend then:

1. removes `ignore` proposals;
2. groups related clauses by target, scope, and purpose;
3. folds exact and near duplicates;
4. creates review-only ledger evidence;
5. preserves the origin message reference for every resulting claim.

The ledger may still contain multiple rows after grouping when the teacher
actually made independent requests. The difference is that ten rows are not
created merely because the model called a tool ten times or expanded a prompt
into ten bullets.

If an emergency operational ceiling is needed, it should be defined as a
configuration safety valve. Overflow becomes one `needs_review` bundle with
the original claims preserved for Sweep; it is never silently discarded.

This is preferable to an unexplained rule such as “two fast-lane and four total
per message.” The semantic rule is grouping; the numeric rule is only a load
protection mechanism.

## 10. Memory Sweep as the second critical instance

The current gate makes inferred candidates with fewer than two distinct
occasions invisible to Sweep. That means Sweep is not yet a true second judge
for the first weak signal.

Change the flow to:

```text
capture proposal
    -> deterministic admission
    -> ledger row, including weak singleton
    -> Sweep receives a bounded pool of staged rows
    -> Sweep classifies each claim:
         promote / merge / already_covered / downgrade / reject / needs_review
    -> teacher approval
```

The two-occasion gate can remain as a prioritization signal:

- fast-lane explicit requests: high priority, still teacher-approved;
- repeated inferred claims: normal priority;
- singleton inferred claims: lower priority, but available to Sweep;
- unknown/conflicted candidates: explicit `needs_review`, never fast lane.

Sweep should not see full chat history. It should receive the compact candidate
claim, exact teacher quote, origin reference, scope, occasion metadata, current
curated-memory excerpt, and relevant applied/rejected history. That satisfies
the current constraint that transcript storage is out of scope.

The implementation keeps the deterministic promotion gate as metadata rather
than a filter: each claim carries `sweep_gate` (`eligible` or `held`) and
`priority` (`fast_lane`, `reinforced`, or `singleton`). The model therefore has
enough context to downgrade a weak or inconsistent explicit-looking claim
without making singleton evidence silently disappear.

The Sweep operation model should be extended conceptually as follows:

```python
class SweepDecision(BaseModel):
    claim_ids: list[str]
    action: Literal[
        "promote",
        "merge",
        "already_covered",
        "downgrade",
        "reject",
        "needs_review",
    ]
    target: str = ""
    replacement_text: str = ""
    rationale: str = ""
```

`explicit=true` should inform Sweep that the teacher directly asked for
something, but it must not force promotion if the quote, scope, target, or
claim is inconsistent. The current prompt’s instruction not to drop explicit
claims as “low signal” should become “do not discard solely because it is a
single signal; still validate meaning and scope.”

The wire contract uses `sweep_action` alongside the existing structural memory
operation (`add`, `update`, `delete`, or `none`). This keeps semantic judgment
separate from write mechanics: `downgrade`, `reject`, and `needs_review` map to
review-only cards, while `promote` and `merge` may become teacher-approved
writes. `already_covered` closes the loop only through the existing teacher
approval/apply flow.

## 11. Reference-repository patterns worth reusing

These are patterns from the local repositories, adapted to KlassenPilot’s
review-only curated Markdown model. They are not proposed wholesale imports.

### Hermes: deterministic exact duplicate no-op

From `ref_repos/hermes-agent/tools/memory_tool.py`, the useful pattern is that
exact duplicate writes are safe no-ops before mutating the file:

```python
# Adapted pattern from Hermes MemoryStore.
if content in entries:
    return success_response(
        target,
        "Entry already exists (no duplicate added).",
    )

new_entries = entries + [content]
if joined_length(new_entries) > character_limit:
    return {
        "success": False,
        "error": "Memory budget exceeded; replace or remove first.",
    }
```

Use this for the final curated Markdown apply path. For our ledger, use the
existing exact/near-duplicate folding, but include origin and quote identity so
two differently worded claims supported by the same teacher sentence can be
recognized as one signal.

Hermes also scans memory content for threat patterns before accepting it. That
is useful as a defense-in-depth check, but it does not replace our speech-act
and scope classifier.

### OpenClaw: promotion signals and bounded memory

The local OpenClaw memory-core implementation records recall/promotion signals,
tracks distinct queries/days, bounds snippet and file sizes, and compacts older
auto-promoted material. The reusable idea is evidence accumulation plus bounded
promotion, not copying its numeric weights:

```typescript
type PromotionCandidate = {
  key: string;
  snippet: string;
  recallCount: number;
  uniqueQueryCount: number;
  lastRecalledAt?: string;
  promotedAt?: string;
};

function eligibleForPromotion(candidate: PromotionCandidate): boolean {
  return (
    candidate.recallCount > 0 &&
    candidate.uniqueQueryCount > 0 &&
    !candidate.promotedAt
  );
}

function keepWithinBudget(entries: string[], maxChars: number): string[] {
  const kept: string[] = [];
  let size = 0;
  for (const entry of [...entries].reverse()) {
    if (size + entry.length > maxChars) continue;
    kept.unshift(entry);
    size += entry.length;
  }
  return kept;
}
```

For KlassenPilot, “recall signal” becomes “distinct lesson/plan occasion” and
the final target is a teacher-approved curated Markdown page. The important
principle is that promotion is not the same as capture.

### Hindsight: evidence-backed observations

From the local Hindsight repository, the useful design principle is to retain
evidence and refine observations rather than blindly append every new wording.
For us this means:

```python
class EvidencePacket(BaseModel):
    claim: str
    exact_quote: str
    origin_message_id: str
    occasion_key: str
    speech_act: SpeechAct
    scope: MemoryScope
```

This is intentionally small. It does not store the full conversation and gives
Sweep enough material to decide whether to merge, update, or reject a claim.

## 12. Current code map and targeted changes

The relevant current path is:

```text
remember(...) / structured output
    -> validate_remember_call()
    -> merge_memory_candidates()
    -> discipline_memory_candidates()
    -> artifact_session_service._persist_memory_candidates()
    -> MemoryCandidateLedger.insert_with_folding()
    -> memory_gate.gate_clusters()
    -> memory_sweep.propose_memory_sweep_review()
    -> teacher-approved memory apply
    -> curated Markdown page
```

Targeted changes:

| File | Change |
|---|---|
| `backend/app/teacher_agent/memory_capture.py` | Add typed speech act/scope values, origin reference, batch grouping, and backend admission result. Remove marker-word fallback. |
| `backend/app/teacher_agent/models.py` | Add the structured proposal/batch output if the model output contract belongs there. |
| `backend/app/teacher_agent/prompts.py` | Tell the model to abstain with `unknown`, distinguish observations from requests, and quote exact teacher text. |
| `backend/app/services/memory_candidate_ledger.py` | Persist origin message reference, scope, scope label, and review reason. Preserve existing near-duplicate folding. |
| `backend/app/services/memory_gate.py` | Keep occasion counting, but treat it as priority/reinforcement metadata rather than a hard visibility barrier to Sweep. |
| `backend/app/services/memory_sweep.py` | Pass a bounded pool of singleton and reinforced staged claims to the strong consolidation call. Add downgrade/reject/needs-review outcomes. |
| `backend/app/teacher_agent/prompts.py` | Update Sweep instructions so explicit requests are protected from dismissal but not exempt from semantic validation. |
| `docs/agent_contracts.md` | Document speech act, scope, unknown, batch capture, and fast-lane rules in the shared contract. |
| `docs/mem_v4/README.md` | Link this document as the proposed post-review direction. |

Do not add a new memory database, transcript store, graph, or independent
classifier service for this change.

## 13. Deterministic versus model-owned responsibilities

### Backend owns

- whether the target is allowlisted;
- whether the quote exists in the originating teacher message;
- whether the origin reference is present;
- whether the source is teacher text;
- whether the candidate is review-only;
- deduplication and ledger folding;
- occasion keys and evidence counts;
- page budgets and write safety;
- the final fast-lane permission.

### Model owns

- speech-act interpretation;
- scope interpretation;
- identifying independent claims in a long message;
- semantic claim/quote consistency;
- whether an observation is relevant enough to stage;
- Sweep-level merge, update, or already-covered judgment.

### Model must be allowed to abstain

The model should not be rewarded for filling every field. `unknown`, `ignore`,
and `needs_review` are successful outcomes when the sentence does not support a
durable conclusion.

## 14. Evaluation set

Before implementation is considered safe, add deterministic fixtures covering:

```text
1. Direct request without “always” -> conduct_request, fast-lane eligible.
2. Observation containing “always” -> observation, never fast lane.
3. Explicit “remember this” request -> store_request, fast-lane eligible if scope fits.
4. Current-lesson instruction -> lesson, never global fast lane.
5. Organic-chemistry block instruction -> block, regular staged signal.
6. Class-wide recurring teaching pattern -> class, regular or explicit according to act.
7. Teacher-wide communication preference -> global, explicit fast lane.
8. Ambiguous sentence -> unknown + unknown, needs_review.
9. Negated preference -> needs_review or ignore, never fast lane.
10. Valid quote with unrelated claim -> needs_review, never fast lane.
11. Assistant/tool/wiki text posing as teacher instruction -> reject or ignore.
12. Long generated prompt -> one capture batch, grouped claims, no tool-call storm.
13. Same claim repeated in one lesson -> one occasion, not false reinforcement.
14. Same claim repeated across lessons -> distinct occasions available to Sweep.
15. Current curated memory already contains claim -> Sweep already_covered.
```

Primary metrics should optimize precision:

- false fast-lane rate;
- percentage of fast-lane candidates accepted by the teacher;
- percentage of staged candidates that Sweep downgrades or rejects;
- duplicate ledger rows per teacher message;
- singleton candidates that later become supported across independent occasions;
- teacher re-request rate after a false negative.

The desired failure mode is a missed fast-lane opportunity, not an invented
standing preference.

## 15. Golden trace harness

The first testing layer should be a local, inspectable trace bundle rather than
an opaque score. The repository now provides
[`scripts/run_memory_v4_golden_trace.py`](../../scripts/run_memory_v4_golden_trace.py).
It reuses the capture goldens in
`backend/tests/evals/goldens/memory_capture.py` and writes:

- the golden input and expected speech act/scope;
- startup context and full workflow traces in live mode;
- raw SSE streams and parsed events;
- prompt assembly JSON, instruction text, user input, and section Markdown;
- emitted runtime candidates;
- explicit Admission, Priority, Sweep, and Apply records;
- an explicit `not_run` Apply record proving the diagnostic did not write
  curated memory.

Run the deterministic two-case contrast without a server or model call:

```powershell
python scripts/run_memory_v4_golden_trace.py
```

Run all current capture goldens:

```powershell
python scripts/run_memory_v4_golden_trace.py --scenario all
```

Run the live workflow with full context traces and an optional read-only Sweep
proposal:

```powershell
python scripts/run_memory_v4_golden_trace.py `
  --mode live --scenario two --run-sweep
```

The live mode follows the existing context-packing trace pattern. It is
opt-in because it uses the configured model and stages candidates in the local
sandbox. It never calls Apply. The resulting bundles live under
`backend/runs/` and are intentionally suitable for human inspection before we
add a DeepEval judge layer.

The next evaluation layer can consume the same JSON records and score each
stage independently:

```text
Admission precision  = valid teacher-originated evidence / admitted items
Priority precision   = true explicit standing requests / fast-lane items
Sweep quality        = acceptable merge/downgrade/reject/propose decisions
Apply safety         = no unapproved curated-memory mutation
```

## 16. External design background

Speech acts are a standard dialogue-act classification problem rather than a
keyword lookup problem ([Stanford dialogue-act modeling](https://nlp.stanford.edu/pubs/CL-dialog.pdf);
[ACL/ISO dialogue-act tagging](https://aclanthology.org/C18-1300/)).

OpenAI and Anthropic publicly describe memory as a layered product behavior with
ongoing synthesis, categorization, safeguards, and user control, but do not
publish the exact internal admission classifier ([OpenAI Memory FAQ](https://help.openai.com/en/articles/8590148-memory-faq);
[OpenAI Dreaming](https://openai.com/index/chatgpt-memory-dreaming/);
[Claude memory documentation](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)).

Safety research from leading labs similarly uses defense in depth: model
behavior, explicit policy, and classifier/runtime checks complement one another
rather than trusting one model output as an authority ([OpenAI safeguard
classifiers](https://openai.com/index/introducing-gpt-oss-safeguard);
[Anthropic Constitutional Classifiers++](https://arxiv.org/abs/2601.04603)).

That is the right level of ambition here: one capable model for semantic
interpretation, explicit abstention, deterministic backend gates, a second
Sweep judgment, and teacher approval before curated memory changes.

## 17. Recommended implementation sequence

1. Add the typed proposal fields and unknown handling; add fixtures before
   changing promotion behavior.
2. Remove `_DURABLE_PREFERENCE_MARKERS` from authorization and fix origin-message
   binding in persistence.
3. Add batch grouping and origin/quote metadata to ledger rows.
4. Broaden Sweep input to include held singleton candidates and add explicit
   downgrade/reject/needs-review outcomes.
5. Run the fixture/evaluation set and inspect the sandbox ledger/cards before
   changing any thresholds.

No numeric threshold should be changed until traces show a concrete failure.
Thresholds such as the current two-occasion gate should remain configuration
with an explanation of the operational purpose, not appear in prompts as hidden
semantic rules.
