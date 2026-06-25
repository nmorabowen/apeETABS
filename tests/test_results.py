"""Unit tests for the results layer (ADR 0003) against the mock SapModel.

The ``Results`` composite is not yet wired into ``_COMPOSITES`` (a later stage
does that), so these tests construct it directly on a bound session. All data
is deterministic in-memory; assertions are on the detached snapshots.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apeETABS.errors import ETABSError
from apeETABS.results import (
    Displacements,
    Profile,
    Reactions,
    Results,
    StoryDrifts,
    StoryForces,
    WallForces,
)

from .conftest import bind, make_mock

# Present units in the default mock are kN, m, C -> length factor for the
# default baseUnits system (N-mm-tonne-s) makes meters -> mm (x1000).
# We avoid asserting on the absolute factor; instead we assert internal
# consistency (Elevation and Ux share the same length factor).


# ----------------------------------------------------------------------
# Fixture tables
# ----------------------------------------------------------------------

def _drift_tables() -> dict:
    """Multi-direction, multi-step Story Drifts + two cases for selection."""
    return {
        "Story Drifts": (
            ["Story", "OutputCase", "StepType", "Direction", "Drift"],
            [
                ["Story3", "EQX", "Max", "X", "0.0012"],
                ["Story3", "EQX", "Min", "X", "-0.0020"],
                ["Story2", "EQX", "Max", "X", "0.0018"],
                ["Story2", "EQX", "Min", "X", "-0.0009"],
                ["Story1", "EQX", "Max", "X", "0.0009"],
                ["Story1", "EQX", "Min", "X", "-0.0004"],
                ["Story3", "EQX", "Max", "Y", "0.0005"],
                ["Story2", "EQX", "Max", "Y", "0.0006"],
                ["Story1", "EQX", "Max", "Y", "0.0003"],
                ["Story3", "EQY", "Max", "X", "0.0001"],
                ["Story2", "EQY", "Max", "X", "0.0002"],
                ["Story1", "EQY", "Max", "X", "0.0001"],
            ],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }


def _displacement_tables() -> dict:
    """Joint Displacements with multi-step rows and one joint per story."""
    return {
        "Joint Displacements": (
            ["Story", "UniqueName", "OutputCase", "StepType", "Ux", "Uy", "Uz"],
            [
                ["Story3", "12", "EQX", "Max", "0.0105", "0.001", "0.0"],
                ["Story3", "12", "EQX", "Min", "-0.0150", "-0.001", "0.0"],
                ["Story2", "8", "EQX", "Max", "0.0062", "0.0005", "0.0"],
                ["Story2", "8", "EQX", "Min", "-0.0040", "-0.0005", "0.0"],
                ["Story1", "4", "EQX", "Max", "0.0021", "0.0002", "0.0"],
                ["Story1", "4", "EQX", "Min", "-0.0010", "-0.0002", "0.0"],
            ],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }


def _reaction_tables() -> dict:
    """Joint Reactions for two supports under a 'Dead' case (FX..MZ)."""
    return {
        "Joint Reactions": (
            ["Story", "UniqueName", "OutputCase", "StepType",
             "FX", "FY", "FZ", "MX", "MY", "MZ"],
            [
                ["Base", "1", "Dead", "Max", "1.0", "2.0", "40.0", "0.0", "0.0", "0.0"],
                ["Base", "2", "Dead", "Max", "-1.0", "2.0", "60.0", "0.0", "0.0", "0.0"],
            ],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }


def _drift_session():
    return bind(make_mock(tables=_drift_tables()))


def _disp_session():
    return bind(make_mock(tables=_displacement_tables()))


def _reaction_session():
    return bind(make_mock(tables=_reaction_tables()))


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------

def test_profile_peak_magnitude_and_story():
    p = Profile(
        elevation=np.array([12.0, 8.0, 4.0]),
        value=np.array([0.001, -0.003, 0.002]),
        stories=["Story3", "Story2", "Story1"],
        unit="",
    )
    val, story = p.peak
    assert story == "Story2"
    assert val == pytest.approx(-0.003)


def test_profile_peak_empty():
    p = Profile(elevation=np.array([]), value=np.array([]), stories=[])
    assert p.peak == (0.0, "")


# ----------------------------------------------------------------------
# StoryDrifts
# ----------------------------------------------------------------------

def test_story_drifts_builds_and_resolves_case():
    e = _drift_session()
    # Results is not yet wired into _COMPOSITES (a later stage does that),
    # so construct it directly on the bound session.
    s = Results(e).story_drifts(case="EQX")
    assert isinstance(s, StoryDrifts)
    assert s.case == "EQX"
    assert s.units["Drift"] == ""  # dimensionless
    # Only EQX rows survived case selection.
    assert set(s.df["OutputCase"]) == {"EQX"}


def test_story_drifts_profile_default_max_roof_to_base():
    s = Results(_drift_session()).story_drifts(case="EQX")
    p = s.profile(direction="X")  # default step="Max"
    assert p.unit == ""
    assert p.stories == ["Story3", "Story2", "Story1"]
    # Roof->base by elevation, Max StepType only.
    assert list(p.elevation) == sorted(p.elevation, reverse=True)
    np.testing.assert_allclose(p.value, [0.0012, 0.0018, 0.0009])


def test_story_drifts_profile_step_min():
    s = Results(_drift_session()).story_drifts(case="EQX")
    p = s.profile(direction="X", step="Min")
    np.testing.assert_allclose(p.value, [-0.0020, -0.0009, -0.0004])


def test_story_drifts_profile_step_abs():
    s = Results(_drift_session()).story_drifts(case="EQX")
    p = s.profile(direction="X", step="abs")
    # abs picks the larger magnitude per story across Max/Min.
    np.testing.assert_allclose(p.value, [-0.0020, 0.0018, 0.0009])


def test_story_drifts_direction_filter():
    s = Results(_drift_session()).story_drifts(case="EQX")
    p = s.profile(direction="Y")
    np.testing.assert_allclose(p.value, [0.0005, 0.0006, 0.0003])


def test_story_drifts_unknown_direction_raises():
    s = Results(_drift_session()).story_drifts(case="EQX")
    with pytest.raises(ETABSError):
        s.profile(direction="Q")


def test_story_drifts_peak():
    s = Results(_drift_session()).story_drifts(case="EQX")
    val, story = s.peak(direction="X")  # Max envelope
    assert story == "Story2"
    assert val == pytest.approx(0.0018)


def test_story_drifts_exceeds():
    s = Results(_drift_session()).story_drifts(case="EQX")
    hit = s.exceeds(0.0015)
    assert isinstance(hit, pd.DataFrame)
    # |Drift| > 0.0015: EQX X Story3 Min (-0.0020) and Story2 Max (0.0018).
    assert set(hit["Story"]) == {"Story3", "Story2"}


def test_story_drifts_elevation_in_report_units():
    s = Results(_drift_session()).story_drifts(case="EQX")
    p = s.profile(direction="X")
    # Default mock present length is m; default report system base length is mm,
    # so 12 m elevation bakes to a larger number (consistent length factor).
    e = _drift_session()
    factor = e.units.length_factor
    np.testing.assert_allclose(p.elevation, np.array([12.0, 8.0, 4.0]) * factor)


# ----------------------------------------------------------------------
# Displacements
# ----------------------------------------------------------------------

def test_displacements_builds_and_bakes_units():
    e = _disp_session()
    d = Results(e).displacements(case="EQX")
    assert isinstance(d, Displacements)
    assert d.case == "EQX"
    factor = e.units.length_factor
    # Ux column baked by the length factor (raw Story3 Max Ux = 0.0105).
    s3max = d.df[(d.df["Story"] == "Story3") & (d.df["StepType"] == "Max")]
    assert float(s3max["Ux"].iloc[0]) == pytest.approx(0.0105 * factor)
    assert d.units["Ux"]  # non-empty length label
    # Only present columns are labelled; this table has no rotation columns.
    assert "Rx" not in d.units


def test_displacements_profile_by_label_roof_to_base():
    e = _disp_session()
    d = Results(e).displacements(case="EQX")
    # Each story has a distinct joint; profile one joint at a time.
    factor = e.units.length_factor
    p = d.profile(label="12", direction="X")  # default step Max
    assert p.label == "12"
    assert p.stories == ["Story3"]
    np.testing.assert_allclose(p.value, [0.0105 * factor])


def test_displacements_peak_abs():
    e = _disp_session()
    d = Results(e).displacements(case="EQX")
    factor = e.units.length_factor
    val, story = d.peak(direction="X", step="abs")
    # Largest |Ux| across joints is Story3 Min = -0.0150.
    assert story == "Story3"
    assert val == pytest.approx(-0.0150 * factor)


def test_displacements_unknown_label_raises():
    d = Results(_disp_session()).displacements(case="EQX")
    with pytest.raises(ETABSError):
        d.profile(label="9999", direction="X")


def test_displacements_by_joint_six_vectors():
    e = _disp_session()
    d = Results(e).displacements(case="EQX")
    by = d.by_joint()
    assert set(by) == {"12", "8", "4"}
    # Each joint -> 6-vector; rotations absent in the table -> 0.0.
    assert all(len(v) == 6 for v in by.values())
    assert all(v[3:] == (0.0, 0.0, 0.0) for v in by.values())
    # by_joint returns PRESENT units (un-baked, the .sm.json contract): joint 12
    # Ux is the largest-magnitude across its Max(0.0105)/Min(-0.0150) rows.
    assert by["12"][0] == pytest.approx(-0.0150)


# ----------------------------------------------------------------------
# Reactions (ADR 0009 solve cross-check)
# ----------------------------------------------------------------------

def test_reactions_builds_and_by_joint():
    e = _reaction_session()
    r = Results(e).reactions(case="Dead")
    assert isinstance(r, Reactions)
    assert r.case == "Dead"
    by = r.by_joint()
    assert set(by) == {"1", "2"}
    # by_joint returns PRESENT units (un-baked): vertical reactions 40 / 60 kN.
    assert by["1"][2] == pytest.approx(40.0)
    assert by["2"][2] == pytest.approx(60.0)
    # Moments present (zero here) -> 6-vectors, force + moment labels set.
    assert all(len(v) == 6 for v in by.values())
    assert r.units["Fz"] and r.units["Mz"]


def test_reactions_requires_one_selector():
    r = Results(_reaction_session())
    with pytest.raises(ETABSError):
        r.reactions()  # neither case nor combo


# ----------------------------------------------------------------------
# Selection: exactly one of case/combo, fuzzy + listing
# ----------------------------------------------------------------------

def test_requires_exactly_one_selector():
    r = Results(_drift_session())
    with pytest.raises(ETABSError):
        r.story_drifts()  # neither
    with pytest.raises(ETABSError):
        r.story_drifts(case="EQX", combo="EQX")  # both


def test_combo_selector_works():
    r = Results(_drift_session())
    s = r.story_drifts(combo="EQY")
    assert s.case == "EQY"
    assert set(s.df["OutputCase"]) == {"EQY"}


def test_fuzzy_match_resolves_to_actual_case():
    # rapidfuzz is installed in this venv; "eqx" -> "EQX".
    r = Results(_drift_session())
    s = r.story_drifts(case="eqx")
    assert s.case == "EQX"


def test_unknown_case_lists_available():
    r = Results(_drift_session())
    with pytest.raises(ETABSError) as exc:
        r.story_drifts(case="TOTALLY_UNRELATED_NAME_XYZ")
    msg = str(exc.value)
    assert "EQX" in msg and "EQY" in msg


# ----------------------------------------------------------------------
# Column-map tolerance + loud failure on version drift
# ----------------------------------------------------------------------

def test_missing_required_column_raises_clear_error():
    bad = {
        "Story Drifts": (
            ["Story", "OutputCase", "StepType", "Direction"],  # no Drift
            [["Story3", "EQX", "Max", "X"]],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }
    r = Results(bind(make_mock(tables=bad)))
    with pytest.raises(ETABSError) as exc:
        r.story_drifts(case="EQX")
    assert "Drift" in str(exc.value)


def test_unknown_extra_columns_are_kept():
    extra = {
        "Story Drifts": (
            ["Story", "OutputCase", "StepType", "Direction", "Drift", "GUID"],
            [["Story3", "EQX", "Max", "X", "0.0012", "abc-123"]],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }
    s = Results(bind(make_mock(tables=extra))).story_drifts(case="EQX")
    assert "GUID" in s.df.columns


def test_empty_table_raises():
    empty = {
        "Story Drifts": (
            ["Story", "OutputCase", "StepType", "Direction", "Drift"],
            [],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }
    r = Results(bind(make_mock(tables=empty)))
    with pytest.raises(ETABSError):
        r.story_drifts(case="EQX")


# ----------------------------------------------------------------------
# StoryForces
# ----------------------------------------------------------------------

def test_story_forces_builds_and_bakes_force_label():
    e = bind(make_mock())
    f = Results(e).story_forces(case="EQX")
    assert isinstance(f, StoryForces)
    assert f.case == "EQX"
    # Force columns get a real force-unit label (not the raw dim key 'force').
    assert f.units["VX"] == e.units.force.name
    assert f.units["VX"] != "force"
    # Moment label is force·length, not 'moment'.
    assert "·" in f.units["MY"]
    assert f.units["MY"] != "moment"


def test_story_forces_shear_stacked_top_bottom():
    e = bind(make_mock())
    factor = e.units.force_factor
    f = Results(e).story_forces(case="EQX")
    p = f.shear(direction="X")
    # 3 stories -> 6 stacked points (bottom,top per story), roof->base.
    assert p.value.size == 6
    # Cumulative shear: Story3 = 100, Story2 = 200, Story1 = 300 (kN),
    # interleaved bottom/top. All equal per story here.
    np.testing.assert_allclose(
        p.value, np.array([100, 100, 200, 200, 300, 300]) * factor
    )
    assert p.unit == e.units.force.name


def test_story_forces_shear_elevation_is_monotonic_staircase():
    # Distinct per-story shear so value/elevation ordering is actually
    # exercised (the old test used equal-per-story values, hiding the bug).
    tables = {
        "Story Forces": (
            ["Story", "OutputCase", "Location", "StepType",
             "P", "VX", "VY", "T", "MX", "MY"],
            [
                ["Story3", "EQX", "Top", "Max", "0", "10", "0", "0", "0", "0"],
                ["Story3", "EQX", "Bottom", "Max", "0", "10", "0", "0", "0", "0"],
                ["Story2", "EQX", "Top", "Max", "0", "25", "0", "0", "0", "0"],
                ["Story2", "EQX", "Bottom", "Max", "0", "25", "0", "0", "0", "0"],
                ["Story1", "EQX", "Top", "Max", "0", "40", "0", "0", "0", "0"],
                ["Story1", "EQX", "Bottom", "Max", "0", "40", "0", "0", "0", "0"],
            ],
        ),
        "Tower and Base Story Definitions": (
            ["Tower", "BSName", "BSElev"],
            [["T1", "Base", "0.0"]],
        ),
    }
    e = bind(make_mock(tables=tables))
    factor = e.units.force_factor
    lf = e.units.length_factor
    p = Results(e).story_forces(case="EQX")
    sh = p.shear(direction="X")
    # Elevation must be the clean monotonic (descending, roof->base) staircase
    # aligned with the interleaved bottom/top value array, NOT the zig-zag.
    np.testing.assert_allclose(
        sh.elevation, np.array([12.0, 8.0, 8.0, 4.0, 4.0, 0.0]) * lf
    )
    # Strictly non-increasing (monotonic) — the property the bug violated.
    assert np.all(np.diff(sh.elevation) <= 0)
    # Distinct per-story shear stays aligned with the staircase.
    np.testing.assert_allclose(
        sh.value, np.array([10, 10, 25, 25, 40, 40]) * factor
    )


def test_story_forces_per_story_force_is_diff():
    e = bind(make_mock())
    factor = e.units.force_factor
    f = Results(e).story_forces(case="EQX")
    p = f.story_force(direction="X")
    # diff of cumulative Top shear [100,200,300] with leading 0 -> [100,100,100].
    np.testing.assert_allclose(p.value, np.array([100, 100, 100]) * factor)
    assert p.stories == ["Story3", "Story2", "Story1"]


def test_story_forces_unknown_direction_raises():
    f = Results(bind(make_mock())).story_forces(case="EQX")
    with pytest.raises(ETABSError):
        f.shear(direction="Z")


def test_story_forces_requires_one_selector():
    r = Results(bind(make_mock()))
    with pytest.raises(ETABSError):
        r.story_forces()
    with pytest.raises(ETABSError):
        r.story_forces(case="EQX", combo="EQX")


# ----------------------------------------------------------------------
# WallForces
# ----------------------------------------------------------------------

def test_wall_forces_builds_with_piers_combos_and_state():
    e = bind(make_mock())
    w = Results(e).wall_forces()
    assert isinstance(w, WallForces)
    assert w.piers == ["P1"]
    assert set(w.combos) == {"DStl1", "DStlE1"}
    # State tag: combos containing 'E' are Dynamic, else Static.
    states = dict(zip(w.df["Combo"], w.df["State"]))
    assert states["DStl1"] == "Static"
    assert states["DStlE1"] == "Dynamic"
    # Force/moment labels are real units, not raw dim keys.
    assert w.units["V2"] == e.units.force.name
    assert "·" in w.units["M3"]


def test_wall_forces_pier_slice_and_unknown():
    w = Results(bind(make_mock())).wall_forces()
    p1 = w.pier("P1")
    assert isinstance(p1, pd.DataFrame)
    assert set(p1["Pier"]) == {"P1"}
    with pytest.raises(ETABSError):
        w.pier("NOPE")


def test_wall_forces_envelope_min_max_per_elevation():
    e = bind(make_mock())
    factor = e.units.force_factor
    w = Results(e).wall_forces()
    env = w.envelope("P1")
    assert set(env) == {"P", "M3", "V2"}
    # All Story3 rows map to elevation 12; V2 across both combos' Top/Bottom
    # rows is {20, 22, 40, 42} -> min 20, max 42 (kN).
    v2 = env["V2"]
    story3_elev = e.units.length_factor * 12.0
    assert v2.loc[story3_elev, "min"] == pytest.approx(20.0 * factor)
    assert v2.loc[story3_elev, "max"] == pytest.approx(42.0 * factor)


def test_wall_forces_amplification_metadata_not_baked():
    e = bind(make_mock())
    w_plain = Results(e).wall_forces()
    assert w_plain.shear_amplification == 1.0

    w = Results(e).wall_forces(
        design_parameters={"overstrength": 1.25, "dynamic_amplification": 1.5}
    )
    # min(3, 1.25*1.5) = 1.875, stored as metadata only.
    assert w.shear_amplification == pytest.approx(1.875)
    # Not baked into the frame: V2 values match the unamplified snapshot.
    np.testing.assert_allclose(
        w.df["V2"].to_numpy(dtype=float),
        w_plain.df["V2"].to_numpy(dtype=float),
    )


def test_wall_forces_amplification_capped_at_three():
    w = Results(bind(make_mock())).wall_forces(
        design_parameters={"overstrength": 2.0, "dynamic_amplification": 2.0}
    )
    assert w.shear_amplification == 3.0
