"""StoryDrifts — story drift snapshot from the ``"Story Drifts"`` table.

A self-contained, per-story drift view for one resolved case/combo. Drift is
dimensionless (no unit baking on the value), but ``Elevation`` is still in
report length units. Holds no live session (ADR 0002 snapshot rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from ..errors import ETABSError
from . import _common
from .Profile import Profile

if TYPE_CHECKING:
    from .._session import _SessionBase

_TABLE = "Story Drifts"

_COLUMN_MAP = {
    "Story": "Story",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "StepNumber": "StepNumber",
    "Direction": "Direction",
    "Drift": "Drift",
    "Label": "Label",
    "X": "X", "Y": "Y", "Z": "Z",
}

_REQUIRED = {"Story", "OutputCase", "Direction", "Drift"}

# Drift is dimensionless: no unit conversion on the value column.
_DIM_MAP = {"Drift": "dimensionless"}

_VALUE_COLS = ["Drift"]


@dataclass
class StoryDrifts:
    """Story drifts for one case/combo; drift is dimensionless.

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units).
        case: The resolved ``OutputCase`` name (post fuzzy-match).
        units: ``{column: unit_label}``; ``Drift`` maps to ``""``.
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
    ) -> "StoryDrifts":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build StoryDrifts. "
                f"Has the model been analyzed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        df, resolved = _common.select_case(df, name, table=_TABLE)
        labels = _common.bake_units(df, _DIM_MAP, parent)
        df = _common.add_elevation(df, parent)
        df = _common.order_roof_to_base(df)
        return cls(df=df, case=resolved, units=labels)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def profile(self, *, direction: str = "X", step: str = "Max") -> Profile:
        """A roof->base drift profile for one ``direction`` (dimensionless).

        Args:
            direction: ``"X"`` / ``"Y"`` (matched against the ``Direction``
                column).
            step: StepType envelope; ``"Max"`` (default), ``"Min"``, ``"abs"``.
        """
        sub = _filter_direction(self.df, direction)
        sub = _common.envelope(sub, _VALUE_COLS, step=step)
        sub = _common.order_roof_to_base(sub)
        elev, value, stories = _common.profile_arrays(sub, "Drift")
        return Profile(
            elevation=elev,
            value=value,
            stories=stories,
            label=f"Drift {str(direction).upper()}",
            unit="",  # drift is dimensionless
        )

    def peak(self, *, direction: str = "X", step: str = "Max") -> tuple[float, str]:
        """The largest-magnitude drift and its story for ``direction``."""
        sub = _filter_direction(self.df, direction)
        sub = _common.envelope(sub, _VALUE_COLS, step=step)
        if sub.empty:
            return 0.0, ""
        vals = pd.to_numeric(sub["Drift"], errors="coerce")
        idx = vals.abs().idxmax()
        return float(sub.loc[idx, "Drift"]), str(sub.loc[idx, "Story"])

    def exceeds(self, limit: float) -> pd.DataFrame:
        """Rows whose drift magnitude exceeds ``limit`` (e.g. a code cap).

        Returns the canonical rows (all directions/steps kept) where
        ``|Drift| > limit``, in the snapshot's roof->base order.
        """
        vals = pd.to_numeric(self.df["Drift"], errors="coerce")
        return self.df[vals.abs() > float(limit)].copy()


def _resolve_selector(case: str | None, combo: str | None) -> str:
    """Require exactly one of ``case=``/``combo=`` and return the name."""
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]


def _filter_direction(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Filter the canonical frame to one drift ``Direction``."""
    want = str(direction).upper()
    if "Direction" not in df.columns:
        return df.copy()
    hit = df[df["Direction"].astype(str).str.upper() == want]
    if hit.empty:
        available = sorted({str(d) for d in df["Direction"].unique()})
        raise ETABSError(
            f"No drift rows for direction '{direction}'. Available: {available}."
        )
    return hit.copy()
