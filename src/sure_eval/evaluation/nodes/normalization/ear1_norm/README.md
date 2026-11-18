# EAR-1 Text Normalization

## Purpose

`normalization/ear1_norm` applies the EAR-1 cpCER text rule to SegLST rows.
It does not score.

## Task Scenarios

- SA-ASR: `sa_asr.zh.cpcer.conversion_sa_asr_ear1_submission_v1.ear1_norm_v1.ear1_scorer_v1`.

## Input

- Schema: `seglst`.
- Roles: `ref`, `hyp`.
- `*` and `exclude` handling must already be done by
  `conversion/sa_asr__ear1_submission`, because this node removes `*`.

## Output

- Schema: `seglst` with normalized `words`.
- Rows that become empty are dropped.
- Trace: input and kept segment counts per role.

## Versioned Computation

- Node id: `normalization/ear1_norm`.
- Version: `v1`.
- Internal stages: `seglst_parse`, `ear1_text_normalize`.
- Rule: Unicode NFKC, lowercase, remove whitespace and Unicode punctuation
  (category `P*`). Digits, symbols and traditional characters are kept.

## Runtime and Assets

- Runtime: `in_process`.
- No extra packages.

## Source and References

- `normalize_text` from the organizer `ear1_metrics.py`, imported from
  `scoring/ear1_scorer/metrics.py`.

## Limitations

- No number, traditional-simplified or filler rewriting.
