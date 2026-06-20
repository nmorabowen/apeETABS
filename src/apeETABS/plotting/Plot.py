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

from . import profiles

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
