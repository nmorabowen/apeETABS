"""Unit tests for the dependency-free cross-check comparator (ADR 0009)."""

from __future__ import annotations

from apeETABS.crosscheck import REACTION_DOFS, compare


def _disp(**joints):
    return {k: tuple(v) for k, v in joints.items()}


def test_identical_passes():
    ref = _disp(a=(1, 2, 3, 0, 0, 0), b=(4, 5, 6, 0, 0, 0))
    rep = compare(ref, dict(ref), quantity="displacements")
    assert rep.passed
    assert rep.n_compared == 2
    assert all(e.max_abs == 0.0 for e in rep.errors)


def test_within_rtol_passes_beyond_fails():
    ref = _disp(a=(100.0, 0, 0, 0, 0, 0))
    near = _disp(a=(101.0, 0, 0, 0, 0, 0))   # 1% off
    far = _disp(a=(110.0, 0, 0, 0, 0, 0))    # 10% off
    assert compare(ref, near, rtol=0.02).passed
    bad = compare(ref, far, rtol=0.02)
    assert not bad.passed
    ux = bad.errors[0]
    assert ux.dof == "Ux"
    assert ux.n_fail == 1
    assert ux.worst_joint == "a"
    assert abs(ux.max_rel - 0.1) < 1e-9


def test_small_absolute_diff_passes_despite_large_relative():
    # Reference ~0: relative error is undefined, atol governs.
    ref = _disp(a=(0.0, 0, 0, 0, 0, 0))
    cand = _disp(a=(1e-10, 0, 0, 0, 0, 0))
    assert compare(ref, cand, atol=1e-9).passed
    # A real value against a zero reference must fail (infinite relative error).
    assert not compare(ref, _disp(a=(5.0, 0, 0, 0, 0, 0)), atol=1e-9).passed


def test_missing_joint_fails_and_is_reported():
    ref = _disp(a=(1, 0, 0, 0, 0, 0), b=(2, 0, 0, 0, 0, 0))
    cand = _disp(a=(1, 0, 0, 0, 0, 0))           # b not solved
    rep = compare(ref, cand)
    assert not rep.passed
    assert rep.missing == ["b"]
    assert rep.n_compared == 1


def test_extra_joint_reported_not_fatal():
    ref = _disp(a=(1, 0, 0, 0, 0, 0))
    cand = _disp(a=(1, 0, 0, 0, 0, 0), z=(9, 0, 0, 0, 0, 0))
    rep = compare(ref, cand)
    assert rep.passed                 # extra candidate joints don't fail it
    assert rep.extra == ["z"]


def test_reaction_dof_labels_and_str():
    ref = {"1": (10.0, 0, 0, 0, 0, 0)}
    rep = compare(ref, {"1": (10.5, 0, 0, 0, 0, 0)},
                  dof_labels=REACTION_DOFS, rtol=0.1, quantity="reactions")
    assert rep.errors[0].dof == "Fx"
    assert "reactions: PASS" in str(rep)
