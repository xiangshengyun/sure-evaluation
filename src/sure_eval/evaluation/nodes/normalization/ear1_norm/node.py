"""EAR-1 text normalization for character-level cpCER."""

from __future__ import annotations

import json
from pathlib import Path

from sure_eval.evaluation.core.types import PipelineNodeResult
from sure_eval.evaluation.nodes.scoring.ear1_scorer.metrics import normalize_text

NODE_ID = "normalization/ear1_norm"
NODE_VERSION = "v1"


def normalize_ear1_seglst_files(
    *, ref_file: str, hyp_file: str, output_dir: str | Path
) -> tuple[str, str, PipelineNodeResult]:
    """Normalize SegLST ``words`` and drop rows whose text becomes empty."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths, counts = [], {}
    for role, source in (("ref", ref_file), ("hyp", hyp_file)):
        segments = json.loads(Path(source).read_text(encoding="utf-8"))
        kept = []
        for segment in segments:
            text = normalize_text(segment["words"])
            if text:
                kept.append({**segment, "words": text})
        target = out / f"{role}.normalized.seglst.json"
        target.write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        paths.append(str(target))
        counts[role] = {"input_segments": len(segments), "kept_segments": len(kept)}
    result = PipelineNodeResult(
        stage="normalization",
        node_id=NODE_ID,
        version=NODE_VERSION,
        details={"rule": "nfkc_lower_remove_whitespace_and_unicode_punctuation", "segments": counts},
        internal_stages=("seglst_parse", "ear1_text_normalize"),
    )
    return paths[0], paths[1], result
