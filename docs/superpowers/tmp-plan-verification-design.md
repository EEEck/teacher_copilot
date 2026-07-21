# Temporary Plan Verification Design

## Scope

Keep the existing shared `ExecutiveRuntime` for lifecycle, findings, severity,
trace state, and save semantics. Create only empty registry placeholders for
Discuss, Update Memory, and Class Brief. Implement the Plan verifier first.

## Plan verifier inputs

Use a bounded packet only:

- teacher request and final Markdown package;
- selected subject, grade, and branch;
- current unit, recent lessons, misconceptions, and relevant class memory;
- teacher preferences and teaching-framework adjustments;
- compact Chemie 9 NTG non-negotiables;
- trusted-source IDs and sections actually read.

Do not provide the full prompt, raw source bodies, or hidden reasoning.

## Two-layer review

1. Deterministic checks cover the canonical Markdown package, known route,
   source-read provenance, available teacher/class context, duration/safety
   mechanics, and source-body-dumping rules.
2. A bounded no-tools economy-model review assesses curriculum grounding and
   scope, class and teacher-preference fit, Chemie pedagogy, differentiation,
   practicality, and safety.

## Report card

Return one report with `overall_status: clear | advisory | safety_hold`, a
one-sentence teacher-facing summary, provenance, and rows for:

- curriculum grounding and scope;
- class context and recent-lesson fit;
- teacher preferences and framework adjustments;
- Chemistry pedagogy and best practices;
- differentiation and common evidence task;
- practicality, timing, and materials;
- safety; and
- Markdown package integrity.

Rows are `clear`, `note`, or `needs_teacher_decision`; this is not a numeric
grade. Show all relevant rows rather than hiding concerns behind an arbitrary
finding cap.

## Teacher control and revision

- Advisory scope, local-sequencing, preference, or missing-local-information
  findings never block saving. Example: organic chemistry may be an intentional
  local Grade 9 extension, so the teacher confirms or corrects the framing.
- Only a credible severe safety problem creates `safety_hold`. The plan remains
  visible and editable; the teacher can revise it or explicitly confirm local
  safety procedures.
- Objective, unambiguous defects may produce a proposed revised draft. It is a
  new draft version with a concise change summary, never a silent overwrite.
- Technical Markdown invalidity remains a normal structural saveability issue,
  not an executive judgement.

## Runtime timing

Return the generated plan immediately. Run the short no-tools verifier after
the plan as a durable background turn; run a short revision turn only when the
report identifies an objective repair. This avoids extending the existing
long-running planner request and preserves a responsive teacher review loop.
