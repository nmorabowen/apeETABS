"""Tests for the editing layer (ADR 0005): lock cycle + edit/assign skeletons.

These run against the mock SapModel (no live ETABS): the real ``Edit`` /
``Assign`` composites and the session lock guard execute unmodified against
the in-memory ``FrameObj`` / ``PointObj`` / ``AreaObj`` collaborators.
"""

from __future__ import annotations

import warnings

import pytest

from apeETABS import ModelLockedError
from apeETABS.editing._target import _Target

from .conftest import bind, make_mock


# ----------------------------------------------------------------------
# Lock cycle
# ----------------------------------------------------------------------


def test_is_locked_reflects_model_state():
    assert bind(make_mock(locked=False)).is_locked is False
    assert bind(make_mock(locked=True)).is_locked is True


def test_lock_sets_state():
    e = bind(make_mock(locked=False))
    e.lock()
    assert e.is_locked is True
    assert e.SapModel._locked is True


def test_unlock_flips_state_and_warns():
    e = bind(make_mock(locked=True))
    with pytest.warns(UserWarning, match="DISCARDS all analysis results"):
        e.unlock()
    assert e.is_locked is False
    assert e.SapModel._locked is False


def test_require_unlocked_passes_when_unlocked():
    e = bind(make_mock(locked=False))
    # Should not raise.
    e._require_unlocked("test op")


def test_require_unlocked_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e._require_unlocked("rename frame 'B1'")


# ----------------------------------------------------------------------
# Lock guard on mutating composite methods
# ----------------------------------------------------------------------


def test_edit_rename_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError):
        e.edit.rename("B1", "B2")
    assert e.SapModel.FrameObj.renamed == []  # no COM call leaked through


def test_edit_delete_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError):
        e.edit.delete("B1")


def test_assign_restraint_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError):
        e.assign.restraint("N1", [True] * 6)
    assert e.SapModel.PointObj.restraints == []


# ----------------------------------------------------------------------
# Edit: rename / delete call the right mock collaborator
# ----------------------------------------------------------------------


def test_rename_frame_calls_changename_and_returns_new():
    e = bind(make_mock(locked=False))
    new = e.edit.rename("B1", "B2")
    assert new == "B2"
    assert e.SapModel.FrameObj.renamed == [("B1", "B2")]


def test_rename_point_uses_pointobj():
    e = bind(make_mock(locked=False))
    e.edit.rename("N1", "N2", kind="point")
    assert e.SapModel.PointObj.renamed == [("N1", "N2")]
    assert e.SapModel.FrameObj.renamed == []


def test_rename_area_uses_areaobj():
    e = bind(make_mock(locked=False))
    e.edit.rename("A1", "A2", kind="area")
    assert e.SapModel.AreaObj.renamed == [("A1", "A2")]


def test_delete_calls_delete_with_objects_itemtype():
    e = bind(make_mock(locked=False))
    e.edit.delete("B1")
    assert e.SapModel.FrameObj.deleted == [("B1", 0)]  # eItemType.Objects


def test_unknown_kind_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(ValueError, match="Unknown object kind"):
        e.edit.rename("X1", "X2", kind="cable")


@pytest.mark.parametrize("meth", ["move", "divide", "replicate"])
def test_edit_stubs_not_implemented(meth):
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError):
        getattr(e.edit, meth)()


# ----------------------------------------------------------------------
# Assign: restraint calls SetRestraint
# ----------------------------------------------------------------------


def test_restraint_calls_setrestraint_objects():
    e = bind(make_mock(locked=False))
    e.assign.restraint("N1", [True, True, True, False, False, False])
    assert e.SapModel.PointObj.restraints == [
        ("N1", [True, True, True, False, False, False], 0)
    ]


def test_restraint_group_uses_group_itemtype():
    e = bind(make_mock(locked=False))
    e.assign.restraint(group="Supports", dofs=[True] * 6)
    name, vals, item_type = e.SapModel.PointObj.restraints[0]
    assert name == "Supports"
    assert item_type == 1  # eItemType.Group


def test_restraint_requires_dofs():
    e = bind(make_mock(locked=False))
    with pytest.raises(ValueError, match="requires dofs"):
        e.assign.restraint("N1")


def test_restraint_rejects_wrong_dof_count():
    e = bind(make_mock(locked=False))
    with pytest.raises(ValueError, match="6 entries"):
        e.assign.restraint("N1", [True, True, True])


@pytest.mark.parametrize("meth", ["modifiers", "releases"])
def test_assign_stubs_not_implemented(meth):
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError):
        getattr(e.assign, meth)()


# ----------------------------------------------------------------------
# Loadings (ADR 0008 assign primitives) — point/frame/area load setters.
# ----------------------------------------------------------------------


def test_point_force_records_six_components():
    e = bind(make_mock(locked=False))
    e.assign.point_force("N1", pattern="Dead", fz=-10.0, mx=2.0)
    rec = e.SapModel.PointObj.forces
    assert len(rec) == 1
    assert rec[0]["name"] == "N1" and rec[0]["pat"] == "Dead"
    assert rec[0]["value"] == [0.0, 0.0, -10.0, 2.0, 0.0, 0.0]
    assert rec[0]["item_type"] == 0  # Objects


def test_area_uniform_default_direction_is_gravity():
    e = bind(make_mock(locked=False))
    e.assign.area_uniform("A1", pattern="Live", value=2.5)
    rec = e.SapModel.AreaObj.uniform_loads[0]
    assert rec["name"] == "A1" and rec["value"] == 2.5
    assert rec["dir"] == 10  # Gravity


def test_area_uniform_named_direction_maps_to_code():
    e = bind(make_mock(locked=False))
    e.assign.area_uniform("A1", pattern="W", value=1.0, direction="X")
    assert e.SapModel.AreaObj.uniform_loads[0]["dir"] == 4  # X


def test_frame_distributed_uniform_defaults_vals_to_value():
    e = bind(make_mock(locked=False))
    e.assign.frame_distributed("B1", pattern="Dead", value=-5.0)
    rec = e.SapModel.FrameObj.dist_loads[0]
    assert rec["name"] == "B1" and rec["type"] == 1  # force
    assert rec["dir"] == 10  # Gravity
    assert rec["v1"] == -5.0 and rec["v2"] == -5.0  # uniform
    assert rec["d1"] == 0.0 and rec["d2"] == 1.0 and rec["rel"] is True


def test_frame_distributed_trapezoidal_and_moment_kind():
    e = bind(make_mock(locked=False))
    e.assign.frame_distributed(
        "B1", pattern="Dead", value=0.0, val_start=1.0, val_end=3.0, kind="moment"
    )
    rec = e.SapModel.FrameObj.dist_loads[0]
    assert rec["type"] == 2  # moment
    assert rec["v1"] == 1.0 and rec["v2"] == 3.0


def test_load_unknown_direction_raises():
    from apeETABS.errors import ETABSError
    e = bind(make_mock(locked=False))
    with pytest.raises(ETABSError, match="Unknown direction"):
        e.assign.area_uniform("A1", pattern="Dead", value=1.0, direction="Bogus")


def test_frame_distributed_unknown_kind_raises():
    from apeETABS.errors import ETABSError
    e = bind(make_mock(locked=False))
    with pytest.raises(ETABSError, match="Unknown load kind"):
        e.assign.frame_distributed("B1", pattern="Dead", value=1.0, kind="bogus")


@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.point_force("N1", pattern="Dead", fz=-1.0),
        lambda a: a.frame_distributed("B1", pattern="Dead", value=-1.0),
        lambda a: a.area_uniform("A1", pattern="Dead", value=-1.0),
    ],
)
def test_load_setters_raise_when_locked(call):
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        call(e.assign)


# ----------------------------------------------------------------------
# _Target resolution
# ----------------------------------------------------------------------


def test_target_name_maps_to_objects():
    t = _Target.resolve("B12")
    assert (t.name, t.item_type) == ("B12", 0)


def test_target_group_maps_to_group():
    t = _Target.resolve(group="Beams")
    assert (t.name, t.item_type) == ("Beams", 1)


def test_target_selected_maps_to_selectedobjects():
    t = _Target.resolve(selected=True)
    assert (t.name, t.item_type) == ("", 2)


def test_target_ambiguous_raises():
    with pytest.raises(ValueError, match="exactly one"):
        _Target.resolve("B12", group="Beams")


def test_target_none_raises():
    with pytest.raises(ValueError, match="exactly one"):
        _Target.resolve()


# ----------------------------------------------------------------------
# Full unlock -> edit happy path
# ----------------------------------------------------------------------


def test_unlock_then_edit():
    e = bind(make_mock(locked=True))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        e.unlock()
    e.edit.rename("B1", "B2")
    assert e.SapModel.FrameObj.renamed == [("B1", "B2")]
