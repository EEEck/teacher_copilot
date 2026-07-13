"""Executive-verification goldens for messy teacher input.

These goldens target the Checkpoint B product contract:
foreground artifact work should proceed where useful, while the executive
sidecar blocks readiness only when durable class-state decisions are unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CHEMIE_9B_CLASS_ID = "chemie_9b_2026_27"

DecisionExpectation = Literal[
    "proceed",
    "proceed_with_note",
    "block_ready",
    "not_ready_clear",
]
Workflow = Literal["ingest", "plan"]


ORGANIC_LESSON_WITH_DATE_AND_STUDENT_MISMATCH = """Class: chemie_9b_2026_27
Date taught: 2026-09-28
Workflow: Update memory from lesson result

We completed the first organic chemistry lesson today.

What happened:
The 15-minute redox recap took closer to 18 minutes, but it was useful. Students remembered that oxidation is electron loss and reduction is electron gain, but several still mixed up oxidation numbers with actual charges. The bridge to organic chemistry worked best when I said: “In redox, we tracked electron transfer; in organic chemistry, we mostly track how atoms share electrons in bonds.”

Carbon bonding:
Students understood quickly that carbon often forms four bonds when I drew methane and ethane. The abstract hybridization language was too much at first. They responded much better to molecule kits and a quick tetrahedron sketch than to the word “sp3”. Ethene and ethyne were useful as contrast examples, but I should keep double/triple bonds visual for now and not overload them with orbital theory.

Teaching-style observation:
Organic chemistry needs a different teaching style than redox. Redox worked with algorithmic steps and oxidation-number drills. Organic chemistry seems to need more visual/spatial work, physical models, sketching, comparison of representations, and less symbolic calculation at the beginning.

Possible teacher preference update:
For organic chemistry lessons, I prefer starting with concrete molecule examples, board sketches, and model kits before introducing terminology. I want the copilot to avoid overly abstract orbital explanations unless I explicitly ask for depth.

Class behavior:
The class was more curious than during the last redox lessons. They asked more “why does it look like that?” questions. However, some students got restless during the redox recap because they felt it was old material.

Student notes:
- S-014 asked strong questions about why carbon has four bonds, but became confused when hybridization was introduced verbally. Use visual models with this student.
- S-006 tried to answer every redox recap question and dominated the room. Use think-pair-share before cold calling.
- S-021 was quiet but wrote an excellent exit-ticket explanation of electron sharing versus electron transfer.
- S-033 still struggles with valence electrons and needs a scaffold before structural formulas.

Memory update suggestions:
Update class_state.md with the transition from redox to organic chemistry.
Add an open loop: revisit oxidation numbers only briefly when needed, but do not let redox review consume the organic chemistry unit.
Add a teaching pattern: for organic chemistry, use visual/spatial representations earlier than formal terminology.
"""


ORGANIC_LESSON_VALID_MESSY_INPUT = (
    ORGANIC_LESSON_WITH_DATE_AND_STUDENT_MISMATCH
    .replace("Date taught: 2026-09-28", "Date taught: 2026-07-09")
    .replace("S-006 tried to answer", "S-046 tried to answer")
)


ORGANIC_LESSON_UNKNOWN_STUDENT_INPUT = ORGANIC_LESSON_VALID_MESSY_INPUT.replace(
    "S-046 tried to answer", "S-006 tried to answer"
)


HARTREE_FOCK_HISTORY_QUESTION = (
    "Did we not cover Hartree-Fock equations in class? Sorry, I am a bit "
    "disorganized with my teaching."
)


WRONG_SUBJECT_MEMORY_INPUT = """Class: Englisch 10c
Date taught: 2026-07-09
Workflow: Update memory from lesson result

We completed a Macbeth essay-feedback lesson today. Students revised thesis
statements, compared quote integration, and discussed how Lady Macbeth's guilt
develops across Act 5. Please save this as the lesson result and add that E-012
needs sentence-level support before the next essay.
"""


@dataclass(frozen=True)
class ExecutiveVerificationGolden:
    golden_id: str
    workflow: Workflow
    class_id: str
    start_body: dict
    messages: tuple[str, ...]
    expected_decisions: tuple[DecisionExpectation, ...]
    required_reply_signals: tuple[tuple[str, ...], ...] = ()
    forbidden_reply_signals: tuple[str, ...] = ()
    required_artifact_patterns: tuple[str, ...] = ()
    forbidden_artifact_patterns: tuple[str, ...] = ()
    required_memory_candidate_targets: tuple[str, ...] = ()
    judge_context: str = ""
    judge_artifact: bool = True
    rationale: str = ""


EXECUTIVE_VERIFICATION_GOLDENS: tuple[ExecutiveVerificationGolden, ...] = (
    ExecutiveVerificationGolden(
        golden_id="memory_date_and_student_mismatch_blocks_then_resolves",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        start_body={
            "lesson_date": "2026-07-09",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "lesson_title": "Organic Chemistry Unit Opener: Carbon Bonding",
        },
        messages=(
            ORGANIC_LESSON_WITH_DATE_AND_STUDENT_MISMATCH,
            "ok great catches you are right, S006 is the wrong student id, date is wrong you have the right one, correct student is 46",
        ),
        expected_decisions=("block_ready", "proceed"),
        required_reply_signals=(
            ("2026-07-09", "2026-09-28", "S-006"),
            ("2026-07-09", "S-046"),
        ),
        forbidden_reply_signals=("I saved this", "saved to memory"),
        required_artifact_patterns=("2026-07-09", "S-046", "Organic Chemistry"),
        forbidden_artifact_patterns=("S-006", "2026-09-28"),
        required_memory_candidate_targets=(
            "copilot_profile.md",
            "teaching_patterns.md",
            "planning_brief.md",
        ),
        rationale=(
            "The agent should draft useful lesson results, block readiness on "
            "the date/student mismatch, then resolve after teacher confirmation."
        ),
    ),
    ExecutiveVerificationGolden(
        golden_id="memory_wrong_subject_context_blocks_artifact",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        start_body={
            "lesson_date": "2026-07-09",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "lesson_title": "Organic Chemistry Unit Opener: Carbon Bonding",
        },
        messages=(WRONG_SUBJECT_MEMORY_INPUT,),
        expected_decisions=("block_ready",),
        required_reply_signals=(("10c", "Chemie 9b"),),
        forbidden_reply_signals=("I saved this", "saved to memory"),
        forbidden_artifact_patterns=("Macbeth", "Lady Macbeth", "E-012"),
        rationale=(
            "A completely different class/subject paste must not become a "
            "save-ready Chemie 9b memory artifact."
        ),
    ),
    ExecutiveVerificationGolden(
        golden_id="memory_valid_messy_input_proceeds",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        start_body={
            "lesson_date": "2026-07-09",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "lesson_title": "Organic Chemistry Unit Opener: Carbon Bonding",
        },
        messages=(
            ORGANIC_LESSON_VALID_MESSY_INPUT,
            "The draft looks right. I am ready to save memory.",
        ),
        expected_decisions=("not_ready_clear", "proceed"),
        forbidden_reply_signals=("not in the roster", "does not resolve", "2026-09-28"),
        required_artifact_patterns=("2026-07-09", "S-046", "Organic Chemistry"),
        forbidden_artifact_patterns=("S-006", "2026-09-28"),
        required_memory_candidate_targets=(
            "copilot_profile.md",
            "teaching_patterns.md",
            "planning_brief.md",
        ),
        rationale=(
            "Valid messy input should proceed without unnecessary clarification."
        ),
    ),
    ExecutiveVerificationGolden(
        golden_id="memory_unknown_student_stays_in_active_class",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        start_body={
            "lesson_date": "2026-07-09",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "lesson_title": "Organic Chemistry Unit Opener: Carbon Bonding",
        },
        messages=(ORGANIC_LESSON_UNKNOWN_STUDENT_INPUT,),
        expected_decisions=("block_ready",),
        required_reply_signals=(("S-006",),),
        forbidden_reply_signals=("9a", "other class", "different class", "switch"),
        required_artifact_patterns=("2026-07-09", "Organic Chemistry"),
        forbidden_artifact_patterns=("S-006",),
        rationale=(
            "An unknown student must block durable readiness and be omitted from "
            "the Chemie 9b diary. The assistant may request an active-class "
            "correction but must not present another class as an option."
        ),
    ),
    ExecutiveVerificationGolden(
        golden_id="memory_unsupported_history_stays_in_active_class",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        start_body={
            "lesson_date": "2026-07-09",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "lesson_title": "Organic Chemistry Unit Opener: Carbon Bonding",
        },
        messages=(HARTREE_FOCK_HISTORY_QUESTION,),
        expected_decisions=("not_ready_clear",),
        required_reply_signals=(("Hartree-Fock",),),
        forbidden_reply_signals=("9a", "other class", "different class", "switch"),
        forbidden_artifact_patterns=("Hartree-Fock", "UHF"),
        judge_context=(
            "The committed Chemie 9b record includes a planned 2026-07-09 "
            "Organic Chemistry Unit Opener: Carbon Bonding. It contains no "
            "Hartree-Fock/UHF coverage. The session's empty diary template is "
            "a workflow shell, not an artifact update."
        ),
        judge_artifact=False,
        rationale=(
            "A teacher question about prior coverage must be answered from the "
            "Chemie 9b record. It is not a lesson update, must not enter the "
            "diary, and must not be redirected to another class. The initial "
            "empty diary template is a workflow shell, not a teacher-content "
            "update."
        ),
    ),
)
