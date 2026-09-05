"""Plan provenance and read-only links to approved lesson-result evidence."""

import hashlib
import json
import re
import uuid


def build_plan_course_refs(wiki, class_id, plan):
    network = wiki.load_course_network(class_id)
    if network is None:
        return None
    cited = set(re.findall(r"Course:\s*`?([\w-]+)", plan))
    # The planner also names canonical map IDs as bold/code tokens in its
    # materials list. Preserve those explicit IDs without inferring from titles.
    cited.update(
        match.group("id")
        for match in re.finditer(r"(?P<marker>\*\*|`)(?P<id>[\w-]+)(?P=marker)", plan)
    )
    ids = sorted(n.id for n in network.nodes if n.id in cited and n.status != "retired")
    from app.course_materials.store import list_course_materials

    cited_materials = set(re.findall(r"Material:\s*`?([\w-]+)", plan))
    approved = {
        m.material_id: {section.id for section in m.sections}
        for m in list_course_materials(wiki, class_id)
        if m.material_id in cited_materials
    }
    materials = sorted(approved)
    active_ids = {n.id for n in network.nodes if n.status != "retired"}
    # This is material-use provenance, not a direct concept citation. Pin the
    # associations now so later map edits cannot change the saved plan's links.
    material_node_refs = [
        {"node_id": node_id, "material_id": material_id, "section_id": section_id}
        for node_id, material_id, section_id in sorted({
            (mapping.node_id, mapping.material_id, mapping.section_id)
            for mapping in network.material_mappings
            if mapping.node_id in active_ids
            and mapping.section_id in approved.get(mapping.material_id, set())
        })
    ]
    return {
        "schema_version": 1,
        "class_id": class_id,
        "network_revision": network.revision,
        "node_ids": ids,
        "material_ids": materials,
        "material_node_refs": material_node_refs,
        "kind": "planned",
        "plan_hash": hashlib.sha256(plan.encode()).hexdigest(),
    }


def write_plan_course_refs(wiki, class_id, lesson_date, plan, refs):
    if refs is None:
        return
    target = wiki.lesson_dir(class_id, lesson_date) / "course_refs.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    value = refs | {
        "plan_hash": hashlib.sha256(plan.encode()).hexdigest(),
        "lesson_date": lesson_date,
    }
    temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(target)


def read_plan_course_refs(wiki, class_id, lesson_date):
    root = wiki.lesson_dir(class_id, lesson_date)
    try:
        refs = json.loads((root / "course_refs.json").read_text(encoding="utf-8"))
        if not isinstance(refs, dict) or not isinstance(refs.get("node_ids"), list):
            return None
        actual = (root / "lesson_plan.md").read_text(encoding="utf-8")
        if (
            refs.get("class_id") != class_id
            or refs.get("plan_hash") != hashlib.sha256(actual.encode()).hexdigest()
        ):
            return None
        return refs
    except (OSError, ValueError):
        return None


def result_evidence_for_nodes(
    wiki, class_id, nodes, *, lesson_limit=20, evidence_limit=6
):
    """Only actual approved result text can support a result link; plans never do."""
    evidence = []
    lessons = wiki.class_dir(class_id) / "lessons"
    for path in sorted(lessons.glob("*/lesson_results.md"), reverse=True)[
        :lesson_limit
    ]:
        text = path.read_text(encoding="utf-8")
        planned = read_plan_course_refs(wiki, class_id, path.parent.name) or {}
        for node in nodes:
            paragraphs = [
                p.strip()
                for p in text.split("\n\n")
                if re.search(r"(?<!\w)" + re.escape(node.title) + r"(?!\w)", p, re.I)
                or node.id in re.findall(r"Course:\s*`?([\w-]+)", p)
            ]
            if paragraphs:
                evidence.append(
                    {
                        "node_id": node.id,
                        "lesson_date": path.parent.name,
                        "source_path": wiki.rel_wiki(path),
                        "quote": paragraphs[0][:700],
                        "relation": "explicit_result_mention",
                    }
                )
            elif node.id in planned.get("node_ids", []):
                evidence.append(
                    {
                        "node_id": node.id,
                        "lesson_date": path.parent.name,
                        "source_path": wiki.rel_wiki(path),
                        "quote": text[:1000],
                        "relation": "results_of_lesson_planned_around_concept",
                    }
                )
        if len(evidence) >= evidence_limit:
            break
    return evidence[:evidence_limit]


def lesson_associations_for_node(wiki, class_id, node):
    """Read existing provenance and approved results, without inferring coverage."""
    wiki.get_class(class_id)
    associations = []
    lessons = wiki.class_dir(class_id) / "lessons"
    for path in sorted(lessons.glob("*/course_refs.json"), reverse=True):
        refs = read_plan_course_refs(wiki, class_id, path.parent.name)
        direct = refs and node.id in refs.get("node_ids", [])
        linked_material = refs and any(
            isinstance(ref, dict) and ref.get("node_id") == node.id
            for ref in refs.get("material_node_refs", [])
        )
        if direct or linked_material:
            associations.append(
                {
                    "kind": "planned",
                    "lesson_date": path.parent.name,
                    "source_path": wiki.rel_wiki(path.parent / "lesson_plan.md"),
                    "relation": "explicit_plan_reference" if direct else "uses_linked_material",
                    "quote": "",
                }
            )
            if len(associations) >= 20:
                break
    associations.extend(
        {
            "kind": "approved_results",
            **{key: value for key, value in result.items() if key != "node_id"},
        }
        for result in result_evidence_for_nodes(
            wiki, class_id, [node], lesson_limit=None, evidence_limit=20
        )
    )
    return sorted(
        associations, key=lambda item: (item["lesson_date"], item["kind"]), reverse=True
    )
