# EAR-1 OpenBench scoring

This node implements the EAR-1 OpenBench ESD-ON/DER and ESR-ON/cpCER
submission contract. It validates the participant ZIP and organizer reference
metadata, then returns pooled score counts. It does not run inference.

The integrated default backend is an in-process scorer. When SciPy is
available it uses SciPy's upstream Hungarian assignment implementation, which
matches the standalone handoff. A small exact fallback keeps the default
path runnable in a minimal SURE installation. The optional `agwer` backend
requires the pinned dependencies from the external EAR-1 package.

The external handoff's `requirements.txt` is still required when running its
standalone `score.py` directly. It is not automatically installed by SURE's
`env setup` because the integrated default scorer can run without it.

## CLI

```bash
sure-eval metric routes ear1 --metric der --track D1 --json
sure-eval metric describe ear1 --metric der --track D1 --output ear1_esd_d1.json
sure-eval metric run --pipeline ear1_esd_d1.json \
  --submission submission.zip \
  --reference-dir /private/organizer/esd/D1 \
  --output-dir ear1_esd_d1
```

For ESR-ON use `--metric cpcer` and the corresponding `R1`/`D1` track. The
reference directory must remain on the scoring worker; it is never included
in the participant ZIP.
