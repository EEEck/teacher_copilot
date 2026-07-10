from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutivePatch,
    ExecutiveRuntime,
    apply_write_verification,
    artifact_fingerprint,
    apply_executive_patch,
    evaluate_write_gate,
    executive_api_payload,
    render_executive_runtime,
)


def test_blocking_finding_sets_needs_decision():
    runtime = ExecutiveRuntime()

    apply_executive_patch(
        runtime,
        ExecutivePatch(
            checked_categories=["identity"],
            findings=[
                ExecutiveFinding(
                    finding_id="student-s021",
                    category="identity",
                    severity="blocking",
                    summary="S-021 is not resolved in the active class.",
                    question="Which student or class should receive this note?",
                    evidence_refs=["reference_001"],
                )
            ],
        ),
    )

    assert [item.finding_id for item in runtime.open_blocking_findings()] == [
        "student-s021"
    ]
    assert executive_api_payload(runtime)["status"] == "needs_decision"


def test_teacher_resolution_closes_existing_finding():
    runtime = ExecutiveRuntime(
        findings={
            "scope-1": ExecutiveFinding(
                finding_id="scope-1",
                category="scope",
                severity="blocking",
                summary="The class is ambiguous.",
                question="Use 9a or 9b?",
            )
        }
    )

    apply_executive_patch(
        runtime,
        ExecutivePatch(
            resolved_findings={"scope-1": "Teacher confirmed 9b."},
            verification_summary="Class scope confirmed.",
        ),
    )

    assert runtime.findings["scope-1"].status == "resolved"
    assert runtime.open_blocking_findings() == []
    assert executive_api_payload(runtime)["status"] == "clear"


def test_advisory_finding_does_not_count_as_blocking():
    runtime = ExecutiveRuntime(
        findings={
            "assumption-1": ExecutiveFinding(
                finding_id="assumption-1",
                category="time_state",
                severity="advisory",
                summary="The new unit is assumed to follow the completed unit.",
            )
        }
    )

    assert runtime.open_blocking_findings() == []
    assert executive_api_payload(runtime)["status"] == "advisory"


def test_rendered_runtime_exposes_open_findings_without_hidden_reasoning():
    runtime = ExecutiveRuntime(
        findings={
            "scope-1": ExecutiveFinding(
                finding_id="scope-1",
                category="scope",
                severity="advisory",
                summary="Using the active class.",
            )
        }
    )

    rendered = render_executive_runtime(runtime)

    assert rendered.startswith("<executive_state>")
    assert '"finding_id": "scope-1"' in rendered
    assert rendered.endswith("</executive_state>")


def test_write_gate_requires_current_fingerprint_and_no_blocking_findings():
    runtime = ExecutiveRuntime()

    apply_write_verification(runtime, artifact="# Draft\n", patch=ExecutivePatch())

    assert evaluate_write_gate(runtime, "# Draft\n", structurally_ready=True).allowed
    changed = evaluate_write_gate(runtime, "# Changed\n", structurally_ready=True)
    assert changed.allowed is False
    assert changed.reason == "artifact_changed_since_verification"


def test_write_gate_blocks_open_finding_even_when_fingerprint_matches():
    runtime = ExecutiveRuntime()
    patch = ExecutivePatch(
        findings=[
            ExecutiveFinding(
                finding_id="student-s999",
                category="identity",
                severity="blocking",
                summary="S-999 is not resolved in the active class.",
                question="Which student should receive this note?",
            )
        ]
    )

    apply_write_verification(runtime, artifact="# Draft\n", patch=patch)

    gate = evaluate_write_gate(runtime, "# Draft\n", structurally_ready=True)
    assert gate.allowed is False
    assert gate.reason == "unresolved_blocking_finding"
    assert runtime.write_verification_fingerprint == artifact_fingerprint("# Draft\n")
