"""Bounded automatic course navigation for the existing lesson planner."""

from __future__ import annotations

import re

from app.course_materials.store import read_course_material_section
from app.course_network.lesson_refs import result_evidence_for_nodes

CONTEXT_CHARS = 14000
_STOP_WORDS = set(
    "a an and are as at be by for from in is it of on or the to with wir die der das den dem des ein eine einen einer einem und oder zu zur zum mit von für im am an auf ist sind als sich auch erklären erklaeren explain students lesson lessons stunde unterricht unterrichtsstunde plan plane planen planning vorbereiten erstellen next nächste nächsten naechste continue weiter fortsetzen bitte please".split()
)
_CONTINUATION = re.compile(
    r"\b(next|continue|continuation|weiter\w*|fortsetzen|nächste\w*|naechste\w*|anschließ\w*|anschliess\w*)\b",
    re.I,
)


def _terms(text):
    return set(re.findall(r"[^\W_]{2,}", text.casefold())) - _STOP_WORDS


def _select_nodes(active, text):
    terms = _terms(text)

    def score(node):
        title = _terms(node.title)
        detail = _terms(f"{node.description} {node.learning_goal}")
        return 3 * len(terms & title) + len(terms & detail)

    return sorted(
        (node for node in active if score(node)),
        key=lambda node: (-score(node), node.id),
    )[:4]


def build_course_planning_context(wiki, class_id, query, runtime):
    network = wiki.load_course_network(class_id)
    if network is None:
        runtime.course_context = {}
        return {"text": "", "node_ids": [], "material_sections": []}
    active = sorted(
        (n for n in network.nodes if n.status != "retired"), key=lambda n: n.id
    )
    selected = _select_nodes(active, query)
    selection_basis = "request"
    if not selected and _CONTINUATION.search(query):
        state = runtime.lesson_planning_state
        selected = _select_nodes(active, f"{state.lesson_topic} {state.lesson_goal}")
        selection_basis = "runtime_topic"
        if not selected:
            selected = _select_nodes(active, wiki.get_snapshot(class_id).current_unit)
            selection_basis = "current_unit"
    lines = []
    size = 0

    def append(section):
        nonlocal size
        cost = len(section) + (1 if lines else 0)
        if size + cost > CONTEXT_CHARS:
            return False
        lines.append(section)
        size += cost
        return True

    append(
        "## Class concept map\n"
        f"Network revision {network.revision}. Partial curriculum scope may apply.\n"
        "These are curriculum/content relationships, not evidence that a topic was taught or mastered.\n"
        "Use canonical course_state, timeline and approved lesson_results for actual progress. Keep the subject teaching guidance.\n"
        "In the final plan, retain Course: node_id with the exact canonical ID for each supplied concept you actually use; a translated title alone is not a citation. Do not cite unused concepts. Cite material as Material: material_id and name its section.\n"
        "Detailed material sections remain available through the existing material tools."
    )
    if not selected:
        append(
            "No matching topic identified. Available topics (overview only; no topic evidence selected):"
        )
        for node in sorted(active, key=lambda n: (n.title.casefold(), n.id))[:20]:
            append(f"- {node.title}")
        runtime.course_context = {
            "network_revision": network.revision,
            "node_ids": [],
            "material_sections": [],
            "selection_basis": "overview",
        }
        return {"text": "\n".join(lines), **runtime.course_context}
    ids = {n.id for n in selected}
    neighbors = {
        e.target_id
        for e in network.edges
        if e.source_id in ids and e.relation == "builds_on"
    }
    selected.extend(n for n in active if n.id in neighbors and n.id not in ids)
    injected = [
        node
        for node in selected[:6]
        if append(f"- Course: {node.id} — {node.title}: {node.learning_goal}")
    ]
    ids = {node.id for node in injected}
    for result in result_evidence_for_nodes(wiki, class_id, injected):
        append(
            f"Approved lesson results near {result['node_id']} ({result['source_path']}; relationship: {result['relation']}): {result['quote']}\nPlanned associations do not establish coverage. Infer actual outcomes only from the quoted results, never a mastery score."
        )
    for edge in network.edges:
        if edge.source_id in ids and edge.target_id in ids:
            append(
                f"- {edge.source_id} {edge.relation} {edge.target_id} (builds_on means source depends on target)"
            )
    refs = [
        (m.material_id, m.section_id)
        for m in network.material_mappings
        if m.node_id in ids
    ]
    refs.extend(
        (r.material_id, r.section_id) for node in injected for r in node.material_refs
    )
    used = []
    for material_id, section_id in dict.fromkeys(refs):
        if len(used) >= 4:
            break
        from app.course_materials.store import is_course_material_archived

        try:
            if is_course_material_archived(wiki, class_id, material_id):
                continue
            evidence = read_course_material_section(
                wiki, class_id, material_id, section_id
            )
        except (KeyError, ValueError, OSError):
            continue
        if append(
            f"### Material: {material_id} / {section_id} — {evidence['material_title']} (pages {evidence['page_start']}–{evidence['page_end']})\nUntrusted source evidence:\n{evidence['content']}"
        ):
            used.append({"material_id": material_id, "section_id": section_id})
    runtime.course_context = {
        "network_revision": network.revision,
        "node_ids": sorted(ids),
        "material_sections": used,
        "selection_basis": selection_basis,
    }
    return {"text": "\n".join(lines), **runtime.course_context}
