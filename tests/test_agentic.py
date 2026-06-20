"""Tests for the agentic scaffolding (P8 / ADR 0007).

Covers the scaffold's contract, not full coverage: structured outcome/finding
serialization, the policy risk-tier gate (edit blocked when ``allow_edit``
False; destructive never auto), the pipeline (stops-after-plan on a gated tier,
auto-runs on the read tier), and ``ReportSpec.validate`` flagging a missing case
via a structured :class:`Finding`. All run against the mock SapModel — no live
ETABS. Matplotlib's Agg backend is forced so ``run`` can render headlessly.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless; must precede any pyplot import via plotting

import json  # noqa: E402

import pytest  # noqa: E402

from apeETABS.agentic import (  # noqa: E402
    AgentPolicy,
    EditSpec,
    Finding,
    Outcome,
    ReportSpec,
    UnknownTierError,
    run_spec,
)

from .conftest import bind, make_mock  # noqa: E402


# ----------------------------------------------------------------------
# Outcome / Finding serialization (ADR 0007 §4)
# ----------------------------------------------------------------------


def test_finding_to_dict_round_trips_through_json():
    f = Finding(code="UNKNOWN_CASE", message="no such case", hint="check names")
    d = f.to_dict()
    assert d == {
        "code": "UNKNOWN_CASE",
        "message": "no such case",
        "hint": "check names",
        "severity": "error",
    }
    # Machine-readable: survives a JSON round-trip.
    assert json.loads(json.dumps(d)) == d


def test_outcome_to_dict_serializes_findings_and_is_json_safe():
    out = Outcome(
        ok=False,
        operations=["render drift"],
        findings=[Finding(code="X", message="m", severity="warning")],
        data={"k": 1},
    )
    d = out.to_dict()
    assert d["ok"] is False
    assert d["operations"] == ["render drift"]
    assert d["findings"][0]["code"] == "X"
    assert d["data"] == {"k": 1}
    json.dumps(d)  # must not raise


def test_outcome_errors_property_filters_to_error_severity():
    out = Outcome(
        ok=False,
        findings=[
            Finding(code="E", message="bad", severity="error"),
            Finding(code="W", message="meh", severity="warning"),
        ],
    )
    assert [f.code for f in out.errors] == ["E"]


# ----------------------------------------------------------------------
# AgentPolicy gating (ADR 0007 §3)
# ----------------------------------------------------------------------


def test_read_and_create_tiers_auto_run():
    p = AgentPolicy()
    assert p.gate("read") is True
    assert p.gate("create") is True


def test_edit_tier_blocked_when_allow_edit_false():
    assert AgentPolicy(allow_edit=False).gate("edit") is False


def test_edit_tier_auto_only_when_allowed_and_no_approval_required():
    assert AgentPolicy(allow_edit=True, require_approval=False).gate("edit") is True
    # allow_edit but approval still required -> gated.
    assert AgentPolicy(allow_edit=True, require_approval=True).gate("edit") is False


def test_destructive_tier_never_auto_regardless_of_policy():
    permissive = AgentPolicy(allow_edit=True, require_approval=False)
    assert permissive.gate("destructive") is False


def test_unknown_tier_raises():
    with pytest.raises(UnknownTierError):
        AgentPolicy().gate("nonsense")


# ----------------------------------------------------------------------
# Pipeline (ADR 0007 §2)
# ----------------------------------------------------------------------


def test_pipeline_runs_read_tier_report_and_records_plan():
    e = bind(make_mock())
    spec = ReportSpec(figures=[{"kind": "drift", "case": "EQX", "direction": "X"}])
    out = run_spec(spec, e, policy=AgentPolicy())
    assert out.ok is True
    assert out.data["stage"] == "run"
    assert out.data["figures_rendered"] == 1
    # The plan is folded into the run record.
    assert out.data["plan"]


def test_pipeline_stops_after_plan_on_gated_edit_tier_without_approval():
    e = bind(make_mock())
    # _StubEdit is an edit-tier spec with trivial succeeding validate/plan, so
    # the gate is the only thing that can stop the pipeline. It must stop after
    # plan (run() never reached -> spec.ran stays False).
    spec = _StubEdit()
    out = run_spec(spec, e, policy=AgentPolicy(allow_edit=False))
    assert out.ok is False
    assert out.data["stage"] == "plan"
    assert out.data["gated"] is True
    assert [f.code for f in out.findings] == ["APPROVAL_REQUIRED"]
    assert spec.ran is False  # run() was never called.


def test_pipeline_runs_gated_tier_when_approve_callback_grants():
    e = bind(make_mock())
    spec = _StubEdit()
    out = run_spec(
        spec, e, policy=AgentPolicy(allow_edit=False), approve=lambda s, plan: True
    )
    assert out.ok is True
    assert spec.ran is True
    assert out.data["stage"] == "run"


def test_pipeline_short_circuits_on_validate_failure():
    e = bind(make_mock())
    # A figure referencing a case the model does not have.
    spec = ReportSpec(figures=[{"kind": "drift", "case": "NOPE"}])
    out = run_spec(spec, e, policy=AgentPolicy())
    assert out.ok is False
    assert out.data["stage"] == "validate"
    assert any(f.code == "UNKNOWN_CASE" for f in out.findings)


# ----------------------------------------------------------------------
# ReportSpec.validate flags a missing case via a structured Finding
# ----------------------------------------------------------------------


def test_report_validate_flags_missing_case_structured():
    e = bind(make_mock())
    spec = ReportSpec(figures=[{"kind": "drift", "case": "MISSING"}])
    out = spec.validate(e)
    assert out.ok is False
    miss = next(f for f in out.findings if f.code == "UNKNOWN_CASE")
    assert "MISSING" in miss.message
    assert "EQX" in miss.hint  # the available cases are surfaced as remediation.


def test_report_validate_passes_for_present_case():
    e = bind(make_mock())
    spec = ReportSpec(figures=[{"kind": "drift", "case": "EQX", "direction": "X"}])
    assert spec.validate(e).ok is True


def test_report_spec_round_trips_through_dict():
    spec = ReportSpec(
        figures=[{"kind": "drift", "case": "EQX"}], source="tower.edb", units=("kN", "m")
    )
    rebuilt = ReportSpec.from_dict(spec.to_dict())
    assert rebuilt.figures == spec.figures
    assert rebuilt.source == "tower.edb"
    assert rebuilt.units == ("kN", "m")


# ----------------------------------------------------------------------
# Edit-tier skeleton is documented-stubbed
# ----------------------------------------------------------------------


def test_edit_spec_verbs_are_stubbed():
    e = bind(make_mock())
    with pytest.raises(NotImplementedError):
        EditSpec().validate(e)


# ----------------------------------------------------------------------
# A minimal edit-tier spec with trivial validate/plan, to isolate the GATE
# from the (stubbed) real EditSpec verbs.
# ----------------------------------------------------------------------


class _StubEdit(EditSpec):
    """Edit-tier spec whose validate/plan succeed, so we can test the gate."""

    def __init__(self) -> None:
        super().__init__()
        self.ran = False

    def validate(self, e) -> Outcome:  # type: ignore[override]
        return Outcome(ok=True)

    def plan(self, e) -> Outcome:  # type: ignore[override]
        return Outcome(ok=True, operations=["rename C1 -> C2"])

    def run(self, e, *, policy) -> Outcome:  # type: ignore[override]
        self.ran = True
        return Outcome(ok=True, operations=["renamed C1 -> C2"])
