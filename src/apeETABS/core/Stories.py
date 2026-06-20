"""Stories composite — story geometry and elevation mapping.

This is the collaborator that, by composition, replaces the old
``modelResults_utilities`` mixin. Results objects do not inherit elevation
logic; they hold the session and call ``self._parent.stories.map_elevation(df)``.

Story data is fetched once and cached; call :meth:`refresh` after the model
changes in ETABS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..errors import ok

if TYPE_CHECKING:
    from .._session import _SessionBase

# Table + columns holding the tower base story (name/elevation).
_BASE_TABLE = "Tower and Base Story Definitions"
_BASE_NAME_COL = "BSName"
_BASE_ELEV_COL = "BSElev"


@dataclass
class StoryTable:
    """Typed snapshot of the model's stories (top story first, base last).

    ``names``/``elevations`` include the base level as the final entry, so
    ``elevations`` spans roof down to base — the natural axis for plots.
    """

    base_name: str
    base_elevation: float
    names: list[str]
    elevations: np.ndarray              # one per name, base included
    heights: np.ndarray                 # per story (no base entry)
    is_master: list[bool] = field(default_factory=list)
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def mapping(self) -> dict[str, float]:
        """``{story_name: elevation}`` including the base level."""
        return dict(zip(self.names, self.elevations.tolist()))


class Stories:
    """Story geometry, elevation mapping, and step-axis helpers."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent
        self._cache: StoryTable | None = None

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    @property
    def data(self) -> StoryTable:
        """The cached :class:`StoryTable` (built on first access)."""
        if self._cache is None:
            self._cache = self._build()
        return self._cache

    def refresh(self) -> "Stories":
        """Drop the cache so the next access re-reads from ETABS."""
        self._cache = None
        return self

    @property
    def mapping(self) -> dict[str, float]:
        """``{story_name: elevation}`` including the base level."""
        return self.data.mapping

    @property
    def elevations(self) -> np.ndarray:
        """Elevations (one per story, base included), roof→base order."""
        return self.data.elevations

    @property
    def names(self) -> list[str]:
        return self.data.names

    @property
    def table(self) -> pd.DataFrame:
        """Stories as a DataFrame (Story, Elevation, Height, IsMaster)."""
        return self.data.frame

    # ------------------------------------------------------------------
    # Elevation mapping (the ex-mixin behavior, now via composition)
    # ------------------------------------------------------------------

    def map_elevation(self, df: pd.DataFrame, *, story_col: str = "Story") -> pd.DataFrame:
        """Add an ``Elevation`` column by mapping ``story_col`` to elevations.

        Returns the same DataFrame (mutated in place) for convenience.
        """
        df["Elevation"] = df[story_col].map(self.mapping)
        return df

    def map_elevation_top_bottom(
        self, df: pd.DataFrame, *, story_col: str = "Story", location_col: str = "Location"
    ) -> pd.DataFrame:
        """Map elevations distinguishing ``Top``/``Bottom`` row locations.

        ``Top`` rows take the story's own elevation; ``Bottom`` rows take
        the elevation of the story below (the lowest story uses its own).
        """
        mapping = self.mapping
        ordered = sorted(mapping.items(), key=lambda kv: kv[1], reverse=True)
        lower = {
            ordered[i][0]: mapping[ordered[i + 1][0]] for i in range(len(ordered) - 1)
        }
        lower[ordered[-1][0]] = mapping[ordered[-1][0]]  # lowest -> itself

        df["Elevation"] = df[story_col].map(mapping)
        bottom = df[location_col] == "Bottom"
        df.loc[bottom, "Elevation"] = df.loc[bottom, story_col].map(lower)
        return df

    def step_axis(self, *, scale: float = 1.0) -> np.ndarray:
        """Stacked elevations for step-wise (story-shear style) plots.

        Each interior elevation is repeated so values can be drawn as a
        staircase. Divide by ``scale`` to express in report units.
        """
        return np.flip(np.repeat(self.elevations, 2)[1:-1] / scale)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> StoryTable:
        sap = self._parent.SapModel
        # GetStories_2 out order:
        # BaseElevation, NumberStories, StoryNames, StoryElevations,
        # StoryHeights, IsMasterStory, SimilarToStory, SpliceAbove,
        # SpliceHeight, color, ret
        (base_elev, _num, names, elevs, heights, is_master,
         _similar, _splice_above, _splice_h, _color) = ok(
            sap.Story.GetStories_2(0, 0, [], [], [], [], [], [], [], []),
            "GetStories_2",
        )

        base_name, base_elev = self._base_story(default_elev=float(base_elev))

        names = [base_name, *list(names)]
        elevations = np.insert(np.asarray(elevs, dtype=float), 0, base_elev)
        heights = np.asarray(heights, dtype=float)

        frame = pd.DataFrame(
            {
                "Story": list(names),
                "Elevation": elevations,
                "IsMaster": [False, *list(is_master)],
            }
        )
        return StoryTable(
            base_name=base_name,
            base_elevation=float(base_elev),
            names=list(names),
            elevations=elevations,
            heights=heights,
            is_master=[False, *list(is_master)],
            frame=frame,
        )

    def _base_story(self, *, default_elev: float) -> tuple[str, float]:
        """Resolve the base story name/elevation, preferring the base table."""
        try:
            df = self._parent.tables.get(_BASE_TABLE, numeric=True)
            if not df.empty and _BASE_NAME_COL in df and _BASE_ELEV_COL in df:
                return str(df[_BASE_NAME_COL].iloc[0]), float(df[_BASE_ELEV_COL].iloc[0])
        except Exception:  # noqa: BLE001 — fall back to the API value
            if self._parent._verbose:
                print(f"Could not read '{_BASE_TABLE}'; using API base elevation.")
        return "Base", default_elev
