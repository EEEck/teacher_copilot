from app.teacher_agent.wiki.subject_frameworks import select_framework


def test_generating_profile_uses_the_class_route_and_writes_only_class_memory(wiki):
    path = wiki.framework_profile_path("chemie_9b_2026_27")
    path.unlink(missing_ok=True)

    rendered = wiki.regenerate_framework_profile("chemie_9b_2026_27")

    assert path.exists()
    assert rendered == path.read_text(encoding="utf-8")
    assert "teaching_frameworks/09/key_summary.md" in rendered
    assert "authority: teacher_adjusted_class_profile" in rendered


def test_regenerating_profile_preserves_existing_approved_adjustments(wiki):
    path = wiki.framework_profile_path("chemie_9b_2026_27")
    framework = select_framework(wiki, "chemie", 9, "NTG")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "authority: teacher_adjusted_class_profile\n"
        "---\n\n"
        "# Teaching Framework Profile - chemie_9b_2026_27\n\n"
        "## Teacher-approved adjustments\n"
        "- Use more particle-model drawings before equations.\n\n"
        "## Class-specific cautions\n"
        "- Contrast ion charge with oxidation number explicitly.\n",
        encoding="utf-8",
    )

    rendered = wiki.regenerate_framework_profile("chemie_9b_2026_27")

    assert framework.path in rendered
    assert "Use more particle-model drawings before equations." in rendered
    assert "Contrast ion charge with oxidation number explicitly." in rendered


def test_profile_generation_rejects_mismatched_curriculum_subject(wiki):
    path = wiki.class_dir("chemie_9b_2026_27") / "curriculum_profile.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("subject: chemie", "subject: physik"), encoding="utf-8")

    try:
        wiki.regenerate_framework_profile("chemie_9b_2026_27")
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected mismatched curriculum subject to be rejected")
