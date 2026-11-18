"""EAR-1 ESR-ON conversion: submission ZIP and reference STMs to scored SegLST rows.

Validates the ZIP against ``sessions.json`` and drops every row that overlaps an
organizer ``exclude`` interval or a reference row containing ``*``. Text is
left unnormalized; ``normalization/ear1_norm`` runs next.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sure_eval.evaluation.conversion.ear1_submission_format import (
    exclusion_spans,
    kept_rows,
    load_sessions,
    load_transcription_pair,
    write_seglst,
)

CONVERSION_ID = "sa_asr__ear1_submission"


@dataclass
class Ear1Conversion:
    ref_file: str
    hyp_file: str
    sessions_file: str
    track: str | None
    trace: dict[str, Any] = field(default_factory=dict)


def convert_ear1_transcription(
    *, ref_file: str, hyp_file: str, sessions_file: str, output_dir: str | Path
) -> Ear1Conversion:
    """Convert an ESR-ON submission ZIP (``hyp_file``) and reference STM directory (``ref_file``)."""

    track, sessions = load_sessions(sessions_file)
    ref, hyp = load_transcription_pair(hyp_file, ref_file, sessions)
    ref_rows, hyp_rows, dropped = {}, {}, 0
    for sid, meta in sessions.items():
        exclusions = exclusion_spans(ref[sid], meta)
        ref_rows[sid] = kept_rows(ref[sid], exclusions)
        hyp_rows[sid] = kept_rows(hyp[sid], exclusions)
        dropped += len(ref[sid]) + len(hyp[sid]) - len(ref_rows[sid]) - len(hyp_rows[sid])

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref_out, hyp_out, sessions_out = out / "ref.seglst.json", out / "hyp.seglst.json", out / "sessions.json"
    ref_count = write_seglst(ref_out, ref_rows)
    hyp_count = write_seglst(hyp_out, hyp_rows)
    scored = {sid: {} for sid in sessions}
    sessions_out.write_text(json.dumps({"track": track, "sessions": scored}, indent=1) + "\n", encoding="utf-8")
    return Ear1Conversion(
        ref_file=str(ref_out),
        hyp_file=str(hyp_out),
        sessions_file=str(sessions_out),
        track=track,
        trace={
            "conversion_id": CONVERSION_ID,
            "track": track,
            "session_count": len(sessions),
            "excluded_rows": dropped,
            "ref_segments": ref_count,
            "hyp_segments": hyp_count,
        },
    )
