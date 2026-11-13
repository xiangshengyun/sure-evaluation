"""EAR-1 OpenBench configured task route descriptors."""

from __future__ import annotations

from sure_eval.evaluation.scripts.contracts import (
    call_route_executor,
    contract_from_manifest,
    describe_from_contracts,
    find_pipeline_route,
    find_task_route,
    load_task_manifest,
    load_task_routes,
    route_execution_metric,
    write_route_run_outputs,
)


def describe_pipeline(
    *, metric: str = "der", track: str | None = None, pipeline_id: str | None = None
):
    manifest, manifest_path = load_task_manifest("ear1")
    routes, routes_path = load_task_routes("ear1")
    route = _select_route(routes, metric=metric, track=track, pipeline_id=pipeline_id)
    normalized_metric = route_execution_metric(route) or metric
    contract = contract_from_manifest(manifest, route["input_contract"])
    return describe_from_contracts(
        task="EAR1",
        pipeline_id=route["pipeline_id"],
        metric=normalized_metric,
        language="n/a",
        node_ids=tuple(route["nodes"]),
        contracts=(contract,),
        task_config_path=manifest_path,
        route_config_path=routes_path,
        computation_node_ids=tuple(route.get("computation_nodes") or route["nodes"]),
        execution_metrics=(normalized_metric,),
        script_module=__name__,
        executor=str(route["executor"]),
    )


def run(
    submission: str,
    reference_dir: str,
    *,
    output_dir: str,
    metric: str = "der",
    track: str | None = None,
    pipeline_id: str | None = None,
    distance_backend: str = "builtin",
):
    if not output_dir:
        raise ValueError("output_dir is required")
    routes, _ = load_task_routes("ear1")
    route = _select_route(routes, metric=metric, track=track, pipeline_id=pipeline_id)
    resolved_track = str(route["track"])
    description = describe_pipeline(
        metric=route_execution_metric(route) or metric,
        track=resolved_track,
        pipeline_id=route["pipeline_id"],
    )
    params = dict(route.get("params") or {})
    if distance_backend:
        params["distance_backend"] = distance_backend
    report = call_route_executor(
        route,
        submission=submission,
        reference_dir=reference_dir,
        task=str(route["ear_task"]),
        track=resolved_track,
        metric=route_execution_metric(route) or metric,
        pipeline_id=route["pipeline_id"],
        **params,
    )
    return write_route_run_outputs(report=report, description=description, output_dir=output_dir)


def _select_route(routes, *, metric: str, track: str | None, pipeline_id: str | None):
    if pipeline_id:
        return find_pipeline_route(routes, pipeline_id=pipeline_id)
    normalized_metric = metric.lower().replace("-", "")
    if normalized_metric in {"cpcer", "cp_cer"}:
        normalized_metric = "cpcer"
    route = find_task_route(routes, metric=normalized_metric, track=track.upper() if track else None)
    return route
