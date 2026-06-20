"""Plot — the ``e.plot`` session sugar composite (ADR 0004 §4).

A session-bound composite: for one-liners each method accepts **either** a
snapshot in hand **or** selection kwargs (``case=`` / ``combo=``). In the
latter case it fetches via ``self._parent.results`` and forwards to the pure
function. The pure functions in :mod:`apeETABS.plotting.profiles` stay
snapshot-only (Layer C stays clean); only this session-bound composite is
allowed to fetch, since it already holds ``_parent``.

    e.plot.drift(drift, direction="X")          # snapshot in hand
    e.plot.drift(case="EQx", direction="X")     # sugar: fetch, then plot
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import forces, profiles

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from .._session import _SessionBase


class Plot:
    """Session sugar over the pure profile plotters."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Fetch helper (the one contained place the plotting sugar reaches the
    # session — see ADR 0004 §4).
    # ------------------------------------------------------------------

    def _resolve_drifts(self, snapshot, *, case, combo):
        if snapshot is not None:
            return snapshot
        return self._parent.results.story_drifts(case=case, combo=combo)

    def _resolve_displacements(self, snapshot, *, case, combo):
        if snapshot is not None:
            return snapshot
        return self._parent.results.displacements(case=case, combo=combo)

    def _resolve_story_forces(self, snapshot, *, case, combo):
        if snapshot is not None:
            return snapshot
        return self._parent.results.story_forces(case=case, combo=combo)

    def _resolve_wall_forces(self, snapshot, *, design_parameters):
        if snapshot is not None:
            return snapshot
        return self._parent.results.wall_forces(design_parameters=design_parameters)

    # ------------------------------------------------------------------
    # Sugar methods
    # ------------------------------------------------------------------

    def drift(
        self,
        snapshot: Any = None,
        *,
        case: str | None = None,
        combo: str | None = None,
        **kw: Any,
    ) -> tuple["Figure", "Axes"]:
        """Plot a drift profile from a snapshot or a fetched selection."""
        snap = self._resolve_drifts(snapshot, case=case, combo=combo)
        return profiles.drift_profile(snap, **kw)

    def displacement(
        self,
        snapshot: Any = None,
        *,
        label: str,
        case: str | None = None,
        combo: str | None = None,
        **kw: Any,
    ) -> tuple["Figure", "Axes"]:
        """Plot a displacement profile from a snapshot or a fetched selection."""
        snap = self._resolve_displacements(snapshot, case=case, combo=combo)
        return profiles.displacement_profile(snap, label=label, **kw)

    # ------------------------------------------------------------------
    # Force sugar (StoryForces / WallForces)
    # ------------------------------------------------------------------

    def story_shear(
        self,
        snapshot: Any = None,
        *,
        case: str | None = None,
        combo: str | None = None,
        **kw: Any,
    ) -> tuple["Figure", "Axes"]:
        """Plot a stepped story-shear profile from a snapshot or fetched selection."""
        snap = self._resolve_story_forces(snapshot, case=case, combo=combo)
        return forces.story_shear(snap, **kw)

    def story_forces(
        self,
        snapshot: Any = None,
        *,
        case: str | None = None,
        combo: str | None = None,
        **kw: Any,
    ) -> tuple["Figure", "Axes"]:
        """Plot per-story forces (barh + line) from a snapshot or fetched selection."""
        snap = self._resolve_story_forces(snapshot, case=case, combo=combo)
        return forces.story_forces(snap, **kw)

    def wall_forces(
        self,
        pier: str,
        snapshot: Any = None,
        *,
        design_parameters: Any = None,
        **kw: Any,
    ) -> tuple["Figure", Any]:
        """Plot the P/M/V triptych for a pier from a snapshot or fetched selection."""
        snap = self._resolve_wall_forces(snapshot, design_parameters=design_parameters)
        return forces.wall_forces(snap, pier, **kw)

    def wall_force_envelopes(
        self,
        pier: str,
        snapshot: Any = None,
        *,
        design_parameters: Any = None,
        amplification: float | None = None,
        **kw: Any,
    ) -> tuple["Figure", Any]:
        """Plot min/max pier envelopes (with amplified shear) from snapshot or fetch.

        When fetching, the shear amplification carried on the snapshot
        (``shear_amplification`` metadata) is used as the default ``amplification``.
        """
        snap = self._resolve_wall_forces(snapshot, design_parameters=design_parameters)
        if amplification is None:
            amplification = getattr(snap, "shear_amplification", None)
        return forces.wall_force_envelopes(snap, pier, amplification=amplification, **kw)
