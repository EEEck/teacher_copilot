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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def error_message(body: dict) -> str:
    error = body.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    detail = body.get("detail")
    return detail if isinstance(detail, str) else ""


def run(api_base: str, wiki_root: Path) -> dict:
    class_8a = "chemie_8a_2026_27"
    seeded_9b = "chemie_9b_2026_27"
    classes_root = wiki_root / "wiki" / "classes"
    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        require(
            expect_status(client.get("/api/health"), 200)["status"] == "ok",
            "health endpoint did not report status=ok",
        )
        initial = expect_status(client.get("/api/classes"), 200)["classes"]
        initial_ids = {item["id"] for item in initial}
        require(seeded_9b in initial_ids, f"missing seeded class {seeded_9b}")
        require(class_8a not in initial_ids, f"class {class_8a} already exists")

        routes = expect_status(client.get("/api/classes/curriculum-routes"), 200)[
            "routes"
        ]
        require(routes == SUPPORTED_ROUTES, "curriculum routes did not match")

        seeded_snapshot = expect_status(
            client.get(f"/api/classes/{seeded_9b}/snapshot"), 200
        )
        seeded_timeline = expect_status(
            client.get(f"/api/classes/{seeded_9b}/timeline"), 200
        )
        require(
            seeded_snapshot["last_committed_date"] == "2026-06-01"
            and seeded_snapshot["last_committed_at"] == "2026-06-01T04:39:00"
            and seeded_snapshot["last_committed_title"] == "Compact class memory",
            "seeded class lost its known last-commit metadata",
        )

        created = expect_status(client.post("/api/classes", json=CREATE_8A), 201)
        require(
            created
            == {
                "id": class_8a,
                "label": "Chemie 8a — 2026/27",
                "subject": "chemie",
            },
            "created class summary did not match",
        )

        fresh_snapshot = expect_status(
            client.get(f"/api/classes/{class_8a}/snapshot"), 200
        )
        fresh_timeline = expect_status(
            client.get(f"/api/classes/{class_8a}/timeline"), 200
        )
        require(
            fresh_snapshot["current_unit"] == "Not set",
            "new class has a current unit",
        )
        require(
            fresh_snapshot["last_committed_date"] is None,
            "new class has a committed lesson date",
        )
        require(
            fresh_snapshot["last_committed_at"] is None
            and fresh_snapshot["last_committed_title"] is None,
            "new class has committed lesson metadata",
        )
        require(
            fresh_snapshot["open_loop_count"] == 0,
            "new class has open loops",
        )
        require(
            fresh_snapshot["recent_lessons"] == [],
            "new class has recent lessons",
        )
        require(fresh_timeline["entries"] == [], "new class timeline has entries")
        require(fresh_timeline["months"] == [], "new class timeline has months")

        class_root = classes_root / class_8a
        required = {
            "class_config.md",
            "course_state.md",
            "curriculum_profile.md",
            "misconceptions.md",
            "open_loops.md",
            "students.md",
            "timeline.md",
            "trusted_sources.md",
            "memory/planning_brief.md",
            "memory/teaching_patterns.md",
            "memory/copilot_profile.md",
            "memory/session_summaries.md",
            "memory/teaching_framework_adjustments.md",
            "students/S-001.md",
            "students/S-002.md",
        }
        require(
            all((class_root / rel).is_file() for rel in required),
            "new class is missing required wiki files",
        )
        require(
            not (class_root / "course_network" / "network.json").exists(),
            "new class unexpectedly has a course network",
        )
        require(
            "Atombau und Periodensystem"
            in (class_root / "course_state.md").read_text(encoding="utf-8"),
            "new class course state did not retain prior learning",
        )

        before_duplicate = tree_digest(classes_root)
        duplicate = expect_status(client.post("/api/classes", json=CREATE_8A), 422)
        require(
            "already exists" in error_message(duplicate),
            "duplicate was not reported",
        )
        require(
            tree_digest(classes_root) == before_duplicate,
            "duplicate rejection mutated the class sandbox",
        )

        unsupported = CREATE_8A | {
            "label": "Chemie 8c — 2026/27",
            "section": "c",
            "branch": "SG",
        }
        before_unsupported = tree_digest(classes_root)
        rejected = expect_status(client.post("/api/classes", json=unsupported), 422)
        require(
            "NTG" in error_message(rejected),
            "unsupported branch was not reported",
        )
        require(
            not (classes_root / "chemie_8c_2026_27").exists(),
            "unsupported class directory was created",
        )
        require(
            tree_digest(classes_root) == before_unsupported,
            "unsupported rejection mutated the class sandbox",
        )

        require(
            expect_status(client.get(f"/api/classes/{seeded_9b}/snapshot"), 200)
            == seeded_snapshot,
            "seeded class snapshot changed",
        )
        require(
            expect_status(client.get(f"/api/classes/{seeded_9b}/timeline"), 200)
            == seeded_timeline,
            "seeded class timeline changed",
        )

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
