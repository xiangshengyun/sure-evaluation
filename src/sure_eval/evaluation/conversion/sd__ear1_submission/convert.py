"""EAR-1 ESD-ON conversion: submission ZIP and reference RTTM input to scored SegLST rows.

Validates the ZIP and session coverage against ``sessions.json``, then projects
each session onto its scoring regions (UEM) so the regions form one contiguous
timeline. Output rows keep the organizer scorer's order and float values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sure_eval.evaluation.conversion.ear1_submission_format import (
    load_diarization_pair,
    load_sessions,
    project,
    write_seglst,
)

CONVERSION_ID = "sd__ear1_submission"


@dataclass
class Ear1Conversion:
    ref_file: str
    hyp_file: str
    sessions_file: str
    track: str | None
    trace: dict[str, Any] = field(default_factory=dict)


def convert_ear1_diarization(
    *, ref_file: str, hyp_file: str, sessions_file: str, output_dir: str | Path
) -> Ear1Conversion:
    """Convert an ESD-ON submission ZIP and reference RTTM file or directory."""

    track, sessions = load_sessions(sessions_file)
    ref, hyp = load_diarization_pair(hyp_file, ref_file, sessions)
    ref_rows, hyp_rows, scored = {}, {}, {}
    for sid, meta in sessions.items():
        ref_rows[sid], duration = project(ref.get(sid, []), meta["uem"])
        hyp_rows[sid], _ = project(hyp.get(sid, []), meta["uem"])
        scored[sid] = {"scored_duration_s": duration}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref_out, hyp_out, sessions_out = out / "ref.seglst.json", out / "hyp.seglst.json", out / "sessions.json"
    ref_count = write_seglst(ref_out, ref_rows)
    hyp_count = write_seglst(hyp_out, hyp_rows)
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
            "sessions_without_hypothesis": [sid for sid in sessions if not hyp.get(sid)],
            "ref_segments": ref_count,
            "hyp_segments": hyp_count,
        },
    )
