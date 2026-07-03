"""Student Summary judge golden definitions."""

from __future__ import annotations

from dataclasses import dataclass

from tests.evals.goldens.layer_isolation import CHEMIE_9B_CLASS_ID


@dataclass(frozen=True)
class StudentSummaryGolden:
    golden_id: str
    class_id: str
    student_id: str
    prompt: str
    student_page_markdown: str
    proposed_summary: str
    required_patterns: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    geval_criteria: str = ""


S045_STUDENT_PAGE = """# Jonas Becker

> Class: chemie_9b_2026_27

## Student Summary
- Jonas shows strong oral participation while building consistency in written chemistry notation and reasoning.

## 2026-04-24
- Quick orally, but rushed the written skeleton equation.

## 2026-05-14
- Good oral answers on oxidation rules, weaker on notation.

## 2026-05-25
- Needed one reminder to write the reasoning out clearly.

## 2026-06-01
- Starting to improve notation and performance in written tests, while beginning to disrupt class at times.

## 2026-06-08
- Disrupted class again last week and mentioned problems at home.
"""


STUDENT_SUMMARY_GOLDENS: tuple[StudentSummaryGolden, ...] = (
    StudentSummaryGolden(
        golden_id="s045_balanced_learning_and_support_trajectory",
        class_id=CHEMIE_9B_CLASS_ID,
        student_id="S-045",
        prompt=(
            "Revise S-045's durable Student Summary from the current summary and dated "
            "observations. Keep it to one neutral sentence."
        ),
        student_page_markdown=S045_STUDENT_PAGE,
        proposed_summary=(
            "Jonas is improving in written notation and test performance, while recent "
            "disruptions suggest he benefits from clear routines and a discreet support check-in."
        ),
        required_patterns=(
            r"\bimprov(?:e|ing|ed|ement)\b",
            r"\b(?:written|test|notation)\b",
            r"\b(?:disruptions?|routine|support|check-in)\b",
        ),
        forbidden_patterns=(
            r"\bdifficult to handle\b",
            r"\bproblems at home\b",
            r"\bdiagnos(?:e|ed|is|tic)\b",
            r"\bdisciplin(?:e|ary|ed)\b",
            r"\bplacement\b",
            r"\bgrade(?:d|s)?\b",
            r"\blazy\b",
            r"\btroublemaker\b",
            r"\bdefiant\b",
        ),
        geval_criteria=(
            "Judge whether the proposed Student Summary is a single neutral, evidence-grounded "
            "sentence for durable teacher memory. It should preserve the longer trajectory that "
            "Jonas was orally strong and is now improving written notation/test performance, "
            "while also reflecting repeated recent disruption as a support/routine need. It "
            "should not overreact to one or two observations, expose sensitive home-context "
            "details, use fixed-trait labels such as 'difficult to handle', or make diagnosis, "
            "grading, placement, discipline, or high-stakes claims."
        ),
    ),
)
