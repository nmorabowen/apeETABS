"""WallForces — pier design-force snapshot from ``"Design Forces - Piers"``.

A self-contained, report-unit-baked view of wall (pier) design forces across
all load combinations. Ports the proven numeric logic from the v0
``modelResults_wallForces`` (per-pier slices, min/max envelopes per elevation,
dynamic/static state tag, capacity-design shear amplification) to the new
architecture: a typed ``@dataclass`` detached from the session, units baked,
amplification stored as *metadata* (NOT baked into the frame). Holds no live COM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from ..errors import ETABSError
from . import _common

if TYPE_CHECKING:
    from .._session import _SessionBase

_TABLE = "Design Forces - Piers"

# ETABS column -> canonical. Tolerant: only present keys are renamed; unknown
# extras are kept untouched.
_COLUMN_MAP = {
    "Story": "Story",
    "Pier": "Pier",
    "OutputCase": "Combo",
    "Combo": "Combo",
    "ComboName": "Combo",
    "Location": "Location",
    "P": "P",
    "V2": "V2", "V3": "V3",
    "T": "T",
    "M2": "M2", "M3": "M3",
}

_REQUIRED = {"Story", "Pier", "Combo", "P", "V2", "M3"}

# Per-column dimension for unit baking. Forces are F, moments/torsion F·L.
_DIM_MAP = {
    "P": "force", "V2": "force", "V3": "force",
    "T": "moment", "M2": "moment", "M3": "moment",
}

_VALUE_COLS = ["P", "V2", "V3", "T", "M2", "M3"]


@dataclass
class WallForces:
    """Pier design forces across all combos, report units baked.

    Attributes:
        df: Canonical columns plus ``Elevation`` (report length units) and a
            ``State`` tag (``"Dynamic"``/``"Static"``); force/moment columns in
            report units.
        units: ``{column: unit_label}`` for axis annotation.
        piers: Distinct pier labels present.
        combos: Distinct load-combination names present.
        shear_amplification: Capacity-design shear factor metadata (1.0 unless
            ``design_parameters`` were supplied). NOT baked into ``df``.
    """

    df: pd.DataFrame
    units: dict[str, str]
    piers: list[str]
    combos: list[str]
    shear_amplification: float = 1.0
    design_parameters: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Builder (called by the Results composite)
    # ------------------------------------------------------------------

    @classmethod
    def from_table(
        cls,
        parent: "_SessionBase",
        *,
        design_parameters: dict[str, float] | None = None,
    ) -> "WallForces":
        """Build a snapshot of all pier design forces.

        Args:
            design_parameters: Optional ``{'overstrength', 'dynamic_amplification'}``;
                their product (capped at 3) becomes ``shear_amplification``
                metadata. Omitted -> amplification 1.0.
        """
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build WallForces. "
                f"Has the model been designed?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        labels = _common.bake_units(df, _DIM_MAP, parent)
        df = _common.add_elevation(df, parent)
        df["State"] = df["Combo"].map(_state_of)
        df = _common.order_roof_to_base(df)

        amp = _shear_amplification(design_parameters)
        return cls(
            df=df,
            units=labels,
            piers=[str(p) for p in df["Pier"].unique()],
            combos=[str(c) for c in df["Combo"].unique()],
            shear_amplification=amp,
            design_parameters=dict(design_parameters or {}),
        )

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def pier(self, label: str) -> pd.DataFrame:
        """All rows for one pier ``label`` (every combo), roof->base."""
        hit = self.df[self.df["Pier"].astype(str) == str(label)]
        if hit.empty:
            raise ETABSError(
                f"No pier '{label}' in WallForces. Available: {self.piers}."
            )
        return hit.copy()

    def envelope(self, pier: str) -> dict[str, pd.DataFrame]:
        """Min/max envelopes per elevation for one pier.

        Returns ``{'P': df, 'M3': df, 'V2': df}`` where each frame is indexed
        by ``Elevation`` with ``min``/``max`` columns aggregated across all
        load combinations.
        """
        data = self.pier(pier)
        return {
            col: data.groupby("Elevation")[col].agg(["min", "max"])
            for col in ("P", "M3", "V2")
        }


def _state_of(combo: object) -> str:
    """Tag a combo as ``Dynamic`` (contains 'E') else ``Static`` (v0 rule)."""
    return "Dynamic" if "E" in str(combo).upper() else "Static"


def _shear_amplification(design_parameters: dict[str, float] | None) -> float:
    """``min(3, overstrength * dynamic_amplification)`` (1.0 if unspecified)."""
    if not design_parameters:
        return 1.0
    try:
        overstrength = float(design_parameters["overstrength"])
        dynamic = float(design_parameters["dynamic_amplification"])
    except KeyError as exc:
        raise ETABSError(
            "design_parameters must provide 'overstrength' and "
            "'dynamic_amplification'."
        ) from exc
    return min(3.0, overstrength * dynamic)
