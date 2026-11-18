# SA-ASR EAR-1 Submission Conversion

Converts an EAR-1 ESR-ON submission into SegLST rows for
`normalization/ear1_norm` and `scoring/ear1_scorer`.

- Input: `hyp` submission ZIP (one `<session_id>.stm` per session), `ref`
  directory with one reference `<session_id>.stm` per session, `sessions`
  organizer `sessions.json`.
- Checks: ZIP members, STM fields, session IDs and timestamps.
- Rows are sorted by start and end time. A row is dropped on both sides when
  it overlaps an `exclude` interval or a reference row whose text contains
  `*`. This runs before normalization, which would remove the `*`.
- Output: `ref.seglst.json`, `hyp.seglst.json` (text not yet normalized) and
  `sessions.json`.

Parsing and validation are copied from the organizer scorer
(`openbench-integration-0.1`); see `conversion/ear1_submission_format.py`.
