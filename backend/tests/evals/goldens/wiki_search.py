"""Wiki-search component golden definitions."""

from __future__ import annotations

from dataclasses import dataclass

from tests.evals.goldens.layer_isolation import CHEMIE_9B_CLASS_ID, ENGL_10C_CLASS_ID


@dataclass(frozen=True)
class WikiSearchGolden:
    golden_id: str
    class_id: str
    query: str
    required_path_markers: tuple[str, ...] = ()
    required_text_markers: tuple[str, ...] = ()
    forbidden_path_markers: tuple[str, ...] = ()


WIKI_SEARCH_GOLDENS: tuple[WikiSearchGolden, ...] = (
    WikiSearchGolden(
        golden_id="9b_misconception_charge_vs_oxidation",
        class_id=CHEMIE_9B_CLASS_ID,
        query="ion charge oxidation number misconception",
        required_path_markers=("wiki/classes/chemie_9b_2026_27/",),
        required_text_markers=("oxidation", "charge"),
        forbidden_path_markers=("engl_10c_2026_27", "wiki/subjects/ESL.md"),
    ),
    WikiSearchGolden(
        golden_id="9b_redox_date_range_pathfinder",
        class_id=CHEMIE_9B_CLASS_ID,
        query="2026-05-25 redox metal displacement",
        required_path_markers=("wiki/classes/chemie_9b_2026_27/", "2026-05-25"),
        required_text_markers=("redox",),
        forbidden_path_markers=("engl_10c_2026_27",),
    ),
    WikiSearchGolden(
        golden_id="10c_subject_bound_search",
        class_id=ENGL_10C_CLASS_ID,
        query="essay scaffolding pair feedback",
        required_path_markers=("wiki/classes/engl_10c_2026_27/",),
        required_text_markers=("essay",),
        forbidden_path_markers=("chemie_9b_2026_27", "wiki/subjects/chemie.md"),
    ),
)
