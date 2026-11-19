# SD — Speaker Diarization

Evaluate speaker diarization outputs with Diarization Error Rate (DER).

```bash
sure-eval metric routes sd --metric der
```

## Metrics

| Metric | Pipeline ID | Nodes | Params |
|:-------|:------------|:------|:-------|
| `der` | `sd.any.der.meeteval_v1` | `scoring/meeteval` | `collar: 0.25` |
| `der` (EAR-1) | `sd.any.der.conversion_sd_ear1_submission_v1.ear1_scorer_v1` | `conversion/sd__ear1_submission` → `scoring/ear1_scorer` | collar 0, organizer scorer `openbench-integration-0.1` |

`sd.any.der.meeteval_v1` is the default. The two routes are not comparable:
MeetEval averages DER over sessions with a 0.25 s collar; EAR-1 pools error
time over sessions with no collar.

## Input Format

Reference and hypothesis annotation files in a MeetEval-supported format:

- RTTM
- STM
- CTM
- SegLST

Example RTTM line:

```text
SPEAKER meeting_001 1 12.34 2.50 <NA> <NA> speaker_A <NA>
```

## CLI Usage

```bash
sure-eval metric describe sd --metric der --output /tmp/sd.json
sure-eval metric run --pipeline /tmp/sd.json \
  --ref-file ref.rttm --hyp-file hyp.rttm --output-dir /tmp/sd_eval
```

## Python API

```python
from sure_eval.evaluation.scripts import run_task

report = run_task(
    "sd",
    ref_file="ref.rttm",
    hyp_file="hyp.rttm",
    metric="der",
    output_dir="/tmp/sd_eval",
)
print(report.score)
```

## Output

- `report.json` — `score` (DER), `num_sessions`, missed/false-alarm/speaker-error times.
- `pipeline_description.json` — canonical `metric`, selected `pipeline_id`,
  `execution_metrics`, `computation_node_ids`, relative `task_config_path` /
  `route_config_path`, `script_entrypoint`, `executor`, and node versions.

## Environment Notes

SD requires `meeteval`. Install with:

```bash
pip install -e ".[diarization]"
```

Or ensure the `scoring/meeteval` node environment is set up:

```bash
sure-eval env setup --node scoring/meeteval
```

## EAR-1 Route

Scores EAR-1 (ICASSP 2027 Grand Challenge) ESD-ON submissions with the
organizer scorer. D1 and R1 use the same route; the platform passes the
reference files of the selected track.

| Item | Version |
|:--|:--|
| `conversion/sd__ear1_submission` | `v1` |
| `scoring/ear1_scorer` | `v1` |
| Organizer scorer | `openbench-integration-0.1` |

Inputs:

- `--hyp-file`: submission ZIP with `submission.rttm` at the root and an
  optional `empty_sessions.txt` listing sessions with no speech.
- `--ref-file`: reference RTTM, or a directory containing `reference.rttm`.
- `--sessions-file`: organizer `sessions.json`.

```json
{
  "track": "D1",
  "sessions": {
    "EVAL001": {"duration_s": 9, "uem": [[0, 7], [8, 9]]},
    "EVAL002": {"duration_s": 3}
  }
}
```

`track` must be `D1` or `R1` and is copied to the report; check it against the
leaderboard. `uem` is optional; the whole recording is scored without it. The
run fails if a session is missing or unknown, or a row is malformed or outside
the recording.

DER: collar 0, overlap scored, one speaker mapping per session over its UEM.
Missed, false-alarm and confusion time are summed over sessions and divided by
total reference speaker time.

Setup and run with the bundled fixtures:

```bash
python -m pip install 'scipy>=1.10'
sure-eval env check --node scoring/ear1_scorer

sure-eval metric describe sd \
  --pipeline-id sd.any.der.conversion_sd_ear1_submission_v1.ear1_scorer_v1 \
  --output sd_ear1.json
sure-eval metric run --pipeline sd_ear1.json \
  --hyp-file tests/fixtures/ear1/esd/submission.zip \
  --ref-file tests/fixtures/ear1/esd/reference \
  --sessions-file tests/fixtures/ear1/esd/reference/sessions.json \
  --output-dir sd_ear1 --validate-env
```

`sd_ear1/report.json` → `details.scoring_result`:

```json
{"scorer_version": "openbench-integration-0.1", "task": "ESD-ON", "track": "D1", "metric": "DER",
 "score": 0.5, "score_pct": 50.0, "session_count": 2,
 "counts": {"miss_s": 3.0, "fa_s": 1.0, "conf_s": 1.0, "ref_s": 10.0}}
```

Converted rows are kept in `sd_ear1/conversion/sd__ear1_submission/`.
`sure-eval env setup` does not install `pip` runtime nodes yet.
