# EAR-1 OpenBench

EAR-1 is registered as the `ear1` task. It has two scoring protocols:

| Task | Metric | Track selector | Submission |
| --- | --- | --- | --- |
| ESD-ON | DER | D1 or R1 | ZIP with root `submission.rttm`; optional `empty_sessions.txt` |
| ESR-ON | cpCER | D1 or R1 | ZIP with one root `<session_id>.stm` per session |

The organizer reference directory is private to the scoring worker. It must
contain `sessions.json` and the task-specific reference files described by the
EAR-1 handoff. The ZIP and reference directory are passed separately.

Discover and describe an exact route:

```bash
sure-eval metric routes ear1 --metric der --track D1 --json
sure-eval metric describe ear1 --metric der --track D1 \
  --output ear1_esd_d1.json
```

Run ESD-ON:

```bash
sure-eval metric run --pipeline ear1_esd_d1.json \
  --submission submission.zip \
  --reference-dir /private/organizer/ear1/esd/D1 \
  --output-dir ear1_esd_d1 --validate-env
```

For ESR-ON use `--metric cpcer` and the selected `D1` or `R1` route. The
optional `--distance-backend agwer` requires the pinned EAR-1 fast-scoring
dependencies; the default `builtin` backend is self-contained.

The report keeps the official scorer version, `score`, `score_pct`, pooled
`counts`, track, session count, and the full input contract. ESD uses zero
collar, overlap-inclusive DER. ESR uses EAR-1 normalized character-level
speaker matching and cpCER. These protocols are separate from the existing
`sd.any.der.meeteval_v1` route.
