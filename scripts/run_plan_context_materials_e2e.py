"""Live API checks for plan Context / session materials.

Default: GET draft (class_core + materials) then upload the ESL fixture to
Chemie 9b and assert 422 off-subject reject. Uses the running backend
(default http://localhost:8011) and live Mistral OCR.

Browser steps: ``scripts/plan_context_materials_hitl.md``.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import pathlib
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ESL_PDF = (
    BACKEND
    / "tests"
    / "fixtures"
    / "materials"
    / "esl_textbook_sample_pages_9_to_11.pdf"
)
CLASS_ID = "chemie_9b_2026_27"


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 600,
) -> tuple[int, Any]:
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
                return resp.status, json.loads(body.decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(detail)
        except json.JSONDecodeError:
            parsed = detail
        return exc.code, parsed


def _error_message(body: Any) -> str:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if body.get("detail"):
            return str(body["detail"])
    return str(body)


def _multipart_pdf(path: pathlib.Path, *, arm: str = "textbook") -> tuple[bytes, str]:
    boundary = "----kp-context-materials"
    filename = path.name
    file_bytes = path.read_bytes()
    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="arm"\r\n\r\n'
            f"{arm}\r\n"
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
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _check_draft(base: str, class_id: str, session_id: str) -> int:
    status, draft = _request(
        "GET",
        f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/draft",
    )
    if status != 200 or not isinstance(draft, dict):
        print(f"FAIL: GET draft -> {status} {_error_message(draft)}")
        return 1
    core = draft.get("class_core")
    if not isinstance(core, list) or not core:
        print("FAIL: draft missing class_core (restart backend on current code)")
        return 1
    keys = {item.get("key") for item in core if isinstance(item, dict)}
    for required in (
        "planning_brief",
        "recent_lessons",
        "top_misconceptions",
        "teaching_patterns",
        "copilot_profile",
        "session_summaries",
    ):
        if required not in keys:
            print(f"FAIL: class_core missing {required}: {sorted(keys)}")
            return 1
    materials = draft.get("materials") or []
    print(f"draft ok: class_core={len(core)} materials={len(materials)}")
    for item in materials:
        print(f"  - {item.get('material_id')} {item.get('title')}")
    return 0


def _patch_planning_brief(
    base: str, class_id: str, session_id: str, *, exclude: bool
) -> int:
    status, body = _request(
        "PATCH",
        f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/context",
        payload={"excluded_core_keys": ["planning_brief"] if exclude else []},
    )
    if status != 200 or not isinstance(body, dict):
        print(f"FAIL: PATCH context -> {status} {_error_message(body)}")
        return 1
    items = {
        item["key"]: item
        for item in body.get("class_core") or []
        if isinstance(item, dict)
    }
    included = items.get("planning_brief", {}).get("included")
    expect = not exclude
    if included is not expect:
        print(f"FAIL: planning_brief included={included} expected={expect}")
        return 1
    print(f"PATCH context ok: planning_brief included={included}")
    return 0


def _upload_esl_expect_422(
    base: str, class_id: str, session_id: str, pdf: pathlib.Path
) -> int:
    if not pdf.is_file():
        print(f"FAIL: missing ESL fixture {pdf}")
        return 1
    before_status, before = _request(
        "GET",
        f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/draft",
    )
    if before_status != 200 or not isinstance(before, dict):
        print(f"FAIL: GET draft before upload -> {before_status}")
        return 1
    before_ids = {
        item.get("material_id") for item in (before.get("materials") or [])
    }
    raw, content_type = _multipart_pdf(pdf)
    print(f"uploading {pdf.name} (live OCR; may take a minute)...")
    status, body = _request(
        "POST",
        f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/materials",
        raw=raw,
        content_type=content_type,
        timeout=900,
    )
    message = _error_message(body)
    if status == 503:
        print(f"FAIL: OCR unavailable (503): {message}")
        return 1
    if status != 422:
        print(f"FAIL: ESL upload -> {status} {message}")
        return 1
    lowered = message.lower()
    if "english" not in lowered and "esl" not in lowered and "englisch" not in lowered:
        print(f"FAIL: 422 message missing subject: {message}")
        return 1
    after_status, after = _request(
        "GET",
        f"{base}/api/classes/{class_id}/plan/sessions/{session_id}/draft",
    )
    if after_status != 200 or not isinstance(after, dict):
        print(f"FAIL: GET draft after upload -> {after_status}")
        return 1
    after_ids = {item.get("material_id") for item in (after.get("materials") or [])}
    if after_ids != before_ids:
        print(f"FAIL: inventory changed after reject {before_ids} -> {after_ids}")
        return 1
    print(f"PASS: ESL reject 422 ({message})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8011")
    parser.add_argument("--class-id", default=CLASS_ID)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--pdf", type=pathlib.Path, default=ESL_PDF)
    parser.add_argument(
        "--skip-esl-reject",
        action="store_true",
        help="Only GET draft / class_core checks (no live OCR)",
    )
    parser.add_argument(
        "--patch-context",
        action="store_true",
        help="PATCH planning_brief off then back on (mutates the active session)",
    )
    args = parser.parse_args()

    base = args.base.rstrip("/")
    class_id = args.class_id
    session_id = args.session_id
    if not session_id:
        status, started = _request(
            "POST",
            f"{base}/api/classes/{class_id}/plan/sessions",
            payload={},
        )
        if status != 200 or not isinstance(started, dict):
            print(f"FAIL: start session -> {status} {_error_message(started)}")
            return 1
        session_id = str(started["session_id"])
        print(f"session {session_id}")

    if _check_draft(base, class_id, session_id) != 0:
        return 1

    if args.patch_context:
        if _patch_planning_brief(base, class_id, session_id, exclude=True) != 0:
            return 1
        if _patch_planning_brief(base, class_id, session_id, exclude=False) != 0:
            return 1

    if args.skip_esl_reject:
        print("PASS: draft + context checks (ESL reject skipped)")
        return 0
    return _upload_esl_expect_422(base, class_id, session_id, args.pdf)


if __name__ == "__main__":
    raise SystemExit(main())
