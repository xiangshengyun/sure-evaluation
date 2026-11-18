"""SD task routes: MeetEval DER and the EAR-1 organizer DER."""

from __future__ import annotations

import tempfile
from pathlib import Path

from sure_eval.evaluation.conversion.sd__ear1_submission import CONVERSION_ID as EAR1_CONVERSION_ID
from sure_eval.evaluation.conversion.sd__ear1_submission import convert_ear1_diarization
from sure_eval.evaluation.core.types import EvaluationFiles, EvaluationReport, MetricInputContract
from sure_eval.evaluation.nodes.scoring.ear1_scorer import score_ear1
from sure_eval.evaluation.nodes.scoring.meeteval import score_meeteval
from sure_eval.evaluation.pipeline_identity import (
    build_atomic_pipeline_id,
    component_trace_ids,
    conversion_component,
    node_component,
)

_SD_CONTRACT = MetricInputContract(
    metric_id="scoring/meeteval",
    required_roles=("hyp", "ref"),
    row_format="meeteval_annotation",
    alignment_key="session_id",
    aggregation="session_mean_error_rate",
    purpose="speaker_diarization_error_rate",
)


def evaluate_sd_files(
    ref_file: str,
    hyp_file: str,
    *,
    metric: str = "der",
    collar: float = 0.25,
) -> EvaluationReport:
    """Evaluate speaker diarization annotations with MeetEval DER."""

    normalized_metric = metric.lower()
    if normalized_metric not in {"der", "der_dscore", "dscore"}:
        raise ValueError(f"Unsupported SD metric: {metric}")
    input_files = EvaluationFiles.from_ref_hyp(ref_file=ref_file, hyp_file=hyp_file)
    _SD_CONTRACT.validate(input_files)
    _, scoring_result = score_meeteval(
        ref_file=ref_file,
        hyp_file=hyp_file,
        metric="der",
        collar=collar,
    )
    result = scoring_result.details["result"]
    components = (node_component("scoring/meeteval"),)
    pipeline_id = build_atomic_pipeline_id("sd", "any", "der", components)
    return EvaluationReport(
        task="SD",
        language="n/a",
        metric="der",
        score=float(result["der"]),
        pipeline_id=pipeline_id,
        pipeline_trace=(scoring_result,),
        input_contract=_SD_CONTRACT,
        input_files=input_files,
        computation_node_ids=component_trace_ids(components),
        details={
            "scoring_result": result,
            "input_contract": _SD_CONTRACT.as_dict(),
            "input_files": input_files.as_dict(),
            "params": {"collar": collar},
        },
    )


_SD_EAR1_CONTRACT = MetricInputContract(
    metric_id="scoring/ear1_scorer",
    required_roles=("hyp", "ref", "sessions"),
    row_format="ear1_esd_submission_zip",
    alignment_key="session_id",
    aggregation="pooled_error_seconds_over_reference_speaker_seconds",
    purpose="speaker_diarization_error_rate",
)


def evaluate_sd_ear1_files(
    ref_file: str,
    hyp_file: str,
    *,
    sessions_file: str,
    metric: str = "der",
    conversion_output_dir: str | None = None,
) -> EvaluationReport:
    """Score an EAR-1 ESD-ON submission ZIP with the organizer DER rules."""

    if metric.lower() != "der":
        raise ValueError(f"Unsupported SD metric: {metric}")
    input_files = EvaluationFiles(roles={"ref": ref_file, "hyp": hyp_file, "sessions": sessions_file})
    _SD_EAR1_CONTRACT.validate(input_files)
    components = (conversion_component(EAR1_CONVERSION_ID), node_component("scoring/ear1_scorer"))
    pipeline_id = build_atomic_pipeline_id("sd", "any", "der", components)
    with tempfile.TemporaryDirectory(prefix="sure_sd_ear1_") as temp_dir:
        conversion = convert_ear1_diarization(
            ref_file=ref_file,
            hyp_file=hyp_file,
            sessions_file=sessions_file,
            output_dir=Path(conversion_output_dir or temp_dir),
        )
        result, scoring_result = score_ear1(
            metric="der",
            ref_file=conversion.ref_file,
            hyp_file=conversion.hyp_file,
            sessions_file=conversion.sessions_file,
        )
    return EvaluationReport(
        task="SD",
        language="n/a",
        metric="der",
        score=float(result["score"]),
        pipeline_id=pipeline_id,
        pipeline_trace=(scoring_result,),
        input_contract=_SD_EAR1_CONTRACT,
        input_files=input_files,
        computation_node_ids=component_trace_ids(components),
        details={
            "scoring_result": result,
            "conversion_trace": [conversion.trace],
            "input_contract": _SD_EAR1_CONTRACT.as_dict(),
            "input_files": input_files.as_dict(),
            "params": {"collar": 0.0, "scorer_version": result["scorer_version"]},
        },
    )
