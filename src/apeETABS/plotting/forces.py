"""Pure force plots — snapshot in, ``(fig, ax)`` out (ADR 0004 §1, §5).

Ports of the proven old ``modelResults_storyForces`` / ``modelResults_wallForces``
plots, adapted to the ADR 0004 contract: the only input is a results snapshot
already in report units (Layer B). These functions never touch the session or
``SapModel``, never call ``plt.show()``, and never mutate global rcParams — so
they are unit testable on synthetic snapshots without a display.

Composition is via ``ax``: ``ax=None`` creates a fresh figure; a given ``ax``
(or array of axes) is drawn on and its parent figure returned. The stepped
elevation axis is carried *on the snapshot* (``StoryForces.shear()`` returns a
``Profile`` whose ``elevation``/``value`` are already stacked top/bottom); the
pure functions only mirror and render it. Wall plots read ``snapshot.df``
(``Elevation`` column) directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


# Force triptych panel definitions (axial / moment / shear), mirroring the old
# wall-force plots' P / M3 / V2 layout.
_WALL_PANELS = (
    {"data": "P", "xlabel": "Axial Force", "symbol": "P_u"},
    {"data": "M3", "xlabel": "Bending Moment", "symbol": "M_u"},
    {"data": "V2", "xlabel": "Shear Force", "symbol": "V_u"},
)


def _new_axes(ax: "Axes | None") -> tuple["Figure", "Axes"]:
    """Return ``(fig, ax)``, creating a new figure only when ``ax is None``."""
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots()
        return fig, ax
    return ax.figure, ax


def _new_triptych(axes: Any) -> tuple["Figure", Any]:
    """Return ``(fig, axes)`` for a 1x3 panel layout.

    ``axes=None`` creates a fresh ``(fig, [P, M3, V2])`` row; a given array of
    axes is drawn on and its parent figure returned.
    """
    import matplotlib.pyplot as plt

    if axes is None:
        fig, axes = plt.subplots(1, 3)
        return fig, axes
    return axes[0].figure, axes


def _value_label(prefix: str, unit: str | None) -> str:
    unit = unit or ""
    return f"{prefix} [{unit}]" if unit else prefix


# ----------------------------------------------------------------------
# Story forces
# ----------------------------------------------------------------------


def story_shear(
    snapshot: Any,
    *,
    direction: str = "X",
    ax: "Axes | None" = None,
    label: str | None = None,
    step: str = "Max",
    **line_kwargs: Any,
) -> tuple["Figure", "Axes"]:
    """Plot a stepped, mirrored cumulative story-shear profile over elevation.

    ``snapshot`` is a ``StoryForces`` snapshot; ``snapshot.shear(...)`` returns a
    :class:`~apeETABS.results.Profile` whose ``elevation``/``value`` are already
    stacked top/bottom (the staircase). The shear is symmetric, so both ``+v``
    and ``-v`` are drawn (mirrored ±), as in the old code.
    """
    fig, ax = _new_axes(ax)

    profile = snapshot.shear(direction=direction, step=step)
    series_label = label if label is not None else profile.label

    ax.plot(profile.value, profile.elevation, label=series_label, **line_kwargs)
    # Mirror without a second legend entry; reuse the same color when given.
    mirror_kw = dict(line_kwargs)
    line_color = ax.lines[-1].get_color()
    mirror_kw.setdefault("color", line_color)
    ax.plot(-profile.value, profile.elevation, **mirror_kw)

    ax.set_xlabel(_value_label(f"Story Shear {direction}", getattr(profile, "unit", "")))
    ax.set_ylabel("Elevation")

    if series_label is not None:
        ax.legend()
    return fig, ax


def story_forces(
    snapshot: Any,
    *,
    direction: str = "X",
    ax: "Axes | None" = None,
    label: str | None = None,
    step: str = "Max",
    **line_kwargs: Any,
) -> tuple["Figure", "Axes"]:
    """Plot per-story forces as a mirrored ``barh`` with a line overlay.

    ``snapshot`` is a ``StoryForces`` snapshot; ``snapshot.story_force(...)``
    returns a per-story :class:`~apeETABS.results.Profile` (the diff of the
    cumulative shear). Bars are drawn for ±force (symmetric) with a thin line
    overlay, mirroring the old ``barh`` + line style.
    """
    fig, ax = _new_axes(ax)

    profile = snapshot.story_force(direction=direction, step=step)
    series_label = label if label is not None else profile.label

    elevation = profile.elevation
    value = profile.value

    color = line_kwargs.pop("color", None)
    alpha = line_kwargs.pop("alpha", 0.5)
    bars = ax.barh(elevation, value, align="center", alpha=alpha, color=color)
    bar_color = bars[0].get_facecolor() if len(bars) else color
    ax.barh(elevation, -value, align="center", alpha=alpha, color=bar_color)

    line_kwargs.setdefault("linewidth", 0.5)
    line_kwargs.setdefault("linestyle", "--")
    line_kwargs.setdefault("marker", ".")
    ax.plot(value, elevation, color=bar_color, label=series_label, **line_kwargs)
    ax.plot(-value, elevation, color=bar_color, **line_kwargs)

    ax.set_xlabel(_value_label(f"Story Force {direction}", getattr(profile, "unit", "")))
    ax.set_ylabel("Elevation")

    if series_label is not None:
        ax.legend()
    return fig, ax


# ----------------------------------------------------------------------
# Wall (pier) forces
# ----------------------------------------------------------------------


def wall_forces(
    snapshot: Any,
    pier: str,
    *,
    ax: Any = None,
    **line_kwargs: Any,
) -> tuple["Figure", Any]:
    """Plot a P / M3 / V2 triptych for one pier, one line per combo over height.

    ``snapshot`` is a ``WallForces`` snapshot; ``snapshot.pier(pier)`` returns the
    rows for that pier (with ``Combo``, ``Elevation``, ``P``, ``M3``, ``V2``).
    Returns ``(fig, axes)`` with the three panels.
    """
    from .style import PALETTE

    fig, axes = _new_triptych(ax)

    df = snapshot.pier(pier)
    combos = list(dict.fromkeys(df["Combo"].tolist()))
    units = getattr(snapshot, "units", {}) or {}

    line_kwargs.setdefault("marker", ".")
    line_kwargs.setdefault("linewidth", 0.5)

    for color_idx, combo in enumerate(combos):
        combo_df = df[df["Combo"] == combo]
        color = PALETTE[color_idx % len(PALETTE)]
        for ax_idx, panel in enumerate(_WALL_PANELS):
            axes[ax_idx].plot(
                combo_df[panel["data"]],
                combo_df["Elevation"],
                label=combo,
                color=color,
                **line_kwargs,
            )

    for ax_idx, panel in enumerate(_WALL_PANELS):
        panel_ax = axes[ax_idx]
        panel_ax.set_xlabel(
            _value_label(f"{panel['xlabel']} ${panel['symbol']}$", units.get(panel["data"]))
        )
        panel_ax.set_ylabel("Elevation")

    if combos:
        axes[0].legend()
    axes[0].figure.suptitle(f"Design Forces - Wall: {pier}")
    return fig, axes


def wall_force_envelopes(
    snapshot: Any,
    pier: str,
    *,
    amplification: float | None = None,
    ax: Any = None,
    **line_kwargs: Any,
) -> tuple["Figure", Any]:
    """Plot min/max P / M3 / V2 envelopes for one pier, with an amplified shear.

    ``snapshot.envelope(pier)`` returns ``{'P': df, 'M3': df, 'V2': df}`` where
    each frame is min/max indexed by ``Elevation``. If ``amplification`` is given
    (and ``!= 1``) an amplified shear overlay is added to the V2 panel — the
    factor is analysis metadata (``shear_amplification``), never baked into the
    snapshot ``df``. Returns ``(fig, axes)``.
    """
    fig, axes = _new_triptych(ax)

    envelopes = snapshot.envelope(pier)
    units = getattr(snapshot, "units", {}) or {}

    line_kwargs.setdefault("marker", ".")
    line_kwargs.setdefault("linewidth", 1.5)

    for ax_idx, panel in enumerate(_WALL_PANELS):
        panel_ax = axes[ax_idx]
        force = panel["data"]
        env = envelopes[force]
        elev = env.index

        panel_ax.plot(env["min"], elev, color="black", label="Envelope", **line_kwargs)
        panel_ax.plot(env["max"], elev, color="black", **line_kwargs)

        if force == "V2" and amplification is not None and amplification != 1.0:
            panel_ax.plot(
                env["min"] * amplification, elev, color="blue", linestyle="--",
                marker=line_kwargs.get("marker"), linewidth=line_kwargs.get("linewidth"),
                label=f"Amplified ({amplification}x)",
            )
            panel_ax.plot(
                env["max"] * amplification, elev, color="blue", linestyle="--",
                marker=line_kwargs.get("marker"), linewidth=line_kwargs.get("linewidth"),
            )
            panel_ax.legend()

        panel_ax.set_xlabel(
            _value_label(f"{panel['xlabel']} ${panel['symbol']}$", units.get(force))
        )
        panel_ax.set_ylabel("Elevation")

    axes[0].figure.suptitle(f"Design Force Envelopes - Wall: {pier}")
    return fig, axes
