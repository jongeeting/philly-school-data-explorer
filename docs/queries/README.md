# Example queries

DuckDB SQL, run from the repository root against `core/` and `marts/` (or the same files from a
release). Every file here is run by `tests/test_queries.py`, so these stay correct.

| File | Question |
| --- | --- |
| `one_school_over_time.sql` | How have one school's enrollment, test scores, and attendance changed? |
| `suspensions_by_group.sql` | What share of students were suspended, by race, in the federal data? |
| `facility_condition_tiers.sql` | How many assessed sites fall in each district condition tier? |
| `lead_and_asbestos_by_governance.sql` | Which kinds of schools have recorded damaged lead paint or asbestos? |
| `buildings_with_recorded_damage.sql` | Which school buildings have recorded damage in an asbestos, lead-paint, or water inspection, and who is there now? |

Rules for anything you build from these: read `status` before `value`; give the `sy` and the
source; do not rank schools; never rebuild groups under 20 students by subtraction.
