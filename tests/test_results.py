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
from apeETABS.results import Displacements, Profile, Results, StoryDrifts

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


def _drift_session():
    return bind(make_mock(tables=_drift_tables()))


def _disp_session():
    return bind(make_mock(tables=_displacement_tables()))


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
