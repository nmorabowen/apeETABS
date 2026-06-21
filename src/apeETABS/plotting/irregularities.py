"""Pure irregularity plots — snapshot in, ``(fig, ax)`` / ``(fig, axes)`` out.

P9 seismic-irregularity plotters following the ADR 0004 contract (and the
``forces.py`` style): the only input is a results snapshot already in report
units. Each plotter takes the SNAPSHOT and calls the snapshot's own compute
method internally (``.eccentricity()`` / ``.ratios()`` / ``.soft_story()`` /
``.mass_check()``), so the ``e.plot`` sugar stays a thin fetch-and-forward.

These functions never touch the session or ``SapModel``, never call
``plt.show()``, and never mutate global rcParams — unit-testable headless.
``ax=None`` creates a fresh figure; a given ``ax`` is drawn on and its parent
figure returned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..criteria import ASCE7, IrregularityCriteria

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


def _new_axes(ax: "Axes | None") -> tuple["Figure", "Axes"]:
    """Return ``(fig, ax)``, creating a new figure only when ``ax is None``."""
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots()
        return fig, ax
    return ax.figure, ax


def _new_pair(axes: Any) -> tuple["Figure", Any]:
    """Return ``(fig, axes)`` for a 1x2 panel layout."""
    import matplotlib.pyplot as plt

    if axes is None:
        fig, axes = plt.subplots(1, 2)
        return fig, axes
    return axes[0].figure, axes


def _length_label(snap: Any) -> str:
    """A length-unit axis label from the snapshot's baked coordinate units."""
    units = getattr(snap, "units", {}) or {}
    for col in ("XCM", "YCM", "XCR", "YCR"):
        if units.get(col):
            return units[col]
    return ""


# ----------------------------------------------------------------------
# Center of mass / center of rigidity (plan scatter)
# ----------------------------------------------------------------------


def center_mass_rigidity(
    snap: Any,
    *,
    ax: "Axes | None" = None,
    annotate: int = 4,
) -> tuple["Figure", "Axes"]:
    """Plan scatter of CM vs CR per story with the eccentricity segment.

    ``snap`` is a :class:`~apeETABS.results.CentersMassRigidity.CentersMassRigidity`
    snapshot; CM ``(XCM,YCM)`` are filled markers, CR ``(XCR,YCR)`` hollow, and
    a thin dashed segment connects each story's CM<->CR. Up to ``annotate`` story
    labels are drawn. Equal aspect; axis labels in length units. Returns
    ``(fig, ax)``.
    """
    fig, ax = _new_axes(ax)

    df = snap.df
    xcm = df["XCM"].to_numpy(dtype=float)
    ycm = df["YCM"].to_numpy(dtype=float)
    xcr = df["XCR"].to_numpy(dtype=float)
    ycr = df["YCR"].to_numpy(dtype=float)
    stories = [str(s) for s in df["Story"].tolist()]

    # Eccentricity segments first so markers sit on top.
    for i in range(len(stories)):
        ax.plot(
            [xcm[i], xcr[i]], [ycm[i], ycr[i]],
            color="gray", linestyle="--", linewidth=0.8, zorder=1,
        )

    ax.scatter(xcm, ycm, marker="o", color="#1f4e79", label="CM", zorder=3)
    ax.scatter(
        xcr, ycr, marker="o", facecolors="none", edgecolors="#c0504d",
        label="CR", zorder=3,
    )

    for i in range(min(annotate, len(stories))):
        ax.annotate(
            stories[i], (xcm[i], ycm[i]),
            textcoords="offset points", xytext=(4, 4), fontsize=8,
        )

    unit = _length_label(snap)
    suffix = f" [{unit}]" if unit else ""
    ax.set_xlabel(f"X{suffix}")
    ax.set_ylabel(f"Y{suffix}")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend()
    return fig, ax


# ----------------------------------------------------------------------
# Torsional irregularity (ratio vs elevation)
# ----------------------------------------------------------------------


def torsional_irregularity(
    snap: Any,
    *,
    direction: str = "X",
    criteria: IrregularityCriteria = ASCE7,
    step: str = "Max",
    ax: "Axes | None" = None,
) -> tuple["Figure", "Axes"]:
    """Torsional max/avg ratio vs elevation with 1a/1b reference lines.

    ``snap`` is a
    :class:`~apeETABS.results.TorsionIrregularity.TorsionIrregularity` snapshot;
    this calls ``snap.ratios(direction=..., criteria=..., step=...)`` internally.
    Vertical reference lines at ``criteria.torsion_1a``/``torsion_1b``; stories
    flagged ``torsion_1b`` are red, ``torsion_1a`` (only) orange. Returns
    ``(fig, ax)``.
    """
    fig, ax = _new_axes(ax)

    data = snap.ratios(direction=direction, criteria=criteria, step=step)
    ratio = data["ratio"].to_numpy(dtype=float)
    elev = data["Elevation"].to_numpy(dtype=float)

    ax.plot(ratio, elev, marker=".", linewidth=1.0, color="#1f4e79",
            drawstyle="steps-pre")

    ax.axvline(criteria.torsion_1a, color="orange", linestyle="--", linewidth=1.0,
               label=f"1a ({criteria.torsion_1a})")
    ax.axvline(criteria.torsion_1b, color="red", linestyle="--", linewidth=1.0,
               label=f"1b ({criteria.torsion_1b})")

    only_1a = data["torsion_1a"].to_numpy(bool) & ~data["torsion_1b"].to_numpy(bool)
    is_1b = data["torsion_1b"].to_numpy(bool)
    if only_1a.any():
        ax.scatter(ratio[only_1a], elev[only_1a], color="orange", zorder=3)
    if is_1b.any():
        ax.scatter(ratio[is_1b], elev[is_1b], color="red", zorder=3)

    ax.set_xlabel(r"$\delta_{max}/\delta_{avg}$")
    ax.set_ylabel("Elevation")
    ax.legend()
    return fig, ax


# ----------------------------------------------------------------------
# Soft story (stiffness + adjacent ratio, 1x2)
# ----------------------------------------------------------------------


def soft_story(
    snap: Any,
    *,
    direction: str = "X",
    criteria: IrregularityCriteria = ASCE7,
    ax: Any = None,
) -> tuple["Figure", Any]:
    """Two-panel soft-story plot. Returns ``(fig, axes)`` (a 1x2 array).

    ``snap`` is a :class:`~apeETABS.results.StoryStiffness.StoryStiffness`
    snapshot; this calls ``snap.soft_story(direction=..., criteria=...)``
    internally. Left panel: stiffness vs elevation. Right panel:
    ``ratio_adjacent`` vs elevation with vertical lines at the 1a/1b adjacent
    thresholds (0.70/0.60); flagged stories colored (1b red, 1a-only orange).
    """
    fig, axes = _new_pair(ax)

    data = snap.soft_story(direction=direction, criteria=criteria)
    elev = data["Elevation"].to_numpy(dtype=float)
    stiff = data["stiffness"].to_numpy(dtype=float)
    ratio = data["ratio_adjacent"].to_numpy(dtype=float)
    only_1a = data["soft_1a"].to_numpy(bool) & ~data["soft_1b"].to_numpy(bool)
    is_1b = data["soft_1b"].to_numpy(bool)

    # Left: stiffness vs elevation.
    axes[0].plot(stiff, elev, marker=".", linewidth=1.0, color="#1f4e79")
    unit = (getattr(snap, "units", {}) or {}).get(_stiff_col(direction), "")
    suffix = f" [{unit}]" if unit else ""
    axes[0].set_xlabel(f"Stiffness {str(direction).upper()}{suffix}")
    axes[0].set_ylabel("Elevation")

    # Right: ratio_adjacent vs elevation with thresholds.
    axes[1].plot(ratio, elev, marker=".", linewidth=1.0, color="#1f4e79")
    axes[1].axvline(criteria.soft_1a_adjacent, color="orange", linestyle="--",
                    linewidth=1.0, label=f"1a ({criteria.soft_1a_adjacent})")
    axes[1].axvline(criteria.soft_1b_adjacent, color="red", linestyle="--",
                    linewidth=1.0, label=f"1b ({criteria.soft_1b_adjacent})")
    if only_1a.any():
        axes[1].scatter(ratio[only_1a], elev[only_1a], color="orange", zorder=3)
    if is_1b.any():
        axes[1].scatter(ratio[is_1b], elev[is_1b], color="red", zorder=3)
    axes[1].set_xlabel(r"$K_i / K_{above}$")
    axes[1].set_ylabel("Elevation")
    axes[1].legend()

    return fig, axes


def _stiff_col(direction: str) -> str:
    return "StiffY" if str(direction).upper() == "Y" else "StiffX"


# ----------------------------------------------------------------------
# Mass irregularity (mass barh + ratio overlay, 1x2)
# ----------------------------------------------------------------------


def mass_irregularity(
    snap: Any,
    *,
    criteria: IrregularityCriteria = ASCE7,
    mass_col: str = "MassX",
    ax: Any = None,
) -> tuple["Figure", Any]:
    """Two-panel mass-irregularity plot. Returns ``(fig, axes)`` (a 1x2 array).

    ``snap`` is a
    :class:`~apeETABS.results.CentersMassRigidity.CentersMassRigidity` snapshot;
    this calls ``snap.mass_check(criteria, mass_col=...)`` internally. Left
    panel: ``barh`` of story mass vs elevation (irregular stories highlighted).
    Right panel: ratio-to-heavier-neighbor vs elevation with a
    ``criteria.mass_ratio`` reference line.
    """
    fig, axes = _new_pair(ax)

    data = snap.mass_check(criteria, mass_col=mass_col)
    elev = data["Elevation"].to_numpy(dtype=float)
    mass = data["mass"].to_numpy(dtype=float)
    irregular = data["irregular"].to_numpy(bool)

    # Heavier-neighbor ratio: the larger of (ratio_above, ratio_below) per story
    # (i.e. how many times heavier this story is vs its lighter neighbor). NaNs
    # (no adjacent) are ignored by nanmax.
    import numpy as np

    ra = data["ratio_above"].to_numpy(dtype=float)
    rb = data["ratio_below"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        ratio_neighbor = np.nanmax(np.vstack([ra, rb]), axis=0)

    colors = ["#c0504d" if flag else "#7f7f7f" for flag in irregular]
    height = _bar_height(elev)
    axes[0].barh(elev, mass, height=height, color=colors, alpha=0.7)
    axes[0].set_xlabel(f"Mass ({mass_col})")
    axes[0].set_ylabel("Elevation")

    axes[1].plot(ratio_neighbor, elev, marker=".", linewidth=1.0, color="#1f4e79")
    axes[1].axvline(criteria.mass_ratio, color="red", linestyle="--",
                    linewidth=1.0, label=f"mass ({criteria.mass_ratio})")
    if irregular.any():
        axes[1].scatter(ratio_neighbor[irregular], elev[irregular], color="#c0504d",
                        zorder=3)
    axes[1].set_xlabel("mass / lighter neighbor")
    axes[1].set_ylabel("Elevation")
    axes[1].legend()

    return fig, axes


def _bar_height(elev: Any) -> float:
    """A reasonable barh height from the story spacing (fallback 1.0)."""
    import numpy as np

    elev = np.asarray(elev, dtype=float)
    if elev.size < 2:
        return 1.0
    diffs = np.abs(np.diff(np.sort(elev)))
    diffs = diffs[diffs > 0]
    return float(diffs.min() * 0.6) if diffs.size else 1.0
