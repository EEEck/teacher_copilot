"""Chat-turn golden definitions (message → tools → grounded response)."""

from __future__ import annotations

from dataclasses import dataclass

from tests.eval.fckw_prompts import CLASS_ID as CHEMIE_9B_CLASS_ID, PROMPT_TURN_1, PROMPT_TURN_2
from tests.eval.memory_update_prompts import MEMORY_UPDATE_PROMPTS

REDOX_LESSON_LOOKUP_PROMPT = (
    "Before I plan the next lesson: what did Chemie 9b cover in our "
    "2026-05-25 redox lesson? Browse the class wiki and cite the lesson you find."
)


@dataclass(frozen=True)
class ChatGolden:
    golden_id: str
    workflow: str
    class_id: str
    message: str
    turn: int = 1
    tools_required: tuple[str, ...] = ()
    tools_any_of: tuple[str, ...] = ()
    tools_any_of_min: int = 0
    require_raw_evidence: bool = False
    geval_criteria: str = ""
    artifact_patterns: tuple[str, ...] = ()
    forbidden_artifact_patterns: tuple[str, ...] = ()
    expected_phase: str = ""
    expected_ready: bool | None = None


PLAN_CHAT_GOLDENS: tuple[ChatGolden, ...] = (
    ChatGolden(
        golden_id="9b_plan_fckw_turn1",
        workflow="plan",
        class_id=CHEMIE_9B_CLASS_ID,
        message=PROMPT_TURN_1,
        turn=1,
        tools_required=("search_memory",),
        tools_any_of=("read_lesson", "read_lesson_range"),
        tools_any_of_min=1,
        require_raw_evidence=True,
        geval_criteria=(
            "The lesson plan draft must be grounded in Chemie 9b class memory and "
            "tool-retrieved wiki evidence. It should build on prior redox lessons "
            "(especially 2026-05-25), cover FCKW/CFC redox and environmental impact "
            "(Montreal Protocol), address oxidation number vs charge, and avoid inventing "
            "class facts that are not supported by the retrieval context."
        ),
        artifact_patterns=("2026-05-25", "FCKW", "45"),
    ),
    ChatGolden(
        golden_id="9b_plan_redox_lesson_lookup",
        workflow="plan",
        class_id=CHEMIE_9B_CLASS_ID,
        message=REDOX_LESSON_LOOKUP_PROMPT,
        turn=1,
        tools_required=(),
        tools_any_of=("read_lesson", "read_lesson_range", "search_memory"),
        tools_any_of_min=1,
        require_raw_evidence=True,
        artifact_patterns=("2026-05-25", "redox"),
    ),
    ChatGolden(
        golden_id="9b_plan_fckw_turn2_review",
        workflow="plan",
        class_id=CHEMIE_9B_CLASS_ID,
        message=PROMPT_TURN_2,
        turn=2,
        tools_any_of=("read_lesson_range", "read_lesson", "list_lessons", "search_memory"),
        tools_any_of_min=1,
        geval_criteria=(
            "The updated plan should add a review/recap of recent lessons grounded "
            "in retrieved class memory, especially confusion around ion charge vs "
            "oxidation number from recent lectures."
        ),
        artifact_patterns=(r"review|recap",),
    ),
)

INGEST_CHAT_GOLDENS: tuple[ChatGolden, ...] = (
    ChatGolden(
        golden_id="9b_ingest_turn2_collect",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        message=MEMORY_UPDATE_PROMPTS[1],
        turn=2,
        tools_any_of=("read_memory_target", "read_lesson", "search_memory"),
        tools_any_of_min=0,
        geval_criteria=(
            "The diary draft should reflect the teacher's 2026-05-29 lesson notes, "
            "use pseudonymous student IDs (S-###) not real names, and stay consistent "
            "with the class memory context."
        ),
        artifact_patterns=("2026-05-29", "anion"),
    ),
    ChatGolden(
        golden_id="9b_ingest_turn3_ready",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        message=MEMORY_UPDATE_PROMPTS[2],
        turn=3,
        tools_any_of=("read_memory_target", "list_memory_targets", "search_memory"),
        tools_any_of_min=1,
        require_raw_evidence=True,
        geval_criteria=(
            "The final diary draft should reflect the teacher's corrections for "
            "2026-05-29, including common anions, the unfinished redox-sequence link, "
            "the 2026-05-25 metal-displacement follow-up, lesson-organization cause "
            "of interruption, and pseudonymous student IDs only."
        ),
        artifact_patterns=("2026-05-29", "common anions", "metal displacement", r"S-\d{3}"),
        forbidden_artifact_patterns=(r"\bJoonho\b", r"\bAlex\b", r"\bRita\b", r"\bMatt\b", r"raw_ref"),
        expected_phase="review_draft",
        expected_ready=True,
    ),
)

CHAT_GOLDENS: tuple[ChatGolden, ...] = PLAN_CHAT_GOLDENS + INGEST_CHAT_GOLDENS

# Multi-turn scenarios: prior messages before the golden message.
CHAT_SCENARIO_PRIORS: dict[str, tuple[str, ...]] = {
    "9b_plan_fckw_turn2_review": (PROMPT_TURN_1,),
    "9b_ingest_turn2_collect": (MEMORY_UPDATE_PROMPTS[0],),
    "9b_ingest_turn3_ready": (MEMORY_UPDATE_PROMPTS[0], MEMORY_UPDATE_PROMPTS[1]),
}
