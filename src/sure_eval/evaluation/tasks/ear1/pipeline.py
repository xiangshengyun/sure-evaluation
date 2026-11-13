"""EAR-1 ESD-ON/ESR-ON scoring pipeline."""

from __future__ import annotations

from pathlib import Path

from sure_eval.evaluation.core.types import EvaluationFiles, EvaluationReport, MetricInputContract, PipelineNodeResult
from sure_eval.evaluation.nodes.scoring.ear1_openbench.scorer import score

NODE_ID = "scoring/ear1_openbench"
NODE_VERSION = "v1"

_CONTRACTS = {
    "ESD-ON": MetricInputContract(
        metric_id=NODE_ID,
        required_roles=("submission", "reference_dir"),
        row_format="EAR-1 submission ZIP + organizer reference directory",
        alignment_key="session_id",
        aggregation="pooled_error_seconds_over_reference_speaker_seconds",
        purpose="EAR-1 speaker diarization DER",
    ),
    "ESR-ON": MetricInputContract(
        metric_id=NODE_ID,
        required_roles=("submission", "reference_dir"),
        row_format="EAR-1 submission ZIP + organizer reference directory",
        alignment_key="session_id",
        aggregation="pooled_character_errors_over_reference_characters",
        purpose="EAR-1 speaker-attributed recognition cpCER",
    ),
}


def evaluate_ear1_files(
    submission: str,
    reference_dir: str,
    *,
    task: str,
    track: str,
    metric: str,
    pipeline_id: str,
    distance_backend: str = "builtin",
) -> EvaluationReport:
    task = task.upper()
    track = track.upper()
    if task not in _CONTRACTS:
        raise ValueError(f"Unsupported EAR-1 task: {task}")
    expected_metric = "DER" if task == "ESD-ON" else "CPCER"
    normalized_metric = metric.lower().replace("-", "").replace("_", "")
    if normalized_metric != expected_metric.lower():
        raise ValueError(f"{task} requires metric {expected_metric.lower()}")
    if not Path(submission).is_file():
        raise ValueError(f"EAR-1 submission ZIP does not exist: {submission}")
    if not Path(reference_dir).is_dir():
        raise ValueError(f"EAR-1 reference directory does not exist: {reference_dir}")
    result = score(
        task,
        track,
        Path(submission),
        Path(reference_dir),
        distance_backend=distance_backend,
    )
    contract = _CONTRACTS[task]
    input_files = EvaluationFiles(
        roles={"submission": submission, "reference_dir": reference_dir}
    )
    node_result = PipelineNodeResult(
        stage="scoring",
        node_id=NODE_ID,
        version=NODE_VERSION,
        details={
            "backend": "ear1_openbench",
            "scorer_version": result["scorer_version"],
            "task": task,
            "track": track,
            "metric": result["metric"],
            "distance_backend": distance_backend,
            "result": result,
        },
        internal_stages=("submission_validation", "reference_validation", "metric_scoring", "pooled_aggregation"),
    )
    return EvaluationReport(
        task="EAR1",
        language="n/a",
        metric=result["metric"].lower(),
        score=float(result["score"]),
        pipeline_id=pipeline_id,
        pipeline_trace=(node_result,),
        input_contract=contract,
        input_files=input_files,
        computation_node_ids=(NODE_ID,),
        details={
            "scoring_result": result,
            "input_contract": contract.as_dict(),
            "input_files": input_files.as_dict(),
            "params": {"task": task, "track": track, "distance_backend": distance_backend},
        },
    )
