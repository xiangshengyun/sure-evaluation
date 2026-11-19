# SD EAR-1 Submission Conversion

Converts an EAR-1 ESD-ON submission into SegLST rows for `scoring/ear1_scorer`.

- Input: `hyp` submission ZIP (`submission.rttm`, optional
  `empty_sessions.txt`), `ref` reference RTTM file or a directory containing
  `reference.rttm`, `sessions` organizer
  `sessions.json`.
- Checks: ZIP members, RTTM fields, session IDs, timestamps within the
  recording, and that every session is covered by rows or an empty
  declaration.
- Each session is cropped to its `uem` regions (the whole recording when
  absent), and the regions are joined into one timeline.
- Output: `ref.seglst.json`, `hyp.seglst.json` and `sessions.json` with the
  scored duration of each session.

Parsing and validation are copied from the organizer scorer
(`openbench-integration-0.1`); see `conversion/ear1_submission_format.py`.
