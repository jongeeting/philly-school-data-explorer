from phillyschools.gaps import (
    AREA_ORDER,
    GAPS_MD,
    KINDS,
    OWNERS,
    PRIORITY_RANK,
    QUESTIONS_MD,
    read_gaps,
    render_markdown,
    render_questions,
)


def test_gaps_are_well_formed():
    gaps = read_gaps()
    ids = [g["gap_id"] for g in gaps]
    assert len(ids) == len(set(ids))
    for g in gaps:
        assert g["area"] in AREA_ORDER
        assert g["kind"] in KINDS
        assert g["priority"] in PRIORITY_RANK
        assert g["status"] in {"open", "in-progress", "blocked", "closed"}
        assert g["gap"] and g["how_to_close"]
        assert g["who_can_close"] in OWNERS


def test_generated_markdown_is_up_to_date():
    assert GAPS_MD.read_text() == render_markdown(read_gaps()), "run: uv run psd gaps"


def test_district_questions_are_up_to_date():
    assert QUESTIONS_MD.read_text() == render_questions(read_gaps()), "run: uv run psd gaps"
