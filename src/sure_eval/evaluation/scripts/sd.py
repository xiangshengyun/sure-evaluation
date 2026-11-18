"""SD configured script route descriptors."""

from __future__ import annotations

from pathlib import Path

from sure_eval.evaluation.scripts.contracts import (
    call_route_executor,
    contract_from_manifest,
    conversion_description,
    describe_from_contracts,
    find_pipeline_route,
    find_task_route,
    load_task_manifest,
    load_task_routes,
    route_execution_metric,
    write_route_run_outputs,
)


def describe_pipeline(*, metric: str = "der", pipeline_id: str | None = None):
    manifest, manifest_path, routes_path, route, normalized_metric = _select_route(
        metric=metric, pipeline_id=pipeline_id
    )
    conversions = _route_conversions(route)
    return describe_from_contracts(
        task="SD",
        pipeline_id=route["pipeline_id"],
        metric=normalized_metric,
        language="n/a",
        node_ids=tuple(route["nodes"]),
        contracts=(contract_from_manifest(manifest, route["input_contract"]),),
        task_config_path=manifest_path,
        route_config_path=routes_path,
        conversion_steps=tuple(conversion_description(conversion_id) for conversion_id in conversions),
        computation_node_ids=(
            *(f"conversion/{conversion_id}" for conversion_id in conversions),
            *tuple(route["nodes"]),
        ),
        execution_metrics=(normalized_metric,),
        script_module=__name__,
        executor=str(route.get("executor") or ""),
    )


def run(
    ref_file: str,
    hyp_file: str,
    *,
    output_dir: str,
    metric: str = "der",
    pipeline_id: str | None = None,
    collar: float | None = None,
    sessions_file: str | None = None,
):
    if not output_dir:
        raise ValueError("output_dir is required")
    description = describe_pipeline(metric=metric, pipeline_id=pipeline_id)
    manifest, _, _, route, normalized_metric = _select_route(metric=metric, pipeline_id=pipeline_id)
    params = dict(route.get("params") or {})
    if collar is not None:
        params["collar"] = collar
    params.update(_route_inputs(manifest, route, output_dir=output_dir, sessions_file=sessions_file))
    report = call_route_executor(
        route,
        ref_file=ref_file,
        hyp_file=hyp_file,
        metric=normalized_metric,
        **params,
    )
    return write_route_run_outputs(report=report, description=description, output_dir=output_dir)


def _select_route(*, metric: str = "der", pipeline_id: str | None = None):
    manifest, manifest_path = load_task_manifest("sd")
    normalized_metric = metric.lower()
    routes, routes_path = load_task_routes("sd")
    if pipeline_id:
        route = find_pipeline_route(routes, pipeline_id=pipeline_id)
    else:
        route = find_task_route(routes, metric=normalized_metric)
    return manifest, manifest_path, routes_path, route, route_execution_metric(route) or normalized_metric


def _route_conversions(route: dict) -> tuple[str, ...]:
    return tuple(str(item) for item in route.get("conversions") or ())


def _route_inputs(manifest: dict, route: dict, *, output_dir: str, sessions_file: str | None) -> dict:
    roles = contract_from_manifest(manifest, route["input_contract"]).get("required_roles") or ()
    inputs: dict = {}
    if "sessions" in roles:
        if not sessions_file:
            raise ValueError(f"Route {route['pipeline_id']} requires --sessions-file")
        inputs["sessions_file"] = sessions_file
    elif sessions_file:
        raise ValueError(f"Route {route['pipeline_id']} does not accept --sessions-file")
    for conversion_id in _route_conversions(route):
        inputs["conversion_output_dir"] = str(Path(output_dir) / "conversion" / conversion_id)
    return inputs
