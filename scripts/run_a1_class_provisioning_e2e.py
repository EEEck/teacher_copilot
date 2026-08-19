from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx


SUPPORTED_ROUTES = [
    {"subject": "chemie", "grade": 8, "branch": "NTG"},
    {"subject": "chemie", "grade": 9, "branch": "NTG"},
]

CREATE_8A = {
    "label": "Chemie 8a — 2026/27",
    "subject": "chemie",
    "grade": 8,
    "section": "a",
    "school_year": "2026_27",
    "branch": "NTG",
    "school_type": "Gymnasium",
    "state": "BY",
    "prior_learning": "Atombau und Periodensystem wurden bereits wiederholt.",
    "student_names": ["Ada Beispiel", "Ben Beispiel"],
}


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def expect_status(response: httpx.Response, status: int) -> dict:
    if response.status_code != status:
        raise AssertionError(
            f"{response.request.method} {response.request.url} returned "
            f"{response.status_code}, expected {status}: {response.text[:1000]}"
        )
    return response.json()


def run(api_base: str, wiki_root: Path) -> dict:
    class_8a = "chemie_8a_2026_27"
    seeded_9b = "chemie_9b_2026_27"
    classes_root = wiki_root / "wiki" / "classes"
    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        assert expect_status(client.get("/api/health"), 200)["status"] == "ok"
        initial = expect_status(client.get("/api/classes"), 200)["classes"]
        initial_ids = {item["id"] for item in initial}
        assert seeded_9b in initial_ids
        assert class_8a not in initial_ids

        routes = expect_status(
            client.get("/api/classes/curriculum-routes"), 200
        )["routes"]
        assert routes == SUPPORTED_ROUTES

        seeded_snapshot = expect_status(
            client.get(f"/api/classes/{seeded_9b}/snapshot"), 200
        )
        seeded_timeline = expect_status(
            client.get(f"/api/classes/{seeded_9b}/timeline"), 200
        )

        created = expect_status(client.post("/api/classes", json=CREATE_8A), 201)
        assert created == {
            "id": class_8a,
            "label": "Chemie 8a — 2026/27",
            "subject": "chemie",
        }

        fresh_snapshot = expect_status(
            client.get(f"/api/classes/{class_8a}/snapshot"), 200
        )
        fresh_timeline = expect_status(
            client.get(f"/api/classes/{class_8a}/timeline"), 200
        )
        assert fresh_snapshot["current_unit"] == "Not set"
        assert fresh_snapshot["last_committed_date"] is None
        assert fresh_snapshot["open_loop_count"] == 0
        assert fresh_snapshot["recent_lessons"] == []
        assert fresh_timeline["entries"] == []
        assert fresh_timeline["months"] == []

        class_root = classes_root / class_8a
        required = {
            "class_config.md", "course_state.md", "curriculum_profile.md",
            "misconceptions.md", "open_loops.md", "students.md",
            "timeline.md", "trusted_sources.md",
            "memory/planning_brief.md", "memory/teaching_patterns.md",
            "memory/copilot_profile.md", "memory/session_summaries.md",
            "memory/teaching_framework_adjustments.md",
            "students/S-001.md", "students/S-002.md",
        }
        assert all((class_root / rel).is_file() for rel in required)
        assert not (class_root / "course_network" / "network.json").exists()
        assert "Atombau und Periodensystem" in (
            class_root / "course_state.md"
        ).read_text(encoding="utf-8")

        before_duplicate = tree_digest(class_root)
        duplicate = expect_status(client.post("/api/classes", json=CREATE_8A), 422)
        assert "already exists" in duplicate["detail"]
        assert tree_digest(class_root) == before_duplicate

        unsupported = CREATE_8A | {
            "label": "Chemie 8c — 2026/27",
            "section": "c",
            "branch": "SG",
        }
        rejected = expect_status(client.post("/api/classes", json=unsupported), 422)
        assert "NTG" in rejected["detail"]
        assert not (classes_root / "chemie_8c_2026_27").exists()

        assert expect_status(
            client.get(f"/api/classes/{seeded_9b}/snapshot"), 200
        ) == seeded_snapshot
        assert expect_status(
            client.get(f"/api/classes/{seeded_9b}/timeline"), 200
        ) == seeded_timeline

        for suffix in ("brief", "memory/sweep/review"):
            expect_status(client.get(f"/api/classes/{class_8a}/{suffix}"), 200)

    return {
        "status": "passed",
        "created_class": class_8a,
        "preserved_class": seeded_9b,
        "routes": SUPPORTED_ROUTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the live A1 class-provisioning API acceptance scenario."
    )
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--wiki-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--allow-external-wiki-root", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    wiki_root = args.wiki_root.resolve()
    if not args.allow_external_wiki_root and not wiki_root.is_relative_to(repo_root):
        raise ValueError(
            "--wiki-root must be inside the repository; pass "
            "--allow-external-wiki-root to override"
        )

    result = run(args.api_base, wiki_root)
    report = json.dumps(result, indent=2, ensure_ascii=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(f"{report}\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
