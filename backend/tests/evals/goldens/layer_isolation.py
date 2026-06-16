"""Layer-isolation golden definitions."""

from __future__ import annotations

from tests.evals.contracts.layer_contract import LayerExpectation, LayerScope

CHEMIE_9B_CLASS_ID = "chemie_9b_2026_27"
ENGL_10C_CLASS_ID = "engl_10c_2026_27"

LAYER_GOLDENS: tuple[LayerExpectation, ...] = (
    LayerExpectation(
        golden_id="9b_global",
        class_id=CHEMIE_9B_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_ONLY,
        required_markers=("Prefers concise 45-minute lesson plans",),
        forbidden_markers=("chemie_9b", "Confusing oxidation", "Distinguish ion charge"),
    ),
    LayerExpectation(
        golden_id="9b_global_class",
        class_id=CHEMIE_9B_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_PLUS_CLASS,
        subject_id="chemie",
        required_markers=("Chemie 9b", "Distinguish ion charge from oxidation number", "Peer checking"),
        forbidden_markers=("Confusing oxidation number with ionic charge",),
        required_memory_files=(
            "taught_so_far.md",
            "planning_brief.md",
            "teaching_patterns.md",
            "copilot_profile.md",
            "session_summaries.md",
        ),
    ),
    LayerExpectation(
        golden_id="9b_global_class_subject",
        class_id=CHEMIE_9B_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT,
        subject_id="chemie",
        required_markers=("Chemie 9b", "Distinguish ion charge from oxidation number", "Peer checking"),
        forbidden_markers=("ESL", "engl_10c", "mathe"),
        subject_required_markers=("Confusing oxidation number with ionic charge",),
        required_memory_files=(
            "taught_so_far.md",
            "planning_brief.md",
            "teaching_patterns.md",
            "copilot_profile.md",
            "session_summaries.md",
        ),
    ),
    LayerExpectation(
        golden_id="10c_global",
        class_id=ENGL_10C_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_ONLY,
        required_markers=("Prefers concise 45-minute lesson plans",),
        forbidden_markers=("engl_10c", "Focus on essay scaffolding", "chemie", "oxidation"),
    ),
    LayerExpectation(
        golden_id="10c_global_class",
        class_id=ENGL_10C_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_PLUS_CLASS,
        subject_id="ESL",
        required_markers=("Englisch 10c", "Focus on essay scaffolding for 10c", "pair feedback in ESL writing blocks"),
        forbidden_markers=("chemie", "oxidation", "Confusing oxidation number with ionic charge"),
        required_memory_files=("taught_so_far.md", "planning_brief.md", "copilot_profile.md"),
    ),
    LayerExpectation(
        golden_id="10c_global_class_subject",
        class_id=ENGL_10C_CLASS_ID,
        layer_scope=LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT,
        subject_id="ESL",
        required_markers=("Englisch 10c", "Focus on essay scaffolding for 10c"),
        forbidden_markers=("chemie", "Confusing oxidation", "chemie_9b"),
        subject_required_markers=("Confusing present perfect with simple past",),
        required_memory_files=("taught_so_far.md", "planning_brief.md", "copilot_profile.md"),
    ),
)
