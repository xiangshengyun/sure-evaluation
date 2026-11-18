# SA-ASR — Speaker-Aware ASR

Evaluate multi-speaker ASR outputs. Reports cpWER as the main metric and DER as a companion metric.
The EAR-1 route reports character-level cpCER for Mandarin.

```bash
sure-eval metric routes sa_asr --language en --metric cpwer
```

## Metrics

| Metric | Pipeline ID | Nodes | Params |
|:-------|:------------|:------|:-------|
| `cpwer` (main, en) | `sa_asr.en.cpwer.conversion_sa_asr_cpwer_v1.whisper_norm_english_v1.meeteval_v1` | `conversion/sa_asr__cpwer` → `normalization/whisper_norm` → `scoring/meeteval` | `collar: 0.5`, `profile: english` |
| `cpwer` (main, zh) | `sa_asr.zh.cpwer.conversion_sa_asr_cpwer_v1.gstar_norm_v1.meeteval_v1` | `conversion/sa_asr__cpwer` → `normalization/gstar_norm` → `scoring/meeteval` | `collar: 0.5` |
| `der` (companion) | same selected route | same selected route | recorded alongside cpWER |
| `cpcer` (EAR-1, zh) | `sa_asr.zh.cpcer.conversion_sa_asr_ear1_submission_v1.ear1_norm_v1.ear1_scorer_v1` | `conversion/sa_asr__ear1_submission` → `normalization/ear1_norm` → `scoring/ear1_scorer` | organizer scorer `openbench-integration-0.1` |

`cpcer` is not comparable with `cpwer`: MeetEval cpWER splits text on
whitespace, so unsegmented Mandarin is scored per utterance, while cpCER scores
characters.

## Input Format

STM six-field rows:

```text
session_id channel speaker start end <transcript>
```

Example:

```text
meeting_001 1 spk_A 12.34 14.80 hello world
```

The pipeline converts STM to key-text for normalization, normalizes the transcript text with the language-selected normalization node, then converts back to STM before MeetEval scoring.

## CLI Usage

```bash
sure-eval metric describe sa_asr --language en --metric cpwer --output /tmp/sa_asr_en.json
sure-eval metric run --pipeline /tmp/sa_asr_en.json \
  --ref-file ref.stm --hyp-file hyp.stm --output-dir /tmp/sa_asr_eval

sure-eval metric describe sa_asr --language zh --metric cpwer --output /tmp/sa_asr_zh.json
```

## Python API

```python
from sure_eval.evaluation.scripts import run_task

report = run_task(
    "sa_asr",
    ref_file="ref.stm",
    hyp_file="hyp.stm",
    language="en",
    metric="cpwer",
    output_dir="/tmp/sa_asr_eval",
)
print(report.score)  # cpWER
```

## Output

- `report.json` — `score` (cpWER), `der`, `num_sessions`.
- `pipeline_description.json` — canonical `metric`, selected `pipeline_id`,
  `execution_metrics`, `computation_node_ids` including conversion nodes,
  relative `task_config_path` / `route_config_path`, `script_entrypoint`,
  `executor`, conversion trace, and node versions.

## EAR-1 Route

Scores EAR-1 (ICASSP 2027 Grand Challenge) ESR-ON submissions with the
organizer scorer. D1 and R1 use the same route; the platform passes the
reference files of the selected track.

| Item | Version |
|:--|:--|
| `conversion/sa_asr__ear1_submission` | `v1` |
| `normalization/ear1_norm` | `v1` |
| `scoring/ear1_scorer` | `v1` |
| Organizer scorer | `openbench-integration-0.1` |

Inputs:

- `--hyp-file`: submission ZIP with one `<session_id>.stm` per session at the
  root. An empty file means no output for that session.
- `--ref-file`: directory with one reference `<session_id>.stm` per session.
- `--sessions-file`: organizer `sessions.json`. `track` must be `D1` or `R1`
  and is copied to the report. Per-session `exclude` lists extra intervals to
  drop.

STM rows have six fields; the transcript is last:

```text
EVAL001 1 spk02 0.0 1.0 你 好
```

cpCER:

1. Rows overlapping an `exclude` interval or a reference row containing `*`
   are dropped from both sides.
2. Text is normalized: NFKC, lowercase, whitespace and punctuation removed.
3. Each speaker's text is joined in time order. Speakers are matched to
   minimize character edits.
4. Substitutions, deletions and insertions are summed over sessions and
   divided by total reference characters.

Setup and run with the bundled fixtures:

```bash
python -m pip install 'scipy>=1.10'
sure-eval env check --node scoring/ear1_scorer

sure-eval metric describe sa_asr --language zh --metric cpcer --output sa_asr_ear1.json
sure-eval metric run --pipeline sa_asr_ear1.json \
  --hyp-file tests/fixtures/ear1/esr/submission.zip \
  --ref-file tests/fixtures/ear1/esr/reference \
  --sessions-file tests/fixtures/ear1/esr/reference/sessions.json \
  --output-dir sa_asr_ear1 --validate-env
```

Expected `score` is 0.625: 1 substitution, 2 deletions and 2 insertions over 8
reference characters. `report.json` → `details.scoring_result` also has
`scorer_version`, `task` (`ESR-ON`), `track`, `score_pct`, `session_count` and
`counts`.

The route parameter `distance_backend` is `builtin`. `agwer` gives the same
totals faster but needs the organizer `requirements-scoring-fast.txt`.

## Environment Notes

SA-ASR requires `meeteval`. Install with:

```bash
pip install -e ".[diarization]"
```
