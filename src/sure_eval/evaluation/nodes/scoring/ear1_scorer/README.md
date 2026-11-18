# EAR-1 Scorer

## Purpose

`scoring/ear1_scorer` computes EAR-1 DER and character cpCER from converted
SegLST rows and pools the counts over sessions. It does not parse submission
ZIPs; the EAR-1 conversion profiles do that.

## Task Scenarios

- SD: `sd.any.der.conversion_sd_ear1_submission_v1.ear1_scorer_v1`.
- SA-ASR: `sa_asr.zh.cpcer.conversion_sa_asr_ear1_submission_v1.ear1_norm_v1.ear1_scorer_v1`.
- Neither route is a task default.

## Input

- Schema: `seglst`.
- Roles: `ref`, `hyp`, `sessions` (converted session list; DER also needs
  `scored_duration_s`).
- Alignment key: `session_id`.
- cpCER expects text already normalized by `normalization/ear1_norm`.

## Output

- Schema: `ear1_metric_report`.
- Fields: `scorer_version`, `task` (`ESD-ON` or `ESR-ON`), `track`, `metric`,
  `score`, `score_pct`, `session_count`, `counts`.
- DER counts: `miss_s`, `fa_s`, `conf_s`, `ref_s`.
- cpCER counts: `substitutions`, `deletions`, `insertions`,
  `reference_characters`.
- Lower is better.

## Versioned Computation

- Node id: `scoring/ear1_scorer`.
- Version: `v1`.
- Organizer scorer version: `openbench-integration-0.1`.
- Internal stages: `metric_scoring`, `pooled_aggregation`.
- DER: collar 0, overlap scored, one speaker mapping per session. Error time
  is summed over sessions and divided by reference speaker time.
- cpCER: per-speaker text joined in time order, speakers matched by minimum
  character edits, errors summed over reference characters.
- `distance_backend`: `builtin` (default) or `agwer`. Totals are the same;
  the S/D/I split can differ on ties.

## Runtime and Assets

- Runtime: `pip`.
- Package: `scipy>=1.10`.

```bash
python -m pip install 'scipy>=1.10'
sure-eval env check --node scoring/ear1_scorer
```

- `agwer` needs the organizer `requirements-scoring-fast.txt`.
- No checkpoints or binaries.

## Source and References

- `metrics.py` is the organizer `ear1_metrics.py` (Git blob
  `2d2e578d6de56afe319603e7b0e0e56654f931c5`, `egs/ear1/local`), changed only
  by one line split for lint.
- Session pooling in `node.py` follows the organizer `score.py`
  (`openbench-integration-0.1`).
- https://earchallenge.github.io/ear1/
- https://github.com/earchallenge/ear1-baselines

## Limitations

- A new organizer scorer version needs a new node version.
- Oracle speaker count and VAD are not enforced.
- Not comparable with the MeetEval DER or cpWER routes.
