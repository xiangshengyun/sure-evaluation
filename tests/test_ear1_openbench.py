import json
from pathlib import Path

import pytest

from sure_eval.evaluation.cli_adapters import build_pipeline_spec, run_pipeline_spec
from sure_eval.evaluation.nodes.scoring.ear1_openbench.scorer import score


EAR1 = Path("/Users/xs/Downloads/ear1_openbench_scoring/examples")
pytestmark = pytest.mark.skipif(not EAR1.is_dir(), reason="EAR-1 handoff fixtures are not installed")


def test_ear1_fixture_scores_match_openbench_contract():
    expected = json.loads((EAR1 / "esd" / "expected.json").read_text())
    result = score(
        expected["task"],
        expected["track"],
        EAR1 / "esd" / "submission.zip",
        EAR1 / "esd" / "reference",
    )
    assert result["score"] == expected["score"]
    assert result["counts"] == expected["counts"]

    expected = json.loads((EAR1 / "esr" / "expected.json").read_text())
    result = score(
        expected["task"],
        expected["track"],
        EAR1 / "esr" / "submission.zip",
        EAR1 / "esr" / "reference",
    )
    assert result["score"] == expected["score"]
    assert result["counts"] == expected["counts"]


def test_ear1_describe_and_run_report(tmp_path):
    pipeline = build_pipeline_spec(
        "ear1", metric="der", track="D1", output_path=tmp_path / "pipeline.json"
    )
    assert pipeline["pipeline_id"] == "ear1.esd.d1.der.ear1_openbench_v1"
    result = run_pipeline_spec(
        pipeline,
        output_dir=str(tmp_path / "out"),
        submission=str(EAR1 / "esd" / "submission.zip"),
        reference_dir=str(EAR1 / "esd" / "reference"),
    )
    assert result["score"] == 0.5
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["details"]["scoring_result"]["score_pct"] == 50.0
    assert report["input_files"]["submission"].endswith("submission.zip")
