"""API E2E: seed bonding material + exact browser MO prompts; assert asset embeds.

Uses the live local API (default http://localhost:8011). Seeds
``mini_bonding_package`` through PlanService against the same draft store the
server uses only when ``--seed-via-service`` is set **and** the backend was
restarted afterward (in-memory sessions). Prefer ``--seed-via-service`` with a
fresh backend, or upload a PDF with ``--pdf``.

Prompts: see ``scripts/plan_materials_mo_e2e_prompts.md``.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import pathlib
import re
import sys
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FIXTURE = BACKEND / "tests" / "fixtures" / "materials" / "mini_bonding_package"

PROMPT_1 = (
    "can you summarize the texbook content i have uploaded to help me decide "
    "how to plan the lesson? i want to focus on the core idea of bonding like "
    "molecualr disscoo curve etc, can you also port images from the textbook "
    "into the md file"
)
PROMPT_2 = (
    "lets focus on mo theory and also the dissociton curve lets use the images "
    "from the textbook, we have the rights to use for the classroom"
)

CLASS_ID = "chemie_9b_2026_27"
ASSET_RE = re.compile(r"assets/img-[^\s)]+", re.I)


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 600,
) -> Any:
    headers: dict[str, str] = {}
    data = raw
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                return json.loads(body.decode("utf-8"))
            return body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> {exc.code}: {detail}") from exc


def _parse_sse_final(text: str) -> dict[str, Any]:
    final: dict[str, Any] = {}
    for block in text.split("\n\n"):
        data_lines = [
            line[5:].strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        try:
            event = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            continue
        if event.get("type") == "final":
            final = event
    return final


def _chat(base: str, class_id: str, session_id: str, message: str) -> dict[str, Any]:
    url = f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/chat/stream"
    req = urllib.request.Request(
        url,
        data=json.dumps({"message": message}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return _parse_sse_final(text)


def _delete_lesson(wiki_root: pathlib.Path, class_id: str, lesson_date: str) -> None:
    lesson_dir = wiki_root / "wiki" / "classes" / class_id / "lessons" / lesson_date
    if lesson_dir.is_dir():
        import shutil

        shutil.rmtree(lesson_dir)
        print(f"deleted lesson {lesson_dir}")
    else:
        print(f"no lesson dir {lesson_dir}")


def _seed_via_service(session_id: str, class_id: str) -> str:
    """Attach mini fixture into an existing session via PlanService + draft store."""
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings
    from app.services.plan_service import PlanService
    from app.services.workflow_drafts import (
        WorkflowDraftStore,
        default_workflow_draft_store_path,
    )
    from app.teacher_agent.agents import AgentRunner
    from app.teacher_agent.wiki.store import WikiStore

    settings = get_settings()
    wiki = WikiStore(settings.wiki_root)
    drafts = WorkflowDraftStore(default_workflow_draft_store_path(wiki.root))
    plan = PlanService(
        wiki=wiki,
        agents=AgentRunner(wiki=wiki),
        workflow_drafts=drafts,
    )
    summary = plan.attach_prebuilt_material(
        class_id,
        session_id,
        package_dir=FIXTURE,
    )
    mid = summary.material_id
    print(f"seeded material {mid} into session {session_id}")
    return mid


def _upload_pdf(base: str, class_id: str, session_id: str, pdf: pathlib.Path) -> str:
    boundary = "----KpMoE2EBoundary"
    filename = pdf.name
    file_bytes = pdf.read_bytes()
    parts: list[bytes] = []
    for name, value in (("arm", "textbook"),):
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    mime = mimetypes.guess_type(filename)[0] or "application/pdf"
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    url = f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/materials"
    data = _request(
        "POST",
        url,
        raw=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        timeout=900,
    )
    mid = str(data["material_id"])
    print(f"uploaded material {mid}")
    return mid


def _run_inprocess(class_id: str, delete_lesson: str, wiki_root: pathlib.Path) -> int:
    """Seed fixture + both prompts via FastAPI TestClient (no live uvicorn)."""
    import os

    os.environ["WIKI_ROOT"] = str(wiki_root)
    sys.path.insert(0, str(BACKEND))
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.config import get_settings
    from app.main import app
    from app.services.ingest_service import IngestService
    from app.services.plan_service import PlanService
    from app.openai_bootstrap import configure_openai_from_settings
    from app.teacher_agent.agents import AgentRunner
    from app.teacher_agent.wiki.store import WikiStore
    from tests.evals.harness import run_chat_turn, seed_plan_material_fixture, start_session

    if delete_lesson:
        _delete_lesson(wiki_root, class_id, delete_lesson)

    settings = get_settings()
    if not configure_openai_from_settings(settings):
        print("FAIL: OPENAI_API_KEY not configured")
        return 1

    wiki = WikiStore(wiki_root)
    agents = AgentRunner(settings=settings, wiki=wiki)
    ingest = IngestService(wiki=wiki, agents=agents)
    plan = PlanService(wiki=wiki, agents=agents)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.plan_service = plan  # type: ignore[attr-defined]
            session_id = start_session(client, workflow="plan", class_id=class_id)
            material_id = seed_plan_material_fixture(
                client,
                class_id=class_id,
                session_id=session_id,
                fixture_name="mini_bonding_package",
            )
            print(f"session={session_id} material={material_id}")
            print("--- turn 1 ---")
            run_chat_turn(
                client,
                workflow="plan",
                class_id=class_id,
                session_id=session_id,
                message=PROMPT_1,
            )
            print("--- turn 2 ---")
            result = run_chat_turn(
                client,
                workflow="plan",
                class_id=class_id,
                session_id=session_id,
                message=PROMPT_2,
            )
            md = str(
                result.final.get("artifact_markdown")
                or result.final.get("plan_markdown")
                or result.final.get("markdown")
                or ""
            )
            matches = ASSET_RE.findall(md)
            print(f"asset refs: {matches[:8]}")
            if not matches:
                print("FAIL: no assets/img- in plan_markdown")
                return 1
            filename = matches[0].split("/")[-1]
            asset = client.get(
                f"/api/classes/{class_id}/plan/sessions/{session_id}"
                f"/materials/{material_id}/assets/{filename}"
            )
            if asset.status_code != 200 or len(asset.content) < 100:
                print(
                    f"FAIL: asset GET {asset.status_code} len={len(asset.content)}"
                )
                return 1
            print(f"PASS: embed + asset OK ({len(asset.content)} bytes)")
    finally:
        app.dependency_overrides.clear()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8011")
    parser.add_argument("--class-id", default=CLASS_ID)
    parser.add_argument("--delete-lesson", default="", help="YYYY-MM-DD to delete")
    parser.add_argument(
        "--wiki-root",
        default=str(BACKEND / "teacher_wiki_sandbox"),
        help="Used with --delete-lesson / --inprocess",
    )
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="Run via TestClient + mini_bonding_package seed (recommended)",
    )
    parser.add_argument(
        "--seed-via-service",
        action="store_true",
        help="Attach mini_bonding_package via PlanService (restart backend after)",
    )
    parser.add_argument("--pdf", type=pathlib.Path, default=None, help="Upload this PDF")
    parser.add_argument(
        "--session-id",
        default="",
        help="Reuse session (default: create new)",
    )
    parser.add_argument("--skip-chat", action="store_true", help="Only seed/upload")
    args = parser.parse_args()

    if args.inprocess:
        return _run_inprocess(
            args.class_id,
            args.delete_lesson,
            pathlib.Path(args.wiki_root),
        )

    if args.delete_lesson:
        _delete_lesson(pathlib.Path(args.wiki_root), args.class_id, args.delete_lesson)

    base = args.base.rstrip("/")
    class_id = args.class_id
    session_id = args.session_id
    if not session_id:
        started = _request(
            "POST",
            f"{base}/api/classes/{class_id}/plan/sessions",
            payload={},
        )
        session_id = str(started["session_id"])
        print(f"started session {session_id}")

    material_id = ""
    if args.pdf:
        material_id = _upload_pdf(base, class_id, session_id, args.pdf)
    elif args.seed_via_service:
        material_id = _seed_via_service(session_id, class_id)
        print(
            "NOTE: if the API server already had this session in memory, "
            "restart uvicorn so it reloads materials from the draft store."
        )
    else:
        draft = _request(
            "GET",
            f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/draft",
        )
        mats = draft.get("materials") or []
        if not mats:
            raise SystemExit(
                "No materials on session. Pass --pdf PATH, --seed-via-service, "
                "or --inprocess."
            )
        material_id = str(mats[0]["material_id"])
        print(f"using existing material {material_id}")

    if not args.skip_chat:
        print("--- turn 1 ---")
        _chat(base, class_id, session_id, PROMPT_1)
        print("--- turn 2 ---")
        final = _chat(base, class_id, session_id, PROMPT_2)
        md = str(
            final.get("artifact_markdown")
            or final.get("plan_markdown")
            or final.get("markdown")
            or ""
        )
        if not md:
            draft = _request(
                "GET",
                f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/draft",
            )
            md = str(draft.get("plan_markdown") or "")
        matches = ASSET_RE.findall(md)
        print(f"asset refs: {matches[:8]}")
        if not matches:
            print("FAIL: no assets/img- in plan_markdown")
            return 1
        filename = matches[0].split("/")[-1]
        asset_url = (
            f"{base}/api/classes/{class_id}/plan/sessions/{session_id}"
            f"/materials/{material_id}/assets/{filename}"
        )
        body = _request("GET", asset_url, timeout=30)
        if not isinstance(body, (bytes, bytearray)) or len(body) < 100:
            print(f"FAIL: asset GET weak response for {asset_url}")
            return 1
        print(f"PASS: embed + asset OK ({len(body)} bytes) {asset_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
