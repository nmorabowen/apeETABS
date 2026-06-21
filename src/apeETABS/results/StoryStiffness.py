"""StoryStiffness — lateral story-stiffness snapshot (``"Story Stiffness"``).

A self-contained, per-story view of lateral stiffness (StiffX/StiffY) for one
resolved case/combo. Powers the ASCE 7 vertical Type 1a/1b soft-story checks.
Stiffness columns are kept raw (force/length); their unit label is set
best-effort to ``force/length`` (no length-conversion baking). Holds no live
session (ADR 0002 snapshot rule).
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
_TABLE = "Story Stiffness"

# Confirmed live (Casa 17B, ETABS v22): real columns are Story, OutputCase,
# CaseType, StepType, StepNumber, ShearX, DriftX, StiffX, ShearY, DriftY,
# StiffY. We map only the ones we use; the rest are kept as unmapped extras.
# NOTE: stiffness is per-direction-per-case — under an X case (e.g. "Sx")
# StiffY reads ~0, so assess soft story in X with the X lateral case and in Y
# with the Y case.
_COLUMN_MAP = {
    "Story": "Story",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "StiffX": "StiffX",
    "StiffY": "StiffY",
}

_REQUIRED = {"Story", "OutputCase", "StiffX", "StiffY"}


@dataclass
class StoryStiffness:
    """Lateral story stiffness for one case/combo (raw force/length units).

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units).
        case: The resolved ``OutputCase`` name (post fuzzy-match).
        units: ``{column: unit_label}``; ``StiffX``/``StiffY`` map to
            ``"force/length"`` (best-effort label, not converted).
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
    ) -> "StoryStiffness":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build "
                f"StoryStiffness. Has the model been analyzed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        df, resolved = _common.select_case(df, name, table=_TABLE)
        df = _common.add_elevation(df, parent)
        df = _common.order_roof_to_base(df)

        # Stiffness is force/length; do NOT length-bake. Best-effort label.
        label = f"{parent.units.force.name}/{parent.units.length.name}"
        labels = {"StiffX": label, "StiffY": label}
        return cls(df=df, case=resolved, units=labels)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def soft_story(
        self,
        *,
        direction: str = "X",
        criteria: IrregularityCriteria = ASCE7,
    ) -> pd.DataFrame:
        """ASCE 7 vertical Type 1a/1b soft-story check, roof->base.

        Args:
            direction: ``"X"`` -> ``StiffX``; ``"Y"`` -> ``StiffY``.
            criteria: Threshold set (defaults to :data:`ASCE7`).

        For each story, "above" is the next story up (higher elevation):

        * ``ratio_adjacent = K_i / K_above``
        * ``ratio_avg3 = K_i / mean(K of up to 3 stories above)``
        * ``soft_1a`` if ``K_i < soft_1a_adjacent*K_above`` OR
          ``K_i < soft_1a_avg3*mean3``
        * ``soft_1b`` likewise with the 1b thresholds.

        The TOP story has no story above -> NaN ratios, False flags. When fewer
        than 3 stories exist above, the average is over however many exist.

        Returns ``Story, Elevation, stiffness, ratio_adjacent, ratio_avg3,
        soft_1a, soft_1b``.
        """
        col = _stiffness_col(direction)
        if col not in self.df.columns:
            raise ETABSError(
                f"Stiffness column '{col}' not present in '{_TABLE}'. "
                f"Available: {list(self.df.columns)}."
            )
        df = _common.order_roof_to_base(self.df).reset_index(drop=True)
        k = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        n = len(k)

        ratio_adjacent = np.full(n, np.nan)
        ratio_avg3 = np.full(n, np.nan)
        soft_1a = np.zeros(n, dtype=bool)
        soft_1b = np.zeros(n, dtype=bool)

        # Roof->base order: index i-1 .. i-3 are the stories above story i.
        for i in range(n):
            above = k[max(0, i - 3):i]  # up to 3 stories above (closest last)
            if above.size == 0:
                continue  # top story: no "above" -> NaN ratios, no flag
            k_above = k[i - 1]
            mean3 = float(np.nanmean(above))
            ki = k[i]

            if k_above and not np.isnan(k_above):
                ratio_adjacent[i] = ki / k_above
            if mean3 and not np.isnan(mean3):
                ratio_avg3[i] = ki / mean3

            soft_1a[i] = (ki < criteria.soft_1a_adjacent * k_above) or (
                ki < criteria.soft_1a_avg3 * mean3
            )
            soft_1b[i] = (ki < criteria.soft_1b_adjacent * k_above) or (
                ki < criteria.soft_1b_avg3 * mean3
            )

        return pd.DataFrame(
            {
                "Story": df["Story"].to_numpy(),
                "Elevation": df["Elevation"].to_numpy(),
                "stiffness": k,
                "ratio_adjacent": ratio_adjacent,
                "ratio_avg3": ratio_avg3,
                "soft_1a": soft_1a,
                "soft_1b": soft_1b,
            }
        )


def _resolve_selector(case: str | None, combo: str | None) -> str:
    """Require exactly one of ``case=``/``combo=`` and return the name."""
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]


def _stiffness_col(direction: str) -> str:
    """Map a direction to its stiffness column name."""
    want = str(direction).upper()
    if want == "X":
        return "StiffX"
    if want == "Y":
        return "StiffY"
    raise ETABSError(f"Unknown direction '{direction}'. Use 'X' or 'Y'.")
