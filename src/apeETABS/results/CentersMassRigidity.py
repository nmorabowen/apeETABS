"""CentersMassRigidity — CM/CR + mass snapshot (``"Centers Of Mass And Rigidity"``).

A self-contained, per-story view of the centers of mass (CM) and rigidity (CR)
plus story masses. Carries NO case/combo (the table is not case-filtered, like
WallForces). Powers the eccentricity (CM<->CR) and ASCE 7 vertical Type 2 mass
irregularity checks. Holds no live session (ADR 0002 snapshot rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from ..criteria import ASCE7, IrregularityCriteria
from ..errors import ETABSError
from . import _common

if TYPE_CHECKING:
    from .._session import _SessionBase

# Confirmed live (Casa 17B, ETABS v22): the real table KEY is Title-Case
# ("Of"/"And"), and the key equals the human TableName.
_TABLE = "Centers Of Mass And Rigidity"

# ETABS column -> canonical. Tolerant: only present keys are renamed.
# Confirmed live (Casa 17B, ETABS v22): real columns are Story, Diaphragm,
# MassX, MassY, XCM, YCM, CumMassX, CumMassY, XCCM, YCCM, XCR, YCR. NOTE: XCR/
# YCR can be empty ("None") when ETABS computes no rigid-diaphragm center of
# rigidity (e.g. semi-rigid diaphragms) — eccentricity then yields NaN, handled
# gracefully downstream.
_COLUMN_MAP = {
    "Story": "Story",
    "Diaphragm": "Diaphragm",
    "MassX": "MassX",
    "MassY": "MassY",
    "XCM": "XCM",
    "YCM": "YCM",
    "XCR": "XCR",
    "YCR": "YCR",
}

_REQUIRED = {"Story", "XCM", "YCM", "XCR", "YCR"}

# CM/CR coordinates are lengths; masses stay raw (no length conversion).
_DIM_MAP = {"XCM": "length", "YCM": "length", "XCR": "length", "YCR": "length"}


@dataclass
class CentersMassRigidity:
    """CM/CR coordinates + story masses, report length units baked on coords.

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units); the
            ``XCM/YCM/XCR/YCR`` columns are in report length units, mass columns
            left raw.
        units: ``{column: unit_label}`` for the baked coordinate columns.
    """

    df: pd.DataFrame
    units: dict[str, str]

    # ------------------------------------------------------------------
    # Builder (called by the Results composite)
    # ------------------------------------------------------------------

    @classmethod
    def from_table(cls, parent: "_SessionBase") -> "CentersMassRigidity":
        """Build a snapshot of CM/CR (and masses) for every story."""
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build "
                f"CentersMassRigidity. Has the model been analyzed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        labels = _common.bake_units(df, _DIM_MAP, parent)
        df = _common.add_elevation(df, parent)
        df = _common.order_roof_to_base(df)
        return cls(df=df, units=labels)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def eccentricity(self) -> pd.DataFrame:
        """Per-story CM<->CR eccentricity ``ex=|XCM-XCR|``, ``ey=|YCM-YCR|``.

        Returns a roof->base DataFrame with ``Story, Elevation, ex, ey`` in
        report length units. NOTE: ``ex/ey`` are NaN when ETABS reports no
        center of rigidity (``XCR/YCR`` empty) — observed on real models even
        with rigid diaphragms (see the parked CR follow-up in BUILD_PLAN).
        """
        df = self.df
        xcm = pd.to_numeric(df["XCM"], errors="coerce")
        ycm = pd.to_numeric(df["YCM"], errors="coerce")
        xcr = pd.to_numeric(df["XCR"], errors="coerce")
        ycr = pd.to_numeric(df["YCR"], errors="coerce")
        out = pd.DataFrame(
            {
                "Story": df["Story"].to_numpy(),
                "Elevation": df["Elevation"].to_numpy(),
                "ex": (xcm - xcr).abs().to_numpy(),
                "ey": (ycm - ycr).abs().to_numpy(),
            }
        )
        return out

    def mass_check(
        self,
        criteria: IrregularityCriteria = ASCE7,
        *,
        mass_col: str = "MassX",
    ) -> pd.DataFrame:
        """ASCE 7 vertical Type 2 (mass) irregularity per story, roof->base.

        A story is flagged when its mass *exceeds* ``criteria.mass_ratio`` times
        an adjacent story's mass (either the story above OR below). Comparing on
        the *heavier-than-neighbor* test (``mass > 1.5*adjacent``) naturally
        exempts a light roof (a roof lighter than the floor below is not
        considered per ASCE 7).

        INTENTIONAL CONSERVATISM (decided 2026-06-21, confirmed against a live
        24-story model): the symmetric test will ALSO flag the floor directly
        below a light roof (floor > 1.5*roof), which ASCE 7's "a roof that is
        lighter than the floor below need not be considered" arguably exempts.
        We keep the symmetric form deliberately — it never misses a heavy story
        and may over-report; the engineer judges flagged stories in context.

        Returns ``Story, Elevation, mass, ratio_above, ratio_below, irregular``.
        Robust to a single-story model (no adjacent -> not irregular).
        """
        if mass_col not in self.df.columns:
            raise ETABSError(
                f"Mass column '{mass_col}' not present in "
                f"'{_TABLE}'. Available: {list(self.df.columns)}."
            )
        # Roof->base order (already), so the row above is the *previous* index
        # (higher elevation) and the row below is the *next* index.
        df = _common.order_roof_to_base(self.df).reset_index(drop=True)
        mass = pd.to_numeric(df[mass_col], errors="coerce")
        mass_above = mass.shift(1)  # story immediately above (higher elevation)
        mass_below = mass.shift(-1)  # story immediately below (lower elevation)

        # ratio of this story's mass to the adjacent story's mass.
        ratio_above = mass / mass_above
        ratio_below = mass / mass_below

        thr = float(criteria.mass_ratio)
        irregular = (
            (mass > thr * mass_above).fillna(False)
            | (mass > thr * mass_below).fillna(False)
        )

        return pd.DataFrame(
            {
                "Story": df["Story"].to_numpy(),
                "Elevation": df["Elevation"].to_numpy(),
                "mass": mass.to_numpy(),
                "ratio_above": ratio_above.to_numpy(),
                "ratio_below": ratio_below.to_numpy(),
                "irregular": irregular.to_numpy(),
            }
        )
