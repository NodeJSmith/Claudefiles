"""Pricing parity tests for bin/orchestrate-cost.

The pricing table (get_pricing, turn_cost, MODEL_PRICING, DEFAULT_PRICING,
_LEGACY_OPUS_RATES) was inlined from ccrecall's token_parser.py verbatim to remove
the ccrecall PyPI dependency (design/specs/1000-ccrecall-to-cass-migration, T05).
These tests pin the inlined values against results computed from the original
ccrecall source (~/source/claude-code-recall/src/ccrecall/token_parser.py, lines
63-162) so a transcription error in the copy would be caught immediately.
"""

import runpy
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "bin" / "orchestrate-cost"

# orchestrate-cost is a PEP 723 uv-script whose only runtime dependency (`whenever`)
# is resolved by `uv run --script`, not by the ambient test environment (the fixed
# test command only adds pytest/questionary/rich). The pricing table under test here
# never touches `whenever` (it's only used by main()'s --since parsing), so a minimal
# stub stands in when the real package isn't importable. This mocks an unrelated
# external dependency at the import boundary, not the code under test.
if "whenever" not in sys.modules:
    try:
        import whenever  # noqa: F401
    except ImportError:
        stub = types.ModuleType("whenever")
        stub.Date = type("Date", (), {})
        sys.modules["whenever"] = stub


def _load_script() -> dict:
    """Execute bin/orchestrate-cost as a module namespace (runpy, no __main__ run)."""
    return runpy.run_path(str(SCRIPT))


FIXED_TOKENS = dict(
    input_tok=100_000,
    output_tok=50_000,
    cache_read=200_000,
    cache_creation=30_000,
    ephem_5m=10_000,
    ephem_1h=5_000,
)

# Expected turn_cost() results per pricing tier for FIXED_TOKENS, computed once from
# the original (pre-extraction) ccrecall pricing block.
EXPECTED_COST_BY_MODEL = {
    "claude-opus-4-0": 6.16875,  # legacy opus (4.0) -- $15/$75 tier
    "claude-opus-4-6": 2.05625,  # current opus (4.6+) -- $5/$25 tier
    "claude-sonnet-4-6": 1.23375,  # sonnet
    "claude-haiku-4-5": 0.41125,  # haiku
}

HAIKU_RATES = {
    "input": 1.0,
    "output": 5.0,
    "cache_write_5m": 1.25,
    "cache_write_1h": 2.0,
    "cache_read": 0.10,
}


def test_turn_cost_matches_ccrecall_baseline_per_tier() -> None:
    script_ns = _load_script()
    get_pricing = script_ns["get_pricing"]
    turn_cost = script_ns["turn_cost"]

    for model, expected in EXPECTED_COST_BY_MODEL.items():
        pricing = get_pricing(model)
        cost = turn_cost(**FIXED_TOKENS, pricing=pricing)
        assert cost == pytest.approx(expected), f"{model}: {cost} != {expected}"


def test_get_pricing_representative_models() -> None:
    script_ns = _load_script()
    get_pricing = script_ns["get_pricing"]
    MODEL_PRICING = script_ns["MODEL_PRICING"]
    DEFAULT_PRICING = script_ns["DEFAULT_PRICING"]
    legacy_rates = script_ns["_LEGACY_OPUS_RATES"]

    sonnet_rates = next(rates for substr, rates in MODEL_PRICING if substr == "sonnet")
    opus_current_rates = next(
        rates for substr, rates in MODEL_PRICING if substr == "opus"
    )

    assert get_pricing("claude-opus-4-0") == legacy_rates
    assert get_pricing("claude-opus-4-1") == legacy_rates
    assert get_pricing("claude-opus-4-6") == opus_current_rates
    assert get_pricing("claude-sonnet-4-6") == sonnet_rates
    assert get_pricing("claude-haiku-4-5") == HAIKU_RATES
    # Unknown model falls back to Sonnet rates (DEFAULT_PRICING).
    assert get_pricing("claude-super-model-9") == DEFAULT_PRICING == sonnet_rates
