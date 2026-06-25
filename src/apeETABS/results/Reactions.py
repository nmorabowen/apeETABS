"""Reactions — joint reaction snapshot from ``"Joint Reactions"``.

A self-contained, report-unit-baked view of support reactions for one resolved
case/combo, mirroring :class:`~apeETABS.results.Displacements.Displacements`.
``Fx/Fy/Fz`` are forces, ``Mx/My/Mz`` moments. Built by the
:class:`~apeETABS.results.Results.Results` composite; holds no live session.

The reaction table is the ETABS side of the ADR 0009 solve cross-check:
:meth:`by_joint` returns ``{joint_id: (Fx,Fy,Fz,Mx,My,Mz)}`` aligned with the
apeGmsh solver's ``solve_and_extract`` output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from ..errors import ETABSError
from . import _common

if TYPE_CHECKING:
    from .._session import _SessionBase

_TABLE = "Joint Reactions"

# ETABS column -> canonical. Tolerant: ETABS uses FX..MZ; some exports F1..M3.
_COLUMN_MAP = {
    "Story": "Story",
    "UniqueName": "Point",
    "Point": "Point",
    "Label": "Label",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "StepNumber": "StepNumber",
    "FX": "Fx", "FY": "Fy", "FZ": "Fz", "MX": "Mx", "MY": "My", "MZ": "Mz",
    "F1": "Fx", "F2": "Fy", "F3": "Fz", "M1": "Mx", "M2": "My", "M3": "Mz",
    "Fx": "Fx", "Fy": "Fy", "Fz": "Fz", "Mx": "Mx", "My": "My", "Mz": "Mz",
}

_REQUIRED = {"OutputCase", "Fx", "Fy", "Fz"}

_DIM_MAP = {
    "Fx": "force", "Fy": "force", "Fz": "force",
    "Mx": "moment", "My": "moment", "Mz": "moment",
}

_VALUE_COLS = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]


@dataclass
class Reactions:
    """Joint reactions for one case/combo, report units baked.

    Attributes:
        df: Canonical columns (``Point``, ``Fx..Mz``), in report units.
        case: The resolved ``OutputCase`` name (post fuzzy-match).
        units: ``{column: unit_label}`` for annotation.
    """

    df: pd.DataFrame
    case: str
    units: dict[str, str]
    factors: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_table(
        cls,
        parent: "_SessionBase",
        *,
        case: str | None = None,
        combo: str | None = None,
    ) -> "Reactions":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build Reactions. "
                f"Has the model been analyzed (and joint reactions requested)?"
            )
        df = _common.map_columns(raw, _COLUMN_MAP, _REQUIRED, table=_TABLE)
        df, resolved = _common.select_case(df, name, table=_TABLE)
        labels = _common.bake_units(df, _DIM_MAP, parent)
        factors = _common.bake_factors(_DIM_MAP, parent)
        return cls(df=df, case=resolved, units=labels, factors=factors)

    def by_joint(self) -> dict[str, tuple[float, float, float, float, float, float]]:
        """``{joint_id: (Fx,Fy,Fz,Mx,My,Mz)}`` in **present units** (cross-check).

        One 6-vector per joint; when several rows share a joint (e.g. Max/Min
        steps) the per-DOF largest-magnitude value is taken. Missing columns
        read as zero. Values are un-baked back to the model's present units (the
        ``.sm.json`` contract), not the report units of :attr:`df`.
        """
        return _common.by_joint(self.df, _VALUE_COLS, self.factors)


def _resolve_selector(case: str | None, combo: str | None) -> str:
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]
