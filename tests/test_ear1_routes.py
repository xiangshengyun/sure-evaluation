"""EAR-1 routes in the SD and SA-ASR tasks."""

import json
import zipfile
from pathlib import Path

import pytest

from sure_eval.evaluation.cli_adapters import build_pipeline_spec, run_pipeline_spec
from sure_eval.evaluation.scripts import describe_pipeline

# Synthetic organizer handoff fixtures; expected.json is the organizer scorer output.
EAR1 = Path(__file__).parent / "fixtures" / "ear1"
SD_EAR1 = "sd.any.der.conversion_sd_ear1_submission_v1.ear1_scorer_v1"
SA_ASR_EAR1 = "sa_asr.zh.cpcer.conversion_sa_asr_ear1_submission_v1.ear1_norm_v1.ear1_scorer_v1"


def _expected(example: str) -> dict:
    return json.loads((EAR1 / example / "expected.json").read_text(encoding="utf-8"))


def _run_sd(tmp_path, *, ref=None, hyp=None, sessions=None):
    pipeline = build_pipeline_spec("sd", pipeline_id=SD_EAR1)
    return run_pipeline_spec(
        pipeline,
        output_dir=str(tmp_path / "out"),
        ref_file=str(ref or EAR1 / "esd" / "reference" / "reference.rttm"),
        hyp_file=str(hyp or EAR1 / "esd" / "submission.zip"),
        sessions_file=str(sessions or EAR1 / "esd" / "reference" / "sessions.json"),
    )


def _run_sa_asr(tmp_path):
    pipeline = build_pipeline_spec("sa_asr", language="zh", metric="cpcer")
    return run_pipeline_spec(
        pipeline,
        output_dir=str(tmp_path / "out"),
        ref_file=str(EAR1 / "esr" / "reference"),
        hyp_file=str(EAR1 / "esr" / "submission.zip"),
        sessions_file=str(EAR1 / "esr" / "reference" / "sessions.json"),
    )


def _report(tmp_path) -> dict:
    return json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))


def test_default_sd_and_sa_asr_routes_are_unchanged():
    assert describe_pipeline("sd", metric="der").pipeline_id == "sd.any.der.meeteval_v1"
    assert describe_pipeline("sa_asr", language="zh", metric="cpwer").pipeline_id == (
        "sa_asr.zh.cpwer.conversion_sa_asr_cpwer_v1.gstar_norm_v1.meeteval_v1"
    )


def test_ear1_routes_describe_their_node_chain():
    sd = describe_pipeline("sd", pipeline_id=SD_EAR1)
    assert sd.computation_node_ids == ("conversion/sd__ear1_submission", "scoring/ear1_scorer")
    assert sd.conversion_steps[0]["id"] == "sd__ear1_submission"

    sa_asr = describe_pipeline("sa_asr", language="zh", metric="cpcer")
    assert sa_asr.pipeline_id == SA_ASR_EAR1
    assert sa_asr.computation_node_ids == (
        "conversion/sa_asr__ear1_submission",
        "normalization/ear1_norm",
        "scoring/ear1_scorer",
    )


def test_sd_ear1_route_matches_organizer_scorer(tmp_path):
    expected = _expected("esd")
    summary = _run_sd(tmp_path)
    report = _report(tmp_path)
    result = report["details"]["scoring_result"]

    assert summary["pipeline_id"] == SD_EAR1
    assert report["pipeline_id"] == SD_EAR1
    assert report["metric"] == "der"
    assert result == expected
    assert [item["node_id"] for item in report["pipeline_trace"]] == ["scoring/ear1_scorer"]
    assert (tmp_path / "out" / "conversion" / "sd__ear1_submission" / "hyp.seglst.json").is_file()


def test_sd_ear1_accepts_reference_directory(tmp_path):
    expected = _expected("esd")
    summary = _run_sd(tmp_path, ref=EAR1 / "esd" / "reference")
    report = _report(tmp_path)

    assert summary["pipeline_id"] == SD_EAR1
    assert report["details"]["scoring_result"] == expected


def test_sd_ear1_reference_directory_requires_reference_rttm(tmp_path):
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()

    with pytest.raises(ValueError, match="reference\\.rttm"):
        _run_sd(tmp_path, ref=reference_dir)


def test_sa_asr_ear1_route_matches_organizer_scorer(tmp_path):
    expected = _expected("esr")
    summary = _run_sa_asr(tmp_path)
    report = _report(tmp_path)
    result = report["details"]["scoring_result"]

    assert summary["pipeline_id"] == SA_ASR_EAR1
    assert report["metric"] == "cpcer"
    assert result == expected
    assert [item["node_id"] for item in report["pipeline_trace"]] == [
        "normalization/ear1_norm",
        "scoring/ear1_scorer",
    ]
    # Rows overlapping the reference "*" row and the organizer exclude interval are dropped.
    assert report["details"]["conversion_trace"][0]["excluded_rows"] == 3


def test_ear1_routes_require_sessions_file(tmp_path):
    pipeline = build_pipeline_spec("sd", pipeline_id=SD_EAR1)
    with pytest.raises(ValueError, match="sessions_file"):
        run_pipeline_spec(
            pipeline,
            output_dir=str(tmp_path / "out"),
            ref_file=str(EAR1 / "esd" / "reference" / "reference.rttm"),
            hyp_file=str(EAR1 / "esd" / "submission.zip"),
        )


def test_meeteval_route_rejects_sessions_file(tmp_path):
    from sure_eval.evaluation.scripts.sd import run

    with pytest.raises(ValueError, match="does not accept --sessions-file"):
        run(
            str(EAR1 / "esd" / "reference" / "reference.rttm"),
            str(EAR1 / "esd" / "submission" / "submission.rttm"),
            output_dir=str(tmp_path / "out"),
            sessions_file=str(EAR1 / "esd" / "reference" / "sessions.json"),
        )


def test_sd_ear1_rejects_submission_that_omits_a_session(tmp_path):
    incomplete = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(EAR1 / "esd" / "submission.zip") as src, zipfile.ZipFile(incomplete, "w") as dst:
        for name in src.namelist():
            if name != "empty_sessions.txt":
                dst.writestr(name, src.read(name))
    with pytest.raises(ValueError, match="coverage differs from the expected sessions"):
        _run_sd(tmp_path, hyp=incomplete)


@pytest.mark.parametrize("track", [None, "X", "d1"])
def test_ear1_rejects_sessions_without_a_valid_track(tmp_path, track):
    config = json.loads((EAR1 / "esd" / "reference" / "sessions.json").read_text(encoding="utf-8"))
    config.pop("track")
    if track is not None:
        config["track"] = track
    sessions = tmp_path / "sessions.json"
    sessions.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="track must be one of"):
        _run_sd(tmp_path, sessions=sessions)


def test_sd_ear1_rejects_malformed_rttm_row(tmp_path):
    malformed = tmp_path / "malformed.zip"
    with zipfile.ZipFile(malformed, "w") as dst:
        dst.writestr("submission.rttm", "SPEAKER EVAL001 1 0.0 3.0 spk01\n")
        dst.writestr("empty_sessions.txt", "EVAL002\n")
    with pytest.raises(ValueError, match="invalid RTTM row"):
        _run_sd(tmp_path, hyp=malformed)


def test_ear1_norm_drops_rows_that_normalize_to_empty(tmp_path):
    from sure_eval.evaluation.nodes.normalization.ear1_norm import normalize_ear1_seglst_files

    rows = [
        {"session_id": "S", "speaker": "a", "start_time": 0.0, "end_time": 1.0, "words": "Ｈｅｌｌｏ， 世界！"},
        {"session_id": "S", "speaker": "a", "start_time": 1.0, "end_time": 2.0, "words": "。。"},
    ]
    for name in ("ref.json", "hyp.json"):
        (tmp_path / name).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    ref, _, result = normalize_ear1_seglst_files(
        ref_file=str(tmp_path / "ref.json"), hyp_file=str(tmp_path / "hyp.json"), output_dir=tmp_path / "n"
    )
    assert [row["words"] for row in json.loads(Path(ref).read_text(encoding="utf-8"))] == ["hello世界"]
    assert result.details["segments"]["ref"] == {"input_segments": 2, "kept_segments": 1}


def test_ear1_scorer_env_check_fails_when_scipy_is_missing(monkeypatch):
    from sure_eval.evaluation import env_check
    from sure_eval.evaluation.env_check import NodeEnvChecker

    original_find_spec = env_check.importlib.util.find_spec

    def _fake_find_spec(name: str):
        if name == "scipy":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(env_check.importlib.util, "find_spec", _fake_find_spec)

    result = NodeEnvChecker().check_node("scoring/ear1_scorer")

    assert result.runtime == "pip_optional"
    assert result.status == "failed"
    assert "scipy" in result.details["missing_imports"]
    assert "pip install" in result.fix
