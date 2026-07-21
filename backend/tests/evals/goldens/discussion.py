"""Live Discuss goldens derived from beta trace review."""

from __future__ import annotations

from tests.evals.goldens.chat_plan import ChatGolden


DISCUSSION_GOLDENS: tuple[ChatGolden, ...] = (
    ChatGolden(
        golden_id="discussion_dota_detour_task_anchor",
        workflow="discussion",
        class_id="chemie_9b_2026_27",
        message="What are Legion Commander's skills in Dota 2?",
        geval_criteria=(
            "The response may answer the Dota detour briefly and naturally, but "
            "must not invent uncertain game mechanics. It must then explicitly "
            "return to the teacher's active organic-chemistry lesson task with a "
            "short, helpful next-step question or offer. Do not produce a lesson "
            "artifact or claim to have changed durable memory."
        ),
    ),
)


DISCUSSION_SCENARIO_PRIORS: dict[str, tuple[str, ...]] = {
    "discussion_dota_detour_task_anchor": (
        "I am planning the next Chemie 9b organic chemistry lesson and need to "
        "decide how to introduce alkane solubility after the water-and-oil demo.",
    ),
}
