"""Internal helpers shared by the results builders (no public class).

Centralizes the cross-cutting mechanics every result type needs:

* **Column mapping** — rename ETABS columns to a canonical schema, tolerant
  of unknown extras, loud on a missing *required* column (version drift).
* **Case/combo selection** — resolve a human name against the table's
  ``OutputCase`` column, fuzzy via ``rapidfuzz`` when installed, else exact
  with a helpful listing.
* **StepType enveloping** — collapse Max/Min/Step rows to one row per story,
  defaulting to ``step="Max"`` (also ``"abs"`` / ``"Min"``).
* **Unit baking** — multiply each value column by ``units.factor(dim)`` from
  a per-column dimension map (dimensionless columns left untouched).

These are functions, not a class, so the "one public class per file" rule
stays intact: the public surface lives in ``Displacements``/``StoryDrifts``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..errors import ETABSError

if TYPE_CHECKING:
    from .._session import _SessionBase

# rapidfuzz is an optional extra; selection degrades to exact matching without it.
try:  # pragma: no cover - import branch is environment-dependent
    from rapidfuzz import process as _rf_process
    from rapidfuzz import fuzz as _rf_fuzz

    _HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _HAVE_RAPIDFUZZ = False

# Fuzzy-match acceptance threshold (0-100). Below this we treat it as a miss
# and raise with the available cases, rather than silently picking a wrong one.
_FUZZY_THRESHOLD = 80.0

# Dimensions that carry no units: skip conversion (multiply by 1.0). Anything
# else is handed to ``units.factor(dim)``.
_DIMENSIONLESS = frozenset({"dimensionless", "angle", "", None})

# Report-unit label for a dimension. Length uses the present length unit's
# name; dimensionless columns get an empty axis label.
_LENGTH_DIMS = frozenset({"length", "disp", "displacement"})


def map_columns(
    df: pd.DataFrame,
    column_map: dict[str, str],
    required: set[str],
    *,
    table: str,
) -> pd.DataFrame:
    """Rename ETABS columns to canonical names; keep unknown extras.

    Args:
        df: The raw table from the ``tables`` composite.
        column_map: ``{etabs_name: canonical_name}``. Only keys present in
            ``df`` are renamed; canonical extras (e.g. ``Elevation``) are
            ignored here and added downstream.
        required: Canonical names that MUST exist after renaming.
        table: Table key, for error messages.

    Raises:
        ETABSError: If a required canonical column is absent after renaming
            (version drift surfaces loudly, not as silent wrong numbers).
    """
    rename = {etabs: canon for etabs, canon in column_map.items() if etabs in df.columns}
    out = df.rename(columns=rename)

    missing = required - set(out.columns)
    if missing:
        raise ETABSError(
            f"Table '{table}' is missing required column(s) "
            f"{sorted(missing)} after mapping. Present columns: "
            f"{list(df.columns)}. The ETABS table layout may have changed; "
            f"update the column map for this result type."
        )
    return out


def select_case(df: pd.DataFrame, name: str, *, table: str) -> tuple[pd.DataFrame, str]:
    """Filter ``df`` to one ``OutputCase``, resolving ``name`` to the nearest.

    With ``rapidfuzz`` installed the human ``name`` is matched to the closest
    actual ``OutputCase`` above :data:`_FUZZY_THRESHOLD`; without it, matching
    is exact. Either way the *resolved* case name is returned so the caller can
    record it on the snapshot.

    Raises:
        ETABSError: If ``OutputCase`` is absent, or no case matches (the
            available cases are listed).
    """
    if "OutputCase" not in df.columns:
        raise ETABSError(
            f"Table '{table}' has no 'OutputCase' column; cannot select a "
            f"case/combo. Present columns: {list(df.columns)}."
        )

    available = [str(c) for c in df["OutputCase"].unique()]

    # Exact hit short-circuits regardless of rapidfuzz.
    if name in available:
        resolved = name
    elif _HAVE_RAPIDFUZZ:
        # Lowercase via the processor so "eqx" matches "EQX" (case-insensitive).
        match = _rf_process.extractOne(
            name,
            available,
            scorer=_rf_fuzz.WRatio,
            processor=str.lower,
            score_cutoff=_FUZZY_THRESHOLD,
        )
        if match is None:
            raise ETABSError(
                f"No case/combo matching '{name}' in table '{table}' "
                f"(best below threshold). Available: {available}."
            )
        resolved = match[0]
    else:
        raise ETABSError(
            f"No case/combo named '{name}' in table '{table}' "
            f"(exact match; install the [fuzzy] extra for fuzzy matching). "
            f"Available: {available}."
        )

    out = df[df["OutputCase"].astype(str) == resolved].copy()
    return out, resolved


def envelope(df: pd.DataFrame, value_cols: list[str], *, step: str) -> pd.DataFrame:
    """Collapse StepType rows to one row per story for the given ``step``.

    Args:
        df: Case-filtered, canonical frame (one or more rows per story).
        value_cols: Columns to reduce when enveloping by magnitude.
        step: ``"Max"`` / ``"Min"`` select that ``StepType``; ``"abs"`` takes
            the larger magnitude of each value column across all step rows
            per story. A literal :class:`int` (or its string) selects that
            ``StepNumber``.

    If the frame has no ``StepType`` column (static cases), it passes through.
    Rows keep canonical roof->base order via a stable story sort.
    """
    if "StepType" not in df.columns and "StepNumber" not in df.columns:
        return df

    # A specific StepNumber overrides StepType handling.
    if isinstance(step, int) or (isinstance(step, str) and step.isdigit()):
        if "StepNumber" in df.columns:
            return df[df["StepNumber"].astype(str) == str(step)].copy()
        return df

    if step in ("Max", "Min"):
        if "StepType" in df.columns:
            sel = df[df["StepType"].astype(str) == step].copy()
            # Fall back to the whole frame if this StepType is absent (static).
            return sel if not sel.empty else df
        return df

    if step == "abs":
        if "Story" not in df.columns:
            return df

        # One row per story: keep the first row as the template, then for each
        # value column substitute the cell with the largest magnitude across
        # that story's step rows. Iterating avoids groupby-apply's grouping-
        # column ambiguity warning while preserving every (non-value) column.
        rows = []
        for _story, group in df.groupby("Story", sort=False):
            base = group.iloc[0].copy()
            for col in value_cols:
                if col in group.columns:
                    vals = pd.to_numeric(group[col], errors="coerce")
                    base[col] = group.loc[vals.abs().idxmax(), col]
            rows.append(base)
        return pd.DataFrame(rows).reset_index(drop=True)

    raise ETABSError(
        f"Unknown step='{step}'. Use 'Max', 'Min', 'abs', or a StepNumber."
    )


def bake_units(
    df: pd.DataFrame,
    dim_map: dict[str, str],
    parent: "_SessionBase",
) -> dict[str, str]:
    """Multiply value columns by their report-unit factor, in place.

    Args:
        df: Canonical frame (mutated: each mapped column converted to report
            units; dimensionless columns left untouched).
        dim_map: ``{canonical_col: dimension}``. ``dimension`` is a key for
            ``units.factor`` (e.g. ``"length"``) or a dimensionless tag.
        parent: The session, providing ``parent.units`` and ``parent.stories``.

    Returns:
        ``{column: unit_label}`` for the converted columns, for plot axes.
    """
    length_unit = parent.units.length.name
    labels: dict[str, str] = {}
    for col, dim in dim_map.items():
        if col not in df.columns:
            continue
        if dim in _DIMENSIONLESS:
            labels[col] = ""
            continue
        factor = parent.units.factor(dim)
        df[col] = pd.to_numeric(df[col], errors="coerce") * factor
        labels[col] = length_unit if dim in _LENGTH_DIMS else dim
    return labels


def add_elevation(df: pd.DataFrame, parent: "_SessionBase") -> pd.DataFrame:
    """Add an ``Elevation`` column (report length units) via the stories map.

    Elevations are converted with the length factor so they share the report
    unit system with displacement columns.

    Raises:
        ETABSError: If any ``Story`` value is absent from the stories map. A
            missing story would otherwise become a silent NaN elevation that
            propagates into snapshots/Profiles, so we fail loudly here
            (ADR 0003 §3) naming the offending value(s).
    """
    parent.stories.map_elevation(df)

    # A Story not in the mapping yields NaN — surface it instead of letting a
    # NaN-elevation row survive into the snapshot/profile.
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


def order_roof_to_base(df: pd.DataFrame) -> pd.DataFrame:
    """Sort rows by descending elevation (roof first, base last)."""
    if "Elevation" not in df.columns:
        return df
    return df.sort_values("Elevation", ascending=False, kind="stable").reset_index(
        drop=True
    )


def profile_arrays(
    df: pd.DataFrame, value_col: str
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract aligned ``(elevation, value, stories)`` arrays for a Profile."""
    elev = df["Elevation"].to_numpy(dtype=float)
    value = pd.to_numeric(df[value_col], errors="coerce").to_numpy(dtype=float)
    stories = [str(s) for s in df["Story"].tolist()]
    return elev, value, stories
