"""OCR subject vs class Fach matching."""

from app.services.materials_subject import (
    is_known_subject_mismatch,
    normalize_subject_family,
    raise_if_off_subject,
)


def test_aliases_collapse_to_families():
    assert normalize_subject_family("Chemie") == "chemie"
    assert normalize_subject_family("chemistry") == "chemie"
    assert normalize_subject_family("English") == "esl"
    assert normalize_subject_family("ESL") == "esl"
    assert normalize_subject_family("Englisch") == "esl"
    assert normalize_subject_family("") is None
    assert normalize_subject_family("(unknown)") is None
    assert normalize_subject_family("organic notes") is None


def test_esl_mismatches_chemie():
    assert is_known_subject_mismatch("chemie", "English")
    assert is_known_subject_mismatch("Chemie", "ESL")
    assert not is_known_subject_mismatch("chemie", "Chemistry")
    assert not is_known_subject_mismatch("chemie", "")
    assert not is_known_subject_mismatch("chemie", "worksheet")


def test_raise_if_off_subject_message():
    try:
        raise_if_off_subject(class_subject="chemie", annotation_subject="English")
    except ValueError as exc:
        assert "English" in str(exc)
        assert "chemie" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
    raise_if_off_subject(class_subject="chemie", annotation_subject="")
