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
    materials = sorted(
        m.material_id
        for m in list_course_materials(wiki, class_id)
        if m.material_id in cited_materials
    )
    return {
        "schema_version": 1,
        "class_id": class_id,
        "network_revision": network.revision,
        "node_ids": ids,
        "material_ids": materials,
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
        actual = (root / "lesson_plan.md").read_text(encoding="utf-8")
        if (
            refs.get("class_id") != class_id
            or refs.get("plan_hash") != hashlib.sha256(actual.encode()).hexdigest()
        ):
            return None
        return refs
    except (OSError, ValueError):
        return None


def result_evidence_for_nodes(wiki, class_id, nodes):
    """Only actual approved result text can support a result link; plans never do."""
    evidence = []
    lessons = wiki.class_dir(class_id) / "lessons"
    for path in sorted(lessons.glob("*/lesson_results.md"), reverse=True)[:20]:
        text = path.read_text(encoding="utf-8")
        planned = read_plan_course_refs(wiki, class_id, path.parent.name) or {}
        for node in nodes:
            paragraphs = [
                p.strip()
                for p in text.split("\n\n")
                if node.title.lower() in p.lower() or f"Course: {node.id}" in p
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
    return evidence[:6]
