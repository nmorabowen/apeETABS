"""Results — the results-extraction composite (ADR 0003, Layer B).

A factory of self-contained, report-unit-baked snapshots. It owns no data of
its own: each method reads the relevant display table through
``self._parent.tables``, resolves the case/combo, bakes units via
``self._parent.units``, attaches elevations via ``self._parent.stories``, and
returns a detached dataclass (no live COM reference).

Registered on the session as ``e.results`` (wired into ``_COMPOSITES`` by a
later stage; this file does not edit ``_core``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .Displacements import Displacements
from .StoryDrifts import StoryDrifts

if TYPE_CHECKING:
    from .._session import _SessionBase


class Results:
    """Factory of detached result snapshots for the connected model."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    def displacements(
        self, *, case: str | None = None, combo: str | None = None
    ) -> Displacements:
        """Joint displacements for exactly one ``case=`` or ``combo=``.

        Example:
            >>> d = e.results.displacements(case="EQX")
            >>> d.peak(direction="X")
        """
        return Displacements.from_table(self._parent, case=case, combo=combo)

    def story_drifts(
        self, *, case: str | None = None, combo: str | None = None
    ) -> StoryDrifts:
        """Story drifts for exactly one ``case=`` or ``combo=``.

        Example:
            >>> s = e.results.story_drifts(case="EQX")
            >>> s.exceeds(0.02)
        """
        return StoryDrifts.from_table(self._parent, case=case, combo=combo)
