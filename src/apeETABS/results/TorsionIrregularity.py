"""TorsionIrregularity — torsional irregularity snapshot.

A self-contained, per-story view of the diaphragm max/avg drift ratio for one
resolved case/combo, powering the ASCE 7 horizontal Type 1a/1b torsional
irregularity check. The ratio is dimensionless. Holds no live session
(ADR 0002 snapshot rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..criteria import ASCE7, IrregularityCriteria
from ..errors import ETABSError
from . import _common

if TYPE_CHECKING:
    from .._session import _SessionBase

# Confirmed live (Casa 17B, ETABS v22): key equals the human TableName.
_TABLE = "Story Max Over Avg Drifts"

# Confirmed live (Casa 17B, ETABS v22): the real columns are "Max Drift" /
# "Avg Drift" (+ a ready "Ratio"). The "Maximum"/"Average" aliases are kept for
# tolerance against other ETABS versions; map_columns renames only present keys.
_COLUMN_MAP = {
    "Story": "Story",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "Direction": "Direction",
    "Max Drift": "Maximum",
    "Avg Drift": "Average",
    "Maximum": "Maximum",  # alt layout (older/other versions)
    "Average": "Average",  # alt layout
    "Ratio": "Ratio",
}

_REQUIRED = {"Story", "OutputCase", "Direction", "Maximum", "Average"}


@dataclass
class TorsionIrregularity:
    """Max/avg drift ratios for one case/combo (dimensionless).

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units).
        case: The resolved ``OutputCase`` name (post fuzzy-match).
    """

    df: pd.DataFrame
    case: str

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
    ) -> "TorsionIrregularity":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build "
                f"TorsionIrregularity. Has the model been analyzed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        df, resolved = _common.select_case(df, name, table=_TABLE)
        df = _common.add_elevation(df, parent)
        df = _common.order_roof_to_base(df)
        return cls(df=df, case=resolved)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def ratios(
        self,
        *,
        direction: str = "X",
        criteria: IrregularityCriteria = ASCE7,
        step: str = "Max",
    ) -> pd.DataFrame:
        """ASCE 7 horizontal Type 1a/1b torsional check, roof->base.

        Filters to ``direction`` (case-insensitive on the ``Direction`` column),
        envelopes ``StepType`` via :func:`_common.envelope` with ``step``, then
        recomputes ``ratio = Maximum/Average`` (preferred over any ETABS-provided
        ``Ratio`` column for robustness; divide-by-zero guarded -> NaN).

        Returns ``Story, Elevation, maximum, average, ratio, torsion_1a,
        torsion_1b`` where ``torsion_1a = ratio > criteria.torsion_1a`` and
        ``torsion_1b = ratio > criteria.torsion_1b``.
        """
        sub = _filter_direction(self.df, direction)
        sub = _common.envelope(sub, ["Maximum", "Average"], step=step)
        sub = _common.order_roof_to_base(sub).reset_index(drop=True)

        maximum = pd.to_numeric(sub["Maximum"], errors="coerce")
        average = pd.to_numeric(sub["Average"], errors="coerce")
        # Recompute for robustness; guard divide-by-zero -> NaN.
        ratio = maximum / average.replace(0, np.nan)

        torsion_1a = (ratio > criteria.torsion_1a).fillna(False)
        torsion_1b = (ratio > criteria.torsion_1b).fillna(False)

        return pd.DataFrame(
            {
                "Story": sub["Story"].to_numpy(),
                "Elevation": sub["Elevation"].to_numpy(),
                "maximum": maximum.to_numpy(),
                "average": average.to_numpy(),
                "ratio": ratio.to_numpy(),
                "torsion_1a": torsion_1a.to_numpy(),
                "torsion_1b": torsion_1b.to_numpy(),
            }
        )


def _resolve_selector(case: str | None, combo: str | None) -> str:
    """Require exactly one of ``case=``/``combo=`` and return the name."""
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]


def _filter_direction(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Filter the canonical frame to one ``Direction`` (case-insensitive)."""
    want = str(direction).upper()
    if "Direction" not in df.columns:
        return df.copy()
    hit = df[df["Direction"].astype(str).str.upper() == want]
    if hit.empty:
        available = sorted({str(d) for d in df["Direction"].unique()})
        raise ETABSError(
            f"No torsion rows for direction '{direction}'. Available: "
            f"{available}."
        )
    return hit.copy()
