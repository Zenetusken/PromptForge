"""Shared constants for the optimization pipeline.

Used by both the internal pipeline (``pipeline.py``) and the sampling-based
pipeline (``sampling_pipeline.py``) to ensure identical gating behavior.
"""

# Minimum analyzer confidence to trust its strategy selection.
# Below this threshold, the pipeline overrides the selected strategy to "auto".
CONFIDENCE_GATE = 0.7

# Keywords used by the semantic check to validate a task_type="coding"
# classification.  If none of these appear in the prompt, confidence is
# reduced by 0.2 before the gate check.
CODING_KEYWORDS: set[str] = {
    "function", "class", "api", "code", "program",
    "script", "endpoint", "database", "module", "import",
}


def compute_optimize_max_tokens(prompt_len: int) -> int:
    """Dynamic output budget: scale with input length, cap at 65536.

    Opus 4.6 supports 128K but ``.parse()`` needs headroom to avoid timeouts.
    """
    return min(max(16384, prompt_len // 4 * 2), 65536)
