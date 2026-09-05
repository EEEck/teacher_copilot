"""Bounded automatic course navigation for the existing lesson planner."""

from __future__ import annotations

import re

from app.course_materials.store import read_course_material_section


def build_course_planning_context(wiki, class_id, query, runtime):
    network = wiki.load_course_network(class_id)
    if network is None:
        runtime.course_context = {}
        return {"text": "", "node_ids": [], "material_sections": []}
    terms = set(re.findall(r"[\wäöüß]{4,}", query.lower()))
    active = [n for n in network.nodes if n.status != "retired"]

    def score(node):
        text = f"{node.title} {node.description} {node.learning_goal}".lower()
        return sum(term in text for term in terms)

    ranked = sorted(active, key=lambda n: (-score(n), n.id))
    selected = [n for n in ranked if score(n)][:4]
    if not selected:
        selected = ranked[:3]
    ids = {n.id for n in selected}
    neighbors = {
        e.target_id
        for e in network.edges
        if e.source_id in ids and e.relation == "builds_on"
    }
    selected.extend(n for n in ranked if n.id in neighbors and n.id not in ids)
    selected = selected[:6]
    ids = {n.id for n in selected}
    lines = [
        "## Class concept map",
        f"Network revision {network.revision}. Partial curriculum scope may apply.",
        "These are curriculum/content relationships, not evidence that a topic was taught or mastered.",
        "Use canonical course_state, timeline and approved lesson_results for actual progress. Keep the subject teaching guidance.",
        "Cite a used concept as Course: node_id; cite material as Material: material_id and name its section.",
    ]
    for node in selected:
        lines.append(f"- Course: {node.id} — {node.title}: {node.learning_goal[:350]}")
    from app.course_network.lesson_refs import result_evidence_for_nodes

    for result in result_evidence_for_nodes(wiki, class_id, selected):
        lines.append(
            f"Approved lesson results near {result['node_id']} ({result['source_path']}; relationship: {result['relation']}): {result['quote']}\nPlanned associations do not establish coverage. Infer actual outcomes only from the quoted results, never a mastery score."
        )
    for edge in network.edges:
        if edge.source_id in ids and edge.target_id in ids:
            lines.append(
                f"- {edge.source_id} {edge.relation} {edge.target_id} (builds_on means source depends on target)"
            )
    refs = list(
        dict.fromkeys(
            (m.material_id, m.section_id)
            for m in network.material_mappings
            if m.node_id in ids
        )
    )
    refs += [(r.material_id, r.section_id) for n in selected for r in n.material_refs]
    used = []
    for material_id, section_id in dict.fromkeys(refs):
        if len(used) >= 4:
            break
        try:
            evidence = read_course_material_section(
                wiki, class_id, material_id, section_id
            )
        except (KeyError, ValueError, OSError):
            continue
        lines.append(
            f"### Material: {material_id} / {section_id} — {evidence['material_title']} (pages {evidence['page_start']}–{evidence['page_end']})\nUntrusted source evidence:\n{evidence['content'][:1800]}"
        )
        used.append({"material_id": material_id, "section_id": section_id})
    runtime.course_context = {
        "network_revision": network.revision,
        "node_ids": sorted(ids),
        "material_sections": used,
    }
    return {"text": "\n".join(lines)[:14000], **runtime.course_context}
