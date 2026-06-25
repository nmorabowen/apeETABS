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

from .CentersMassRigidity import CentersMassRigidity
from .Displacements import Displacements
from .Reactions import Reactions
from .StoryDrifts import StoryDrifts
from .StoryForces import StoryForces
from .StoryStiffness import StoryStiffness
from .TorsionIrregularity import TorsionIrregularity
from .WallForces import WallForces

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

    def reactions(
        self, *, case: str | None = None, combo: str | None = None
    ) -> Reactions:
        """Joint reactions for exactly one ``case=`` or ``combo=``.

        The ETABS side of the ADR 0009 solve cross-check.

        Example:
            >>> r = e.results.reactions(case="Dead")
            >>> r.by_joint()["12"]            # (Fx,Fy,Fz,Mx,My,Mz)
        """
        return Reactions.from_table(self._parent, case=case, combo=combo)

    def story_drifts(
        self, *, case: str | None = None, combo: str | None = None
    ) -> StoryDrifts:
        """Story drifts for exactly one ``case=`` or ``combo=``.

        Example:
            >>> s = e.results.story_drifts(case="EQX")
            >>> s.exceeds(0.02)
        """
        return StoryDrifts.from_table(self._parent, case=case, combo=combo)

    def story_forces(
        self, *, case: str | None = None, combo: str | None = None
    ) -> StoryForces:
        """Story forces for exactly one ``case=`` or ``combo=``.

        Example:
            >>> f = e.results.story_forces(case="EQX")
            >>> f.shear(direction="X")        # cumulative story shear profile
            >>> f.story_force(direction="X")  # per-story force profile
        """
        return StoryForces.from_table(self._parent, case=case, combo=combo)

    def wall_forces(
        self, *, design_parameters: dict[str, float] | None = None
    ) -> WallForces:
        """Pier design forces across all combinations.

        Args:
            design_parameters: Optional ``{'overstrength',
                'dynamic_amplification'}`` -> ``shear_amplification`` metadata
                (``min(3, overstrength*dynamic_amplification)``).

        Example:
            >>> w = e.results.wall_forces(
            ...     design_parameters={"overstrength": 1.25,
            ...                        "dynamic_amplification": 1.5})
            >>> w.envelope("P1")
        """
        return WallForces.from_table(
            self._parent, design_parameters=design_parameters
        )

    def centers_mass_rigidity(self) -> CentersMassRigidity:
        """Centers of mass/rigidity (+ masses) for every story (no case/combo).

        Example:
            >>> c = e.results.centers_mass_rigidity()
            >>> c.eccentricity()                  # |XCM-XCR|, |YCM-YCR| per story
            >>> c.mass_check()                    # ASCE 7 vertical Type 2 (mass)
        """
        return CentersMassRigidity.from_table(self._parent)

    def story_stiffness(
        self, *, case: str | None = None, combo: str | None = None
    ) -> StoryStiffness:
        """Lateral story stiffness for exactly one ``case=`` or ``combo=``.

        Example:
            >>> s = e.results.story_stiffness(case="EQX")
            >>> s.soft_story(direction="X")       # ASCE 7 vertical Type 1a/1b
        """
        return StoryStiffness.from_table(self._parent, case=case, combo=combo)

    def torsion_irregularity(
        self, *, case: str | None = None, combo: str | None = None
    ) -> TorsionIrregularity:
        """Torsional max/avg drift ratios for exactly one ``case=``/``combo=``.

        Example:
            >>> t = e.results.torsion_irregularity(case="EQX")
            >>> t.ratios(direction="X")           # ASCE 7 horizontal Type 1a/1b
        """
        return TorsionIrregularity.from_table(self._parent, case=case, combo=combo)
