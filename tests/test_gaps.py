from phillyschools.gaps import AREA_ORDER, GAPS_MD, KINDS, PRIORITY_RANK, read_gaps, render_markdown


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


def test_generated_markdown_is_up_to_date():
    assert GAPS_MD.read_text() == render_markdown(read_gaps()), "run: uv run psd gaps"
