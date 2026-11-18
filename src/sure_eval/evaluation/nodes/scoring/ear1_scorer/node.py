"""EAR-1 scorer: pooled DER and character cpCER over converted SegLST rows."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sure_eval.evaluation.core.types import PipelineNodeResult

from .metrics import cpcer, der

NODE_ID = "scoring/ear1_scorer"
NODE_VERSION = "v1"
SCORER_VERSION = "openbench-integration-0.1"
METRICS = {
    "der": ("ESD-ON", "DER", "ref_s", ("miss_s", "fa_s", "conf_s")),
    "cpcer": ("ESR-ON", "cpCER", "reference_characters", ("substitutions", "deletions", "insertions")),
}


def score_ear1(
    *,
    metric: str,
    ref_file: str,
    hyp_file: str,
    sessions_file: str,
    distance_backend: str = "builtin",
) -> tuple[dict[str, Any], PipelineNodeResult]:
    """Score converted rows and pool counts over every session in ``sessions_file``."""

    metric = metric.lower()
    if metric not in METRICS:
        raise ValueError(f"Unsupported EAR-1 metric: {metric}")
    config = json.loads(Path(sessions_file).read_text(encoding="utf-8"))
    sessions = config["sessions"]
    ref, hyp = _by_session(ref_file), _by_session(hyp_file)
    if metric == "der":
        counts = [_score_der(ref[sid], hyp[sid], meta["scored_duration_s"]) for sid, meta in sessions.items()]
    else:
        counts = [_score_cpcer(ref[sid], hyp[sid], distance_backend) for sid in sessions]
    task, label, denominator, errors = METRICS[metric]
    totals = {key: sum(row[key] for row in counts) for key in counts[0]}
    if not totals[denominator] > 0:
        raise ValueError("Zero reference denominator for the track")
    value = sum(totals[key] for key in errors) / totals[denominator]
    result = {
        "scorer_version": SCORER_VERSION,
        "task": task,
        "track": config.get("track"),
        "metric": label,
        "score": value,
        "score_pct": 100 * value,
        "session_count": len(sessions),
        "counts": totals,
    }
    node_result = PipelineNodeResult(
        stage="scoring",
        node_id=NODE_ID,
        version=NODE_VERSION,
        details={
            "backend": "ear1_scorer",
            "scorer_version": SCORER_VERSION,
            "metric": metric,
            "distance_backend": distance_backend if metric == "cpcer" else None,
            "result": result,
        },
        internal_stages=("metric_scoring", "pooled_aggregation"),
    )
    return result, node_result


def _by_session(path: str) -> dict[str, list[dict[str, Any]]]:
    rows = defaultdict(list)
    for segment in json.loads(Path(path).read_text(encoding="utf-8")):
        rows[segment["session_id"]].append(
            {
                "speaker": segment["speaker"],
                "start": segment["start_time"],
                "end": segment["end_time"],
                "text": segment["words"],
            }
        )
    return rows


def _score_der(ref, hyp, duration):
    keys = ("miss_s", "fa_s", "conf_s", "ref_s")
    if not ref:
        return dict(zip(keys, (0.0, sum(row["end"] - row["start"] for row in hyp), 0.0, 0.0)))
    result = der(ref, hyp, duration)
    return {key: result[key] for key in keys}


def _streams(rows):
    result = defaultdict(str)
    for row in rows:
        if row["text"]:
            result[row["speaker"]] += row["text"]
    return result


def _score_cpcer(ref, hyp, backend):
    ref, hyp = _streams(ref), _streams(hyp)
    keys = ("substitutions", "deletions", "insertions", "reference_characters")
    if not ref:
        return dict(zip(keys, (0, 0, sum(map(len, hyp.values())), 0)))
    result = cpcer(ref, hyp, distance_backend=backend)
    return {key: result[key] for key in keys}
