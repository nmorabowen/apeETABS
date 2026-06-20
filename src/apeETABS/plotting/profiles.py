"""Pure profile plots — snapshot in, ``(fig, ax)`` out (ADR 0004 §1, §5).

These are free functions: the only input is a results snapshot already in
report units (Layer B). They never touch the session or ``SapModel``, never
call ``plt.show()``, and never mutate global rcParams — so they are unit
testable on synthetic snapshots without a display.

Composition is via ``ax``: ``ax=None`` creates a fresh ``(fig, ax)``; a given
``ax`` is drawn on and its parent figure returned. Profiles plot value on x
and ``Elevation`` on y, with story y-ticks; axis labels come from the
snapshot's unit metadata (``snapshot.units`` / ``Profile.unit``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


def _draw_profile(
    profile: Any,
    *,
    ax: "Axes | None",
    label: str | None,
    value_axis_label: str,
    **line_kwargs: Any,
) -> tuple["Figure", "Axes"]:
    """Shared profile renderer: value on x, ``Elevation`` on y, story ticks.

    ``profile`` is a pinned :class:`~apeETABS.results.Profile`-shaped object
    (``elevation``, ``value``, ``stories``, ``label``, ``unit``).
    """
    fig, ax = _new_axes(ax)

    series_label = label if label is not None else profile.label
    ax.plot(profile.value, profile.elevation, label=series_label, **line_kwargs)

    # Story y-ticks at each elevation; the snapshot is roof->base ordered.
    ax.set_yticks(list(profile.elevation))
    ax.set_yticklabels(list(profile.stories))

    ax.set_xlabel(value_axis_label)
    # The y axis is elevation in report length units; Profile.unit annotates
    # the *value* axis, so the elevation axis keeps a plain "Elevation" label.
    ax.set_ylabel("Elevation")

    if series_label is not None:
        ax.legend()
    return fig, ax


def drift_profile(
    snapshot: Any,
    *,
    direction: str = "X",
    ax: "Axes | None" = None,
    label: str | None = None,
    step: str = "Max",
    **line_kwargs: Any,
) -> tuple["Figure", "Axes"]:
    """Plot a story-drift profile (dimensionless) over elevation.

    Drift is dimensionless, so the value-axis label is simply ``"Drift"``
    (``Profile.unit`` is empty for drift). ``snapshot`` is a ``StoryDrifts``
    snapshot; the profile is taken via ``snapshot.profile(...)``.
    """
    profile = snapshot.profile(direction=direction, step=step)
    unit = getattr(profile, "unit", "") or ""
    value_axis_label = f"Drift [{unit}]" if unit else "Drift"
    return _draw_profile(
        profile,
        ax=ax,
        label=label,
        value_axis_label=value_axis_label,
        **line_kwargs,
    )


def displacement_profile(
    snapshot: Any,
    *,
    label: str,
    direction: str = "X",
    ax: "Axes | None" = None,
    step: str = "Max",
    **line_kwargs: Any,
) -> tuple["Figure", "Axes"]:
    """Plot a joint-displacement profile over elevation.

    ``label`` selects the joint/point whose profile to draw (forwarded to
    ``snapshot.profile(label=...)``) and also names the series. Axis units are
    read from the resulting ``Profile.unit`` (report length units).
    """
    profile = snapshot.profile(label=label, direction=direction, step=step)
    unit = getattr(profile, "unit", "") or ""
    value_axis_label = (
        f"Displacement {direction} [{unit}]" if unit else f"Displacement {direction}"
    )
    return _draw_profile(
        profile,
        ax=ax,
        label=label,
        value_axis_label=value_axis_label,
        **line_kwargs,
    )
