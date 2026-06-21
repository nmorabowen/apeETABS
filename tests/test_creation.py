"""Tests for the creation layer (ADR 0006): the imperative builder tier.

These run against the mock SapModel (no live ETABS): the real ``Define`` /
``Create`` / ``New`` composites execute unmodified against the in-memory
``PropMaterial`` / ``PropFrame`` / ``LoadPatterns`` / ``PointObj`` / ``FrameObj``
/ ``File`` collaborators. We assert that builders call the correct OAPI methods,
return the right names/handles, and guard mutation behind the lock (ADR 0005).
"""

from __future__ import annotations

import pytest

from apeETABS import FrameHandle, ModelLockedError

from .conftest import bind, make_mock


# ----------------------------------------------------------------------
# Define
# ----------------------------------------------------------------------


def test_material_calls_setmaterial_and_returns_name():
    e = bind(make_mock(locked=False))
    name = e.define.material("C30", kind="Concrete")
    assert name == "C30"
    # eMatType.Concrete == 2.
    assert e.SapModel.PropMaterial.materials == [("C30", 2)]
    # No mechanical properties given -> SetMPIsotropic not called.
    assert e.SapModel.PropMaterial.isotropic == []


def test_material_with_mechanicals_calls_setmpisotropic():
    e = bind(make_mock(locked=False))
    e.define.material("C30", kind="Concrete", E=30e6, nu=0.2, alpha=1e-5)
    assert e.SapModel.PropMaterial.isotropic == [("C30", 30e6, 0.2, 1e-5)]


def test_material_E_without_nu_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(ValueError, match="nu is required"):
        e.define.material("C30", E=30e6)


def test_material_unknown_kind_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(Exception, match="Unknown material kind"):
        e.define.material("X", kind="Unobtainium")


def test_material_from_catalog_calls_addmaterial_and_returns_name():
    e = bind(make_mock(locked=False))
    name = e.define.material_from_catalog(
        kind="Rebar",
        region="United States",
        standard="ASTM A615",
        grade="Grade 60",
    )
    # No UserName given -> ETABS-assigned name; the mock falls back to grade.
    assert name == "Grade 60"
    call = e.SapModel.PropMaterial.catalog[-1]
    # eMatType.Rebar == 6.
    assert call["type"] == 6
    assert call["region"] == "United States"
    assert call["standard"] == "ASTM A615"
    assert call["grade"] == "Grade 60"
    assert call["user"] == ""


def test_material_from_catalog_honors_requested_name():
    e = bind(make_mock(locked=False))
    name = e.define.material_from_catalog(
        region="United States",
        standard="ACI 318",
        grade="4000Psi",
        name="MyConc",
    )
    assert name == "MyConc"
    call = e.SapModel.PropMaterial.catalog[-1]
    # eMatType.Concrete == 2 (default kind).
    assert call["type"] == 2
    assert call["user"] == "MyConc"


def test_frame_rect_calls_setrectangle_and_returns_name():
    e = bind(make_mock(locked=False))
    name = e.define.frame_rect("R1", material="C30", depth=0.6, width=0.3)
    assert name == "R1"
    # SetRectangle(Name, MatProp, T3=depth, T2=width).
    assert e.SapModel.PropFrame.rectangles == [("R1", "C30", 0.6, 0.3)]


def test_load_pattern_calls_add_and_returns_name():
    e = bind(make_mock(locked=False))
    name = e.define.load_pattern("DEAD", kind="Dead", self_wt=1.0)
    assert name == "DEAD"
    # eLoadPatternType.Dead == 1; default add=True.
    assert e.SapModel.LoadPatterns.added == [("DEAD", 1, 1.0, True)]


def test_load_pattern_defaults_to_other():
    e = bind(make_mock(locked=False))
    e.define.load_pattern("L1")
    # eLoadPatternType.Other == 8; defaults self_wt=0.0, add=True.
    assert e.SapModel.LoadPatterns.added == [("L1", 8, 0.0, True)]


def test_load_pattern_unknown_kind_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(Exception, match="Unknown load pattern kind"):
        e.define.load_pattern("L1", kind="Bogus")


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------


def test_point_returns_assigned_name():
    e = bind(make_mock(locked=False))
    name = e.create.point(1.0, 2.0, 3.0)
    assert name == "P1"
    assert e.SapModel.PointObj.added[-1]["xyz"] == (1.0, 2.0, 3.0)


def test_point_honors_requested_name():
    e = bind(make_mock(locked=False))
    assert e.create.point(0, 0, 0, name="Origin") == "Origin"


def test_frame_by_coord_returns_handle_with_ij_from_getpoints():
    e = bind(make_mock(locked=False))
    h = e.create.frame_by_coord((0, 0, 0), (0, 0, 3), section="R1", name="C1")
    assert isinstance(h, FrameHandle)
    assert h.name == "C1"
    # I/J come from GetPoints (the mock simulates ETABS reordering by naming
    # the end points off the frame name) — NOT from the input coordinate order.
    assert h.i == "~C1-I"
    assert h.j == "~C1-J"
    # The section property was forwarded to AddByCoord.
    assert e.SapModel.FrameObj.added[-1]["prop"] == "R1"


# ----------------------------------------------------------------------
# Lock guard (ADR 0005 §2) — mutating creates/defines must refuse on a
# locked model.
# ----------------------------------------------------------------------


def test_define_material_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.define.material("C30")


def test_define_material_from_catalog_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.define.material_from_catalog(
            region="United States", standard="ACI 318", grade="4000Psi"
        )


def test_define_frame_rect_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.define.frame_rect("R1", material="C30", depth=0.6, width=0.3)


def test_define_load_pattern_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.define.load_pattern("L1")


def test_create_point_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.create.point(0, 0, 0)


def test_create_frame_raises_when_locked():
    e = bind(make_mock(locked=True))
    with pytest.raises(ModelLockedError, match="unlock"):
        e.create.frame_by_coord((0, 0, 0), (0, 0, 3))


# ----------------------------------------------------------------------
# New templates
# ----------------------------------------------------------------------


def test_new_blank_resets_model():
    e = bind(make_mock(locked=False))
    result = e.new.blank()
    assert result is e  # returns the session for chaining
    assert e.SapModel.File.new_calls == [("blank", ())]


def test_new_blank_sets_units_when_given():
    e = bind(make_mock(units=(2, 1, 1)))  # kip, inch, F
    e.new.blank(units=("kN", "m"))
    # eForce.kN == 4, eLength.m == 6; temperature left at current (1 = F).
    assert e.SapModel._units == [4, 6, 1]


def test_new_grid_only_forwards_template_args():
    e = bind(make_mock(locked=False))
    e.new.grid_only(stories=3, story_height=3.5, lines_x=4, spacing_x=5.0)
    kind, args = e.SapModel.File.new_calls[-1]
    assert kind == "grid_only"
    # (NumberStorys, TypicalStoryHeight, BottomStoryHeight, NumberLinesX,
    #  NumberLinesY, SpacingX, SpacingY)
    assert args == (3, 3.5, 3.0, 4, 2, 5.0, 6.0)


def test_new_steel_deck_forwards_template_args():
    e = bind(make_mock(locked=False))
    e.new.steel_deck(stories=2)
    kind, args = e.SapModel.File.new_calls[-1]
    assert kind == "steel_deck"
    assert args[0] == 2


# ----------------------------------------------------------------------
# Documented stubs (ADR 0006 §2) — must raise NotImplementedError until built.
# ----------------------------------------------------------------------


def test_define_section_stub_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError, match="Define.section"):
        e.define.section()


def test_define_combo_stub_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError, match="Define.combo"):
        e.define.combo()


def test_define_diaphragm_stub_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError, match="Define.diaphragm"):
        e.define.diaphragm()


def test_create_area_stub_raises():
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError, match="Create.area"):
        e.create.area()


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------


def test_creation_composites_are_wired():
    e = bind(make_mock())
    assert e.define is not None
    assert e.create is not None
    assert e.new is not None
