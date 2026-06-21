"""Tests for the P9 seismic-irregularity slice (ADR 0003/0004).

Covers the three result domains (CentersMassRigidity, StoryStiffness,
TorsionIrregularity), their ASCE 7 check math + flags, and the four pure
plotters. All data is deterministic in-memory; the real composites run against
the mock SapModel via the shared ``bind``/``make_mock`` helpers.

Present units in the default mock are kN, m, C; the report base length is mm, so
the length factor is 1000 (m -> mm). Coordinate/elevation columns bake by that
factor; stiffness/mass columns stay raw.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from apeETABS.criteria import ASCE7, IrregularityCriteria  # noqa: E402
from apeETABS.errors import ETABSError  # noqa: E402
from apeETABS.plotting import (  # noqa: E402
    center_mass_rigidity,
    mass_irregularity,
    soft_story,
    torsional_irregularity,
)
from apeETABS.results import (  # noqa: E402
    CentersMassRigidity,
    Results,
    StoryStiffness,
    TorsionIrregularity,
)

from ._mock_sapmodel import StoriesSpec  # noqa: E402
from .conftest import bind, make_mock  # noqa: E402

LF = 1000.0  # m -> mm length factor for the default mock report system

# Four-story spec (top-first), base at 0. Elevations 16/12/8/4.
STORIES4 = StoriesSpec(
    names=["Story4", "Story3", "Story2", "Story1"],
    elevations=[16.0, 12.0, 8.0, 4.0],
    heights=[4.0, 4.0, 4.0, 4.0],
    base_name="Base",
    base_elevation=0.0,
)

_TOWER = (
    ["Tower", "BSName", "BSElev"],
    [["T1", "Base", "0.0"]],
)


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    plt.close("all")


# ----------------------------------------------------------------------
# Fixture tables
# ----------------------------------------------------------------------


def _cmr_tables() -> dict:
    """CM/CR + masses. Story2 mass=300 is >1.5x its neighbors (100/100)."""
    return {
        "Centers Of Mass And Rigidity": (
            ["Story", "Diaphragm", "MassX", "MassY", "XCM", "YCM", "XCR", "YCR"],
            [
                # Story4 (roof) light: mass 80 < floor below (100) -> exempt
                # (80 is not > 1.5*100, so the heavier-than-neighbor test skips it).
                ["Story4", "D1", "80.0", "80.0", "10.0", "5.0", "10.0", "5.0"],
                ["Story3", "D1", "100.0", "100.0", "12.0", "5.0", "10.0", "5.0"],
                # Story2 heavy: 300 > 1.5*100 -> mass irregular.
                ["Story2", "D1", "300.0", "300.0", "10.0", "8.0", "10.0", "5.0"],
                ["Story1", "D1", "100.0", "100.0", "10.0", "5.0", "10.0", "5.0"],
            ],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }


def _stiffness_tables() -> dict:
    """Story Stiffness for soft-story checks (X direction hand-tuned).

    Stiffness top->base: 40, 100, 65, 100. Story2 (K=65) is the test case:
      * K_above = Story3 = 100 -> ratio_adjacent = 0.65
        (< 0.70 1a-adjacent YES; > 0.60 so 1b-adjacent NO).
      * stories above Story2 are Story4(40), Story3(100); mean3 = 70 ->
        ratio_avg3 = 65/70 = 0.9286 (>= 0.80 so 1a-avg3 NO; >= 0.70 so 1b-avg3 NO).
    Net: Story2 is soft_1a (via adjacent) but NOT soft_1b. The deliberately
    soft *roof above* (40) is the top story (no "above") so it never flags.
    """
    return {
        "Story Stiffness": (
            ["Story", "OutputCase", "CaseType", "StepType", "StiffX", "StiffY"],
            [
                ["Story4", "EQX", "LinStatic", "Max", "40.0", "100.0"],
                ["Story3", "EQX", "LinStatic", "Max", "100.0", "100.0"],
                ["Story2", "EQX", "LinStatic", "Max", "65.0", "100.0"],
                ["Story1", "EQX", "LinStatic", "Max", "100.0", "100.0"],
            ],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }


def _stiffness_1b_tables() -> dict:
    """Story Stiffness where Story2 trips the *extreme* 1b threshold.

    Top->base: 100, 100, 50, 100. Story2 K=50 -> ratio_adjacent 0.50 < 0.60
    (1b) and < 0.70 (1a). avg3 above = 100 -> 0.50 < 0.70 (1b) and < 0.80 (1a).
    """
    return {
        "Story Stiffness": (
            ["Story", "OutputCase", "CaseType", "StepType", "StiffX", "StiffY"],
            [
                ["Story4", "EQX", "LinStatic", "Max", "100.0", "100.0"],
                ["Story3", "EQX", "LinStatic", "Max", "100.0", "100.0"],
                ["Story2", "EQX", "LinStatic", "Max", "50.0", "100.0"],
                ["Story1", "EQX", "LinStatic", "Max", "100.0", "100.0"],
            ],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }


def _torsion_tables() -> dict:
    """Story Max Over Avg Drifts. Story3 ratio=1.3 (1a), Story2 ratio=1.5 (1b)."""
    return {
        "Story Max Over Avg Drifts": (
            ["Story", "OutputCase", "CaseType", "StepType", "Direction",
             "Max Drift", "Avg Drift", "Ratio"],
            [
                ["Story4", "EQX", "LinStatic", "Max", "X", "1.0", "1.0", "1.0"],
                # 1.3 > 1.2 (1a) but <= 1.4 (not 1b).
                ["Story3", "EQX", "LinStatic", "Max", "X", "1.3", "1.0", "1.3"],
                # 1.5 > 1.4 (1b).
                ["Story2", "EQX", "LinStatic", "Max", "X", "1.5", "1.0", "1.5"],
                ["Story1", "EQX", "LinStatic", "Max", "X", "1.1", "1.0", "1.1"],
                # A Y row to exercise direction filtering.
                ["Story3", "EQX", "LinStatic", "Max", "Y", "1.05", "1.0", "1.05"],
            ],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }


def _cmr_session():
    return bind(make_mock(tables=_cmr_tables(), stories=STORIES4))


def _stiffness_session(tables=None):
    return bind(make_mock(tables=tables or _stiffness_tables(), stories=STORIES4))


def _torsion_session():
    return bind(make_mock(tables=_torsion_tables(), stories=STORIES4))


# ----------------------------------------------------------------------
# criteria
# ----------------------------------------------------------------------


def test_criteria_defaults():
    assert ASCE7.torsion_1a == 1.2
    assert ASCE7.torsion_1b == 1.4
    assert ASCE7.soft_1a_adjacent == 0.70
    assert ASCE7.soft_1a_avg3 == 0.80
    assert ASCE7.soft_1b_adjacent == 0.60
    assert ASCE7.soft_1b_avg3 == 0.70
    assert ASCE7.mass_ratio == 1.50


def test_criteria_is_frozen():
    with pytest.raises(Exception):
        ASCE7.torsion_1a = 9.9  # type: ignore[misc]


# ----------------------------------------------------------------------
# CentersMassRigidity
# ----------------------------------------------------------------------


def test_cmr_builds_and_bakes_coords_roof_to_base():
    c = Results(_cmr_session()).centers_mass_rigidity()
    assert isinstance(c, CentersMassRigidity)
    # Roof->base order.
    assert list(c.df["Story"]) == ["Story4", "Story3", "Story2", "Story1"]
    # Coordinates baked by length factor (XCM Story3 = 12 m -> 12000 mm).
    s3 = c.df[c.df["Story"] == "Story3"].iloc[0]
    assert float(s3["XCM"]) == pytest.approx(12.0 * LF)
    assert c.units["XCM"]  # non-empty length label
    # Mass left raw.
    assert float(s3["MassX"]) == pytest.approx(100.0)


def test_cmr_eccentricity_math():
    c = Results(_cmr_session()).centers_mass_rigidity()
    ecc = c.eccentricity()
    # Story3: XCM 12, XCR 10 -> ex = 2 m -> 2000 mm; ey = 0.
    s3 = ecc[ecc["Story"] == "Story3"].iloc[0]
    assert float(s3["ex"]) == pytest.approx(2.0 * LF)
    assert float(s3["ey"]) == pytest.approx(0.0)
    # Story2: YCM 8, YCR 5 -> ey = 3 m -> 3000 mm; ex = 0.
    s2 = ecc[ecc["Story"] == "Story2"].iloc[0]
    assert float(s2["ex"]) == pytest.approx(0.0)
    assert float(s2["ey"]) == pytest.approx(3.0 * LF)


def test_cmr_mass_check_flags_and_roof_exemption():
    c = Results(_cmr_session()).centers_mass_rigidity()
    mc = c.mass_check()
    assert list(mc["Story"]) == ["Story4", "Story3", "Story2", "Story1"]
    flags = dict(zip(mc["Story"], mc["irregular"]))
    # Story2 (300) > 1.5*100 either neighbor -> irregular.
    assert flags["Story2"]
    # Story4 is the light roof (80), below it Story3=100; 80 is not > 1.5*100,
    # so the light roof is exempt (not flagged).
    assert not flags["Story4"]
    # Story3 (100): above=80 -> 100 > 1.5*80=120? no; below=300 -> no.
    # Story1 (100): above=300 -> lighter, not heavier. Neither flagged.
    assert not flags["Story3"]
    assert not flags["Story1"]
    # ratio values: Story2 ratio_above = 300/100 = 3.
    s2 = mc[mc["Story"] == "Story2"].iloc[0]
    assert float(s2["ratio_above"]) == pytest.approx(3.0)
    assert float(s2["ratio_below"]) == pytest.approx(3.0)


def test_cmr_mass_check_single_story_not_irregular():
    tables = {
        "Centers Of Mass And Rigidity": (
            ["Story", "MassX", "MassY", "XCM", "YCM", "XCR", "YCR"],
            [["Story1", "100.0", "100.0", "10.0", "5.0", "10.0", "5.0"]],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }
    one = StoriesSpec(names=["Story1"], elevations=[4.0], heights=[4.0])
    c = Results(bind(make_mock(tables=tables, stories=one))).centers_mass_rigidity()
    mc = c.mass_check()
    assert not bool(mc["irregular"].iloc[0])


def test_cmr_empty_table_raises():
    tables = {
        "Centers Of Mass And Rigidity": (
            ["Story", "XCM", "YCM", "XCR", "YCR"],
            [],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }
    r = Results(bind(make_mock(tables=tables, stories=STORIES4)))
    with pytest.raises(ETABSError):
        r.centers_mass_rigidity()


# ----------------------------------------------------------------------
# StoryStiffness / soft story
# ----------------------------------------------------------------------


def test_story_stiffness_builds_with_raw_label():
    e = _stiffness_session()
    s = Results(e).story_stiffness(case="EQX")
    assert isinstance(s, StoryStiffness)
    assert s.case == "EQX"
    # force/length label, raw stiffness (not length-baked).
    assert s.units["StiffX"] == f"{e.units.force.name}/{e.units.length.name}"
    s2 = s.df[s.df["Story"] == "Story2"].iloc[0]
    assert float(s2["StiffX"]) == pytest.approx(65.0)


def test_soft_story_1a_not_1b_math():
    s = Results(_stiffness_session()).story_stiffness(case="EQX")
    soft = s.soft_story(direction="X")
    assert list(soft["Story"]) == ["Story4", "Story3", "Story2", "Story1"]
    s2 = soft[soft["Story"] == "Story2"].iloc[0]
    # K_i=65, K_above=100 -> ratio_adjacent 0.65.
    assert float(s2["ratio_adjacent"]) == pytest.approx(0.65)
    # avg3 above Story2 = mean(40, 100) = 70 -> ratio_avg3 = 65/70 = 0.9286.
    assert float(s2["ratio_avg3"]) == pytest.approx(65.0 / 70.0)
    # 0.65 < 0.70 (1a adjacent) -> soft_1a True.
    assert bool(s2["soft_1a"])
    # 0.65 > 0.60 (1b adjacent NO) AND 0.9286 > 0.70 (1b avg3 NO) -> soft_1b False.
    assert not bool(s2["soft_1b"])


def test_soft_story_top_story_nan_no_flag():
    s = Results(_stiffness_session()).story_stiffness(case="EQX")
    soft = s.soft_story(direction="X")
    top = soft[soft["Story"] == "Story4"].iloc[0]
    assert np.isnan(float(top["ratio_adjacent"]))
    assert np.isnan(float(top["ratio_avg3"]))
    assert not bool(top["soft_1a"])
    assert not bool(top["soft_1b"])


def test_soft_story_1b_extreme():
    s = Results(_stiffness_session(_stiffness_1b_tables())).story_stiffness(case="EQX")
    soft = s.soft_story(direction="X")
    s2 = soft[soft["Story"] == "Story2"].iloc[0]
    # K=50, K_above=100 -> 0.50 < 0.60 (1b adjacent) and < 0.70 (1a).
    assert float(s2["ratio_adjacent"]) == pytest.approx(0.50)
    assert bool(s2["soft_1a"])
    assert bool(s2["soft_1b"])


def test_soft_story_y_direction_not_soft():
    # StiffY is uniform 100 in both fixtures -> no soft story in Y.
    s = Results(_stiffness_session()).story_stiffness(case="EQX")
    soft = s.soft_story(direction="Y")
    assert not soft["soft_1a"].any()
    assert not soft["soft_1b"].any()


def test_story_stiffness_requires_one_selector():
    r = Results(_stiffness_session())
    with pytest.raises(ETABSError):
        r.story_stiffness()
    with pytest.raises(ETABSError):
        r.story_stiffness(case="EQX", combo="EQX")


def test_story_stiffness_empty_table_raises():
    tables = {
        "Story Stiffness": (
            ["Story", "OutputCase", "StepType", "StiffX", "StiffY"],
            [],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }
    r = Results(bind(make_mock(tables=tables, stories=STORIES4)))
    with pytest.raises(ETABSError):
        r.story_stiffness(case="EQX")


# ----------------------------------------------------------------------
# TorsionIrregularity
# ----------------------------------------------------------------------


def test_torsion_ratios_math_and_flags():
    t = Results(_torsion_session()).torsion_irregularity(case="EQX")
    assert isinstance(t, TorsionIrregularity)
    r = t.ratios(direction="X")
    assert list(r["Story"]) == ["Story4", "Story3", "Story2", "Story1"]
    # ratio = Maximum/Average (recomputed).
    s3 = r[r["Story"] == "Story3"].iloc[0]
    assert float(s3["ratio"]) == pytest.approx(1.3)
    assert bool(s3["torsion_1a"])  # 1.3 > 1.2
    assert not bool(s3["torsion_1b"])  # 1.3 <= 1.4
    s2 = r[r["Story"] == "Story2"].iloc[0]
    assert float(s2["ratio"]) == pytest.approx(1.5)
    assert bool(s2["torsion_1a"])
    assert bool(s2["torsion_1b"])  # 1.5 > 1.4
    s1 = r[r["Story"] == "Story1"].iloc[0]
    assert not bool(s1["torsion_1a"])  # 1.1 <= 1.2


def test_torsion_direction_filter():
    t = Results(_torsion_session()).torsion_irregularity(case="EQX")
    ry = t.ratios(direction="Y")
    # Only the single Y row (Story3) survives.
    assert list(ry["Story"]) == ["Story3"]
    assert float(ry["ratio"].iloc[0]) == pytest.approx(1.05)


def test_torsion_divzero_guard():
    tables = {
        "Story Max Over Avg Drifts": (
            ["Story", "OutputCase", "StepType", "Direction",
             "Max Drift", "Avg Drift", "Ratio"],
            [["Story1", "EQX", "Max", "X", "1.0", "0.0", "0.0"]],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }
    one = StoriesSpec(names=["Story1"], elevations=[4.0], heights=[4.0])
    t = Results(bind(make_mock(tables=tables, stories=one))).torsion_irregularity(
        case="EQX"
    )
    r = t.ratios(direction="X")
    assert np.isnan(float(r["ratio"].iloc[0]))
    assert not bool(r["torsion_1a"].iloc[0])


def test_torsion_empty_table_raises():
    tables = {
        "Story Max Over Avg Drifts": (
            ["Story", "OutputCase", "StepType", "Direction", "Max Drift", "Avg Drift"],
            [],
        ),
        "Tower and Base Story Definitions": _TOWER,
    }
    r = Results(bind(make_mock(tables=tables, stories=STORIES4)))
    with pytest.raises(ETABSError):
        r.torsion_irregularity(case="EQX")


def test_torsion_custom_criteria():
    t = Results(_torsion_session()).torsion_irregularity(case="EQX")
    strict = IrregularityCriteria(torsion_1a=1.05, torsion_1b=1.25)
    r = t.ratios(direction="X", criteria=strict)
    s1 = r[r["Story"] == "Story1"].iloc[0]  # ratio 1.1
    assert bool(s1["torsion_1a"])  # 1.1 > 1.05 now


# ----------------------------------------------------------------------
# Plotters (smoke: return Figure + Axes)
# ----------------------------------------------------------------------


def test_plot_center_mass_rigidity_smoke():
    c = Results(_cmr_session()).centers_mass_rigidity()
    fig, ax = center_mass_rigidity(c)
    assert fig is ax.figure
    # CM + CR scatter collections present.
    assert len(ax.collections) >= 2


def test_plot_torsional_irregularity_smoke():
    t = Results(_torsion_session()).torsion_irregularity(case="EQX")
    fig, ax = torsional_irregularity(t, direction="X")
    assert fig is ax.figure
    assert ax.get_ylabel() == "Elevation"
    # Two reference axvlines at 1.2 / 1.4 plus the ratio line.
    assert len(ax.lines) >= 3


def test_plot_soft_story_two_panels():
    s = Results(_stiffness_session()).story_stiffness(case="EQX")
    fig, axes = soft_story(s, direction="X")
    assert len(axes) == 2
    assert axes[0].figure is fig
    assert axes[0].get_ylabel() == "Elevation"


def test_plot_mass_irregularity_two_panels():
    c = Results(_cmr_session()).centers_mass_rigidity()
    fig, axes = mass_irregularity(c)
    assert len(axes) == 2
    assert axes[0].figure is fig
    # barh patches present on the mass panel (4 stories).
    assert len(axes[0].patches) == 4


# ----------------------------------------------------------------------
# Plot sugar (e.plot.*) — resolves snapshot-or-fetch
# ----------------------------------------------------------------------


def test_sugar_cm_cr_and_mass(monkeypatch):
    e = _cmr_session()
    fig, ax = e.plot.cm_cr()
    assert fig is ax.figure
    fig2, axes2 = e.plot.mass_irregularity()
    assert len(axes2) == 2


def test_sugar_torsional_and_soft_story():
    et = _torsion_session()
    fig, ax = et.plot.torsional_irregularity(case="EQX", direction="X")
    assert fig is ax.figure
    es = _stiffness_session()
    fig2, axes2 = es.plot.soft_story(case="EQX", direction="X")
    assert len(axes2) == 2
