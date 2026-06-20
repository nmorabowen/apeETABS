"""Displacements — joint displacement snapshot from ``"Joint Displacements"``.

A self-contained, report-unit-baked view of joint displacements for one
resolved case/combo. Built by :class:`~apeETABS.results.Results.Results`; holds
no live session (ADR 0002 snapshot rule). ``Ux/Uy/Uz`` are lengths,
``Rx/Ry/Rz`` are rotations (dimensionless/angle, left unconverted).
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

_TABLE = "Joint Displacements"

# ETABS column -> canonical. Tolerant: only present keys are renamed, and
# unknown extra columns are kept untouched.
_COLUMN_MAP = {
    "Story": "Story",
    "UniqueName": "Point",
    "Point": "Point",
    "Label": "Label",
    "OutputCase": "OutputCase",
    "CaseType": "CaseType",
    "StepType": "StepType",
    "StepNumber": "StepNumber",
    "Ux": "Ux", "Uy": "Uy", "Uz": "Uz",
    "Rx": "Rx", "Ry": "Ry", "Rz": "Rz",
}

_REQUIRED = {"Story", "OutputCase", "Ux", "Uy", "Uz"}

# Per-column dimension for unit baking (rotations carry no length units).
_DIM_MAP = {
    "Ux": "length", "Uy": "length", "Uz": "length",
    "Rx": "dimensionless", "Ry": "dimensionless", "Rz": "dimensionless",
}

_VALUE_COLS = ["Ux", "Uy", "Uz", "Rx", "Ry", "Rz"]

# direction= -> displacement column.
_DIRECTIONS = {"X": "Ux", "Y": "Uy", "Z": "Uz", "RX": "Rx", "RY": "Ry", "RZ": "Rz"}


@dataclass
class Displacements:
    """Joint displacements for one case/combo, report units baked.

    Attributes:
        df: Canonical columns plus ``Elevation``, in report units.
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
    ) -> "Displacements":
        """Build a snapshot for exactly one ``case=`` or ``combo=``."""
        name = _resolve_selector(case, combo)
        raw = parent.tables.get(_TABLE, numeric=True)
        if raw.empty:
            raise ETABSError(
                f"Table '{_TABLE}' returned no rows; cannot build "
                f"Displacements. Has the model been analyzed?"
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

    def profile(self, *, label: str, direction: str = "X", step: str = "Max") -> Profile:
        """A roof->base displacement profile for one joint ``label``.

        Args:
            label: The joint identifier (matched against ``Point`` then,
                if present, ``Label``).
            direction: ``"X"``/``"Y"``/``"Z"`` (or ``"RX"``/``"RY"``/``"RZ"``).
            step: StepType envelope; ``"Max"`` (default), ``"Min"``, or
                ``"abs"`` (larger magnitude per story).
        """
        col = _direction_col(direction)
        sub = _select_label(self.df, label)
        sub = _common.envelope(sub, _VALUE_COLS, step=step)
        sub = _common.order_roof_to_base(sub)
        elev, value, stories = _common.profile_arrays(sub, col)
        return Profile(
            elevation=elev,
            value=value,
            stories=stories,
            label=label,
            unit=self.units.get(col, ""),
        )

    def peak(self, *, direction: str = "X", step: str = "Max") -> tuple[float, str]:
        """The largest-magnitude displacement and its story, across joints."""
        col = _direction_col(direction)
        sub = _common.envelope(self.df.copy(), _VALUE_COLS, step=step)
        if sub.empty:
            return 0.0, ""
        vals = pd.to_numeric(sub[col], errors="coerce")
        idx = vals.abs().idxmax()
        return float(sub.loc[idx, col]), str(sub.loc[idx, "Story"])


def _resolve_selector(case: str | None, combo: str | None) -> str:
    """Require exactly one of ``case=``/``combo=`` and return the name."""
    if (case is None) == (combo is None):
        raise ETABSError("Pass exactly one of case= or combo=.")
    return case if case is not None else combo  # type: ignore[return-value]


def _direction_col(direction: str) -> str:
    key = str(direction).upper()
    try:
        return _DIRECTIONS[key]
    except KeyError:
        raise ETABSError(
            f"Unknown direction '{direction}'. Use one of {sorted(_DIRECTIONS)}."
        ) from None


def _select_label(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Filter to one joint by ``Point`` (or ``Label`` fallback)."""
    for col in ("Point", "Label"):
        if col in df.columns:
            hit = df[df[col].astype(str) == str(label)]
            if not hit.empty:
                return hit.copy()
    raise ETABSError(
        f"No joint '{label}' in displacements (checked Point/Label)."
    )
