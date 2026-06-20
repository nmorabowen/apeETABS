"""Tests for the plotting layer (ADR 0004).

These tests construct SYNTHETIC snapshot/Profile-like objects matching the
pinned interface, so they do not depend on the results module (built by a
sibling agent). Matplotlib's Agg backend is forced so nothing needs a display.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from apeETABS.plotting import (  # noqa: E402
    Plot,
    displacement_profile,
    drift_profile,
    style,
)


# ----------------------------------------------------------------------
# Synthetic snapshot stubs (pinned Profile / StoryDrifts / Displacements)
# ----------------------------------------------------------------------


class _Profile:
    """Matches the pinned Profile fields used by the plotters."""

    def __init__(self, *, elevation, value, stories, label=None, unit=""):
        self.elevation = np.asarray(elevation, dtype=float)
        self.value = np.asarray(value, dtype=float)
        self.stories = list(stories)
        self.label = label
        self.unit = unit

    @property
    def peak(self):
        i = int(np.argmax(np.abs(self.value)))
        return float(abs(self.value[i])), self.stories[i]


class _Drifts:
    """StoryDrifts-shaped stub: only ``profile(...)`` is exercised."""

    def __init__(self, profile):
        self._profile = profile
        self.last_call = None

    def profile(self, *, direction="X", step="Max"):
        self.last_call = {"direction": direction, "step": step}
        return self._profile


class _Displacements:
    """Displacements-shaped stub: only ``profile(...)`` is exercised."""

    def __init__(self, profile):
        self._profile = profile
        self.last_call = None

    def profile(self, *, label, direction="X", step="Max"):
        self.last_call = {"label": label, "direction": direction, "step": step}
        return self._profile


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    plt.close("all")


@pytest.fixture
def drift_snapshot():
    prof = _Profile(
        elevation=[12.0, 8.0, 4.0, 0.0],
        value=[0.012, 0.018, 0.009, 0.0],
        stories=["Story3", "Story2", "Story1", "Base"],
        label="EQx",
        unit="",  # drift is dimensionless
    )
    return _Drifts(prof)


@pytest.fixture
def disp_snapshot():
    prof = _Profile(
        elevation=[12.0, 8.0, 4.0, 0.0],
        value=[30.0, 20.0, 10.0, 0.0],
        stories=["Story3", "Story2", "Story1", "Base"],
        label="P1",
        unit="mm",
    )
    return _Displacements(prof)


# ----------------------------------------------------------------------
# style.py — no import-time side effects; opt-in apply()/theme()
# ----------------------------------------------------------------------


def test_palette_and_named_colors():
    assert isinstance(style.PALETTE, list)
    assert all(isinstance(c, str) and c.startswith("#") for c in style.PALETTE)
    assert style.BLUE in style.PALETTE
    assert style.GRAY in style.PALETTE


def test_apply_sets_rcparams_globally():
    before = matplotlib.rcParams["axes.grid"]
    try:
        matplotlib.rcParams["axes.grid"] = False
        style.apply()
        assert matplotlib.rcParams["axes.grid"] is True
        # palette becomes the prop cycle
        cycle = matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]
        assert cycle == style.PALETTE
    finally:
        matplotlib.rcParams["axes.grid"] = before


def test_theme_is_scoped_and_restored():
    matplotlib.rcParams["axes.spines.top"] = True
    with style.theme():
        assert matplotlib.rcParams["axes.spines.top"] is False
    # restored on exit
    assert matplotlib.rcParams["axes.spines.top"] is True


# ----------------------------------------------------------------------
# Pure plotters
# ----------------------------------------------------------------------


def test_drift_profile_returns_fig_ax(drift_snapshot):
    fig, ax = drift_profile(drift_snapshot)
    assert fig is ax.figure
    # value on x, elevation on y
    line = ax.lines[0]
    np.testing.assert_allclose(line.get_xdata(), [0.012, 0.018, 0.009, 0.0])
    np.testing.assert_allclose(line.get_ydata(), [12.0, 8.0, 4.0, 0.0])


def test_drift_profile_axis_label_dimensionless(drift_snapshot):
    _, ax = drift_profile(drift_snapshot)
    assert ax.get_xlabel() == "Drift"
    assert ax.get_ylabel() == "Elevation"


def test_drift_profile_story_yticks(drift_snapshot):
    _, ax = drift_profile(drift_snapshot)
    labels = [t.get_text() for t in ax.get_yticklabels()]
    assert labels == ["Story3", "Story2", "Story1", "Base"]


def test_drift_profile_forwards_direction_and_step(drift_snapshot):
    drift_profile(drift_snapshot, direction="Y", step="Min")
    assert drift_snapshot.last_call == {"direction": "Y", "step": "Min"}


def test_ax_injection_reuses_axes(drift_snapshot):
    fig, ax = plt.subplots()
    fig2, ax2 = drift_profile(drift_snapshot, ax=ax)
    assert ax2 is ax
    assert fig2 is fig
    assert len(ax.lines) == 1


def test_overlay_two_series_on_one_ax(drift_snapshot):
    fig, ax = plt.subplots()
    drift_profile(drift_snapshot, ax=ax, label="A", color=style.PALETTE[0])
    drift_profile(drift_snapshot, ax=ax, label="B", color=style.PALETTE[1])
    assert len(ax.lines) == 2


def test_displacement_profile_label_and_units(disp_snapshot):
    fig, ax = displacement_profile(disp_snapshot, label="P1", direction="X")
    assert ax.get_xlabel() == "Displacement X [mm]"
    assert disp_snapshot.last_call["label"] == "P1"
    # label used as series legend label
    assert ax.lines[0].get_label() == "P1"


def test_line_kwargs_passthrough(disp_snapshot):
    _, ax = displacement_profile(
        disp_snapshot, label="P1", linewidth=3.0, linestyle="--"
    )
    assert ax.lines[0].get_linewidth() == 3.0
    assert ax.lines[0].get_linestyle() == "--"


def test_no_show_side_effect(drift_snapshot, monkeypatch):
    called = {"show": False}
    monkeypatch.setattr(plt, "show", lambda *a, **k: called.__setitem__("show", True))
    drift_profile(drift_snapshot)
    assert called["show"] is False


# ----------------------------------------------------------------------
# Plot sugar composite (accepts snapshot OR fetches via _parent.results)
# ----------------------------------------------------------------------


class _FakeResults:
    def __init__(self, drifts, disps):
        self._drifts = drifts
        self._disps = disps
        self.calls = []

    def story_drifts(self, *, case=None, combo=None):
        self.calls.append(("drifts", case, combo))
        return self._drifts

    def displacements(self, *, case=None, combo=None):
        self.calls.append(("disps", case, combo))
        return self._disps


class _FakeSession:
    def __init__(self, results):
        self.results = results


def test_plot_drift_with_snapshot(drift_snapshot):
    session = _FakeSession(_FakeResults(drift_snapshot, None))
    plot = Plot(session)
    fig, ax = plot.drift(drift_snapshot, direction="X")
    assert fig is ax.figure
    # snapshot in hand -> no fetch
    assert session.results.calls == []


def test_plot_drift_fetches_via_results(drift_snapshot):
    results = _FakeResults(drift_snapshot, None)
    plot = Plot(_FakeSession(results))
    fig, ax = plot.drift(case="EQx", direction="X")
    assert results.calls == [("drifts", "EQx", None)]
    assert len(ax.lines) == 1


def test_plot_displacement_fetches_via_results(disp_snapshot):
    results = _FakeResults(None, disp_snapshot)
    plot = Plot(_FakeSession(results))
    fig, ax = plot.displacement(label="P1", combo="1.2D+1.6L")
    assert results.calls == [("disps", None, "1.2D+1.6L")]
    assert ax.get_xlabel() == "Displacement X [mm]"
