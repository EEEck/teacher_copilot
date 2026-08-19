from app.services import class_provisioning as cp

SEEDED_CLASS = "chemie_9b_2026_27"


def test_provisioned_class_does_not_change_seeded_class_state(wiki):
    before_snapshot = wiki.get_snapshot(SEEDED_CLASS)
    before_timeline = wiki.get_timeline(SEEDED_CLASS)
    before_index = wiki.read_wiki_index(SEEDED_CLASS)

    summary = cp.create_class(
        wiki,
        cp.ClassSpec(
            label="Chemie 8a — 2026/27",
            subject="chemie",
            grade=8,
            section="a",
            school_year="2026_27",
        ),
    )

    assert summary.id == "chemie_8a_2026_27"
    assert wiki.get_snapshot(SEEDED_CLASS) == before_snapshot
    assert wiki.get_timeline(SEEDED_CLASS) == before_timeline
    assert wiki.read_wiki_index(SEEDED_CLASS) == before_index
