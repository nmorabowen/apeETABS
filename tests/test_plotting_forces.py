"""Tests for the force plots (ADR 0004 §5, P4).

Synthetic StoryForces/WallForces/Profile-shaped stubs match the pinned fields
so these tests stay independent of the results module. Agg backend is forced so
nothing needs a display.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from apeETABS.plotting import (  # noqa: E402
    Plot,
    story_forces,
    story_shear,
    wall_force_envelopes,
    wall_forces,
)


# ----------------------------------------------------------------------
# Synthetic stubs
# ----------------------------------------------------------------------


class _Profile:
    def __init__(self, *, elevation, value, stories=None, label=None, unit=""):
        self.elevation = np.asarray(elevation, dtype=float)
        self.value = np.asarray(value, dtype=float)
        self.stories = list(stories) if stories is not None else []
        self.label = label
        self.unit = unit


class _StoryForces:
    """StoryForces-shaped stub: ``shear`` / ``story_force`` return Profiles."""

    def __init__(self, shear_profile, force_profile):
        self._shear = shear_profile
        self._force = force_profile
        self.calls = []

    def shear(self, *, direction="X", step="Max"):
        self.calls.append(("shear", direction, step))
        return self._shear

    def story_force(self, *, direction="X", step="Max"):
        self.calls.append(("force", direction, step))
        return self._force


class _WallForces:
    """WallForces-shaped stub: ``pier`` / ``envelope`` + units metadata."""

    def __init__(self, df, *, units=None, shear_amplification=None):
        self.df = df
        self.units = units or {"P": "tonf", "M3": "tonf-m", "V2": "tonf"}
        self.shear_amplification = shear_amplification

    def pier(self, label):
        return self.df[self.df["Pier"] == label]

    def envelope(self, pier):
        d = self.df[self.df["Pier"] == pier]
        return {
            f: d.groupby("Elevation")[f].agg(["min", "max"])
            for f in ("P", "M3", "V2")
        }


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    plt.close("all")


@pytest.fixture
def story_snapshot():
    # stacked top/bottom staircase (mimics StoryForces.shear output)
    shear = _Profile(
        elevation=[12.0, 12.0, 8.0, 8.0, 4.0, 4.0, 0.0, 0.0],
        value=[10.0, 10.0, 25.0, 25.0, 40.0, 40.0, 55.0, 55.0],
        label="EQx",
        unit="tonf",
    )
    force = _Profile(
        elevation=[12.0, 8.0, 4.0, 0.0],
        value=[10.0, 15.0, 15.0, 15.0],
        label="EQx",
        unit="tonf",
    )
    return _StoryForces(shear, force)


@pytest.fixture
def wall_snapshot():
    rows = []
    for combo in ("D+E", "D-E"):
        sign = 1.0 if combo == "D+E" else -1.0
        for elev in (8.0, 4.0, 0.0):
            rows.append(
                {
                    "Pier": "P1",
                    "Combo": combo,
                    "Elevation": elev,
                    "P": sign * (100.0 + elev),
                    "M3": sign * (50.0 + 2 * elev),
                    "V2": sign * (20.0 + elev),
                }
            )
    df = pd.DataFrame(rows)
    return _WallForces(df, shear_amplification=2.5)


# ----------------------------------------------------------------------
# story_shear
# ----------------------------------------------------------------------


def test_story_shear_returns_fig_ax_and_mirrors(story_snapshot):
    fig, ax = story_shear(story_snapshot)
    assert fig is ax.figure
    # +v and -v drawn (mirrored)
    assert len(ax.lines) == 2
    np.testing.assert_allclose(ax.lines[0].get_xdata(), story_snapshot._shear.value)
    np.testing.assert_allclose(ax.lines[1].get_xdata(), -story_snapshot._shear.value)


def test_story_shear_axis_label_and_forwarding(story_snapshot):
    _, ax = story_shear(story_snapshot, direction="Y", step="Min")
    assert ax.get_xlabel() == "Story Shear Y [tonf]"
    assert ax.get_ylabel() == "Elevation"
    assert ("shear", "Y", "Min") in story_snapshot.calls


def test_story_shear_ax_injection(story_snapshot):
    fig, ax = plt.subplots()
    fig2, ax2 = story_shear(story_snapshot, ax=ax)
    assert ax2 is ax and fig2 is fig


# ----------------------------------------------------------------------
# story_forces
# ----------------------------------------------------------------------


def test_story_forces_barh_and_line(story_snapshot):
    fig, ax = story_forces(story_snapshot)
    assert fig is ax.figure
    # two barh containers (±) + two lines (±)
    assert len(ax.patches) == 2 * len(story_snapshot._force.value)
    assert len(ax.lines) == 2
    assert ax.get_xlabel() == "Story Force X [tonf]"


def test_story_forces_forwards_step(story_snapshot):
    story_forces(story_snapshot, direction="Y", step="abs")
    assert ("force", "Y", "abs") in story_snapshot.calls


# ----------------------------------------------------------------------
# wall_forces
# ----------------------------------------------------------------------


def test_wall_forces_triptych(wall_snapshot):
    fig, axes = wall_forces(wall_snapshot, "P1")
    assert len(axes) == 3
    assert axes[0].figure is fig
    # 2 combos x 3 panels = 6 lines total, 2 per panel
    assert all(len(a.lines) == 2 for a in axes)
    assert "P_u" in axes[0].get_xlabel()
    assert "tonf" in axes[0].get_xlabel()


def test_wall_forces_ax_injection(wall_snapshot):
    fig, axes = plt.subplots(1, 3)
    fig2, axes2 = wall_forces(wall_snapshot, "P1", ax=axes)
    assert fig2 is fig
    assert axes2 is axes


# ----------------------------------------------------------------------
# wall_force_envelopes
# ----------------------------------------------------------------------


def test_wall_envelopes_min_max(wall_snapshot):
    fig, axes = wall_force_envelopes(wall_snapshot, "P1")
    # 2 envelope lines per panel (min/max), no amplification overlay
    assert all(len(a.lines) == 2 for a in axes)


def test_wall_envelopes_amplified_shear(wall_snapshot):
    fig, axes = wall_force_envelopes(wall_snapshot, "P1", amplification=2.5)
    # V2 panel (index 2) gets 2 extra amplified lines
    assert len(axes[2].lines) == 4
    assert len(axes[0].lines) == 2  # P unaffected
    labels = [ln.get_label() for ln in axes[2].lines]
    assert any("Amplified" in str(text) for text in labels)


def test_wall_envelopes_no_show(wall_snapshot, monkeypatch):
    called = {"show": False}
    monkeypatch.setattr(plt, "show", lambda *a, **k: called.__setitem__("show", True))
    wall_force_envelopes(wall_snapshot, "P1")
    assert called["show"] is False


# ----------------------------------------------------------------------
# Plot sugar
# ----------------------------------------------------------------------


class _FakeResults:
    def __init__(self, story=None, wall=None):
        self._story = story
        self._wall = wall
        self.calls = []

    def story_forces(self, *, case=None, combo=None):
        self.calls.append(("story_forces", case, combo))
        return self._story

    def wall_forces(self, *, design_parameters=None):
        self.calls.append(("wall_forces", design_parameters))
        return self._wall


class _FakeSession:
    def __init__(self, results):
        self.results = results


def test_sugar_story_shear_with_snapshot(story_snapshot):
    plot = Plot(_FakeSession(_FakeResults(story=story_snapshot)))
    fig, ax = plot.story_shear(story_snapshot, direction="X")
    assert fig is ax.figure
    assert plot._parent.results.calls == []  # snapshot in hand -> no fetch


def test_sugar_story_forces_fetches(story_snapshot):
    results = _FakeResults(story=story_snapshot)
    plot = Plot(_FakeSession(results))
    plot.story_forces(case="EQx")
    assert results.calls == [("story_forces", "EQx", None)]


def test_sugar_wall_forces_fetches(wall_snapshot):
    results = _FakeResults(wall=wall_snapshot)
    plot = Plot(_FakeSession(results))
    fig, axes = plot.wall_forces("P1", design_parameters={"overstrength": 1.0})
    assert results.calls == [("wall_forces", {"overstrength": 1.0})]
    assert len(axes) == 3


def test_sugar_wall_envelopes_uses_snapshot_amplification(wall_snapshot):
    results = _FakeResults(wall=wall_snapshot)
    plot = Plot(_FakeSession(results))
    fig, axes = plot.wall_force_envelopes("P1")
    # snapshot carries shear_amplification=2.5 -> amplified overlay present
    assert len(axes[2].lines) == 4


# ----------------------------------------------------------------------
# Builder<->plotter integration (real path, no synthetic stubs)
# ----------------------------------------------------------------------
#
# The stubbed tests above pin a synthetic staircase whose shape differs from
# the REAL StoryForces builder. This integration test drives the production
# path end to end on the mock fixture: e.plot.story_shear(case=...) fetches the
# real StoryForces via e.results and renders it. Asserting the plotted line
# matches StoryForces.shear().value/.elevation catches builder<->plotter drift.


def test_plot_story_shear_integration_matches_real_builder(etabs):
    snap = etabs.results.story_forces(case="EQX")
    profile = snap.shear(direction="X")

    fig, ax = etabs.plot.story_shear(case="EQX", direction="X")
    assert fig is ax.figure

    # First line is +v (value, elevation); it must mirror the real Profile the
    # builder produced — not the synthetic [12,12,8,8,4,4,0,0] stub shape.
    line = ax.lines[0]
    np.testing.assert_allclose(line.get_xdata(), profile.value)
    np.testing.assert_allclose(line.get_ydata(), profile.elevation)
