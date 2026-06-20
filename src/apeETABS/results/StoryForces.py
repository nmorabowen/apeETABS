"""StoryForces — story force/shear snapshot from the ``"Story Forces"`` table.

A self-contained, report-unit-baked view of per-story forces for one resolved
case/combo. Ports the proven numeric logic from the v0 ``modelResults_storyForces``
(cumulative story shear stacked top/bottom, per-story force via ``np.diff``) to
the new architecture: a typed ``@dataclass`` detached from the session, units
baked, axis labels from unit metadata (ADR 0002/0003). Holds no live COM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..errors import ETABSError
from . import _common
from .Profile import Profile

if TYPE_CHECKING:
    from .._session import _SessionBase

_TABLE = "Story Forces"

# ETABS column -> canonical. Tolerant: only present keys are renamed; unknown
# extras are kept untouched.
_COLUMN_MAP = {
    "Story": "Story",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "StepNumber": "StepNumber",
    "Location": "Location",
    "P": "P",
    "VX": "VX", "VY": "VY",
    "T": "T",
    "MX": "MX", "MY": "MY",
}

_REQUIRED = {"Story", "OutputCase", "Location", "VX", "VY"}

# Per-column dimension for unit baking. Forces are F, moments/torsion F·L.
_DIM_MAP = {
    "P": "force", "VX": "force", "VY": "force",
    "T": "moment", "MX": "moment", "MY": "moment",
}

_VALUE_COLS = ["P", "VX", "VY", "T", "MX", "MY"]

# direction= -> shear column.
_SHEAR_COL = {"X": "VX", "Y": "VY"}


@dataclass
class StoryForces:
    """Story forces for one case/combo, report units baked.

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units);
            force/moment columns converted to report units.
        case: The resolved ``OutputCase`` name (post fuzzy-match).
        units: ``{column: unit_label}`` for axis annotation.
    """

    df: pd.DataFrame
    case: str
    units: dict[str, str]

    # ------------------------------------------------------------------
    # Builder (called by the Results composite)
    # ------------------------------------------------------------------

    @classmethod
    def from_table(
        cls,
        parent: "_SessionBase",
        *,
        case: str | None = None,
        combo: str | None = None,
    ) -> "StoryForces":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build StoryForces. "
                f"Has the model been analyzed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        df, resolved = _common.select_case(df, name, table=_TABLE)
        labels = _common.bake_units(df, _DIM_MAP, parent)
        df = _add_top_bottom_elevation(df, parent)
        df = _common.order_roof_to_base(df)
        return cls(df=df, case=resolved, units=labels)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def shear(self, *, direction: str = "X", step: str = "Max") -> Profile:
        """Cumulative story shear vs elevation, stacked top/bottom.

        Reproduces the v0 staircase profile: the interleaved Bottom/Top shear
        VALUE array (roof->base) is paired against a SEPARATELY-built
        MONOTONIC elevation staircase, so the response plots as a clean
        story-shear step instead of zig-zagging. ``direction`` selects
        ``VX``/``VY``; ``step`` envelopes the StepType (``"Max"`` default).
        """
        col = _shear_col(direction)
        top_df, bot_df = self._top_bottom(step=step)
        top = pd.to_numeric(top_df[col], errors="coerce").to_numpy(dtype=float)
        bottom = pd.to_numeric(bot_df[col], errors="coerce").to_numpy(dtype=float)
        # Interleave bottom/top shear into the value array, roof->base.
        value = np.empty(top.size + bottom.size, dtype=float)
        value[0::2] = bottom
        value[1::2] = top
        # Build the elevation axis as a monotonic staircase aligned with the
        # roof->base value array: take the unique story elevations (incl. base)
        # in descending order and repeat each, trimming the open ends so the
        # length matches the 2*n_stories value array. Reproduces the v0
        # _get_elevations_array logic (np.repeat(...,2)[1:-1]); not flipped
        # here because the value array is already roof->base.
        elev = self._elevation_staircase(top_df, bot_df)
        return Profile(
            elevation=elev,
            value=value,
            stories=[],  # stacked axis has no 1:1 story mapping
            label=f"Shear {str(direction).upper()}",
            unit=self.units.get(col, ""),
        )

    @staticmethod
    def _elevation_staircase(
        top_df: pd.DataFrame, bot_df: pd.DataFrame
    ) -> np.ndarray:
        """Monotonic roof->base step axis aligned with the bottom/top values.

        The story elevations span roof down to base: the upper edge of each
        story is its Top elevation; the lowest story's Bottom is the base.
        Collecting Top elevations (roof->base) plus the base gives the unique
        level edges in descending order; ``np.repeat(edges, 2)[1:-1]`` yields
        the ``2*n_stories`` staircase that pairs with the interleaved
        bottom/top value array (each story's value held flat across its span).
        """
        top_elev = top_df["Elevation"].to_numpy(dtype=float)
        bot_elev = bot_df["Elevation"].to_numpy(dtype=float)
        # Level edges, roof->base: every story Top elevation, then the base
        # (the lowest story's Bottom). top_df/bot_df are roof->base ordered.
        edges = np.concatenate([top_elev, bot_elev[-1:]])
        return np.repeat(edges, 2)[1:-1]

    def story_force(self, *, direction: str = "X", step: str = "Max") -> Profile:
        """Per-story force (difference of cumulative Top shear), roof->base.

        The story force at a level is the change in cumulative Top shear from
        the level above (``np.diff`` with a leading zero at the roof).
        """
        col = _shear_col(direction)
        top_df, _bot_df = self._top_bottom(step=step)
        top = pd.to_numeric(top_df[col], errors="coerce").to_numpy(dtype=float)
        force = np.diff(top, prepend=0.0)
        stories = [str(s) for s in top_df["Story"].tolist()]
        elev = top_df["Elevation"].to_numpy(dtype=float)
        return Profile(
            elevation=elev,
            value=force,
            stories=stories,
            label=f"Story force {str(direction).upper()}",
            unit=self.units.get(col, ""),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _selected(self, *, step: str) -> pd.DataFrame:
        """Case rows enveloped by StepType, roof->base ordered."""
        sub = _common.envelope(self.df.copy(), _VALUE_COLS, step=step)
        return _common.order_roof_to_base(sub)

    def _top_bottom(self, *, step: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Top/Bottom row frames, roof->base, paired one row per story.

        Raises:
            ETABSError: If the counts mismatch (a story missing Top or Bottom)
                — the staircase pairing would be undefined.
        """
        sub = self._selected(step=step)
        top_df = sub[sub["Location"].astype(str) == "Top"].reset_index(drop=True)
        bot_df = sub[sub["Location"].astype(str) == "Bottom"].reset_index(drop=True)
        if len(top_df) != len(bot_df):
            raise ETABSError(
                f"Story Forces has {len(top_df)} Top vs {len(bot_df)} Bottom "
                f"rows for case '{self.case}'; cannot pair the shear profile."
            )
        return top_df, bot_df


def _add_top_bottom_elevation(
    df: pd.DataFrame, parent: "_SessionBase"
) -> pd.DataFrame:
    """Add an ``Elevation`` column honoring Top/Bottom locations.

    Top rows take the story's own elevation; Bottom rows take the story-below
    elevation (the lowest uses its own). Elevations are then baked to report
    length units. A Story absent from the stories map fails loudly rather than
    yielding a silent NaN elevation (ADR 0003 §3).
    """
    parent.stories.map_elevation_top_bottom(df)
    unmapped = df.loc[df["Elevation"].isna(), "Story"]
    if not unmapped.empty:
        missing = sorted({str(s) for s in unmapped})
        raise ETABSError(
            f"Story value(s) {missing} are not in the stories elevation map; "
            f"cannot assign an Elevation. Known stories: "
            f"{list(parent.stories.mapping)}."
        )
    factor = parent.units.length_factor
    df["Elevation"] = pd.to_numeric(df["Elevation"], errors="coerce") * factor
    return df


def _resolve_selector(case: str | None, combo: str | None) -> str:
    """Require exactly one of ``case=``/``combo=`` and return the name."""
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]


def _shear_col(direction: str) -> str:
    key = str(direction).upper()
    try:
        return _SHEAR_COL[key]
    except KeyError:
        raise ETABSError(
            f"Unknown direction '{direction}'. Use 'X' or 'Y'."
        ) from None
