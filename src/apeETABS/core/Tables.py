"""Tables composite — ETABS database tables as pandas DataFrames.

Wraps ``cSapModel.DatabaseTables`` so any displayable ETABS table comes
back as a clean DataFrame. This is the backbone of the parsing layer; the
results domain objects build on top of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..errors import ETABSError

if TYPE_CHECKING:
    from .._session import _SessionBase


class Tables:
    """Read ETABS database tables into DataFrames."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def available(self) -> pd.DataFrame:
        """Return the tables currently available for display.

        Columns: ``TableKey`` (use this as the key for :meth:`get`) and
        ``TableName`` (the human-readable label).
        """
        result = self._parent.SapModel.DatabaseTables.GetAvailableTables(0, [], [], [])
        *outs, ret = result
        if ret != 0:
            raise ETABSError(f"GetAvailableTables failed (ret={ret}).")
        _num, keys, names, _import_type = outs
        return pd.DataFrame({"TableKey": list(keys), "TableName": list(names)})

    def list(self) -> None:
        """Print available tables (human-centric quick look)."""
        df = self.available()
        print(f"\n{len(df)} available tables:")
        for i, (key, name) in enumerate(zip(df["TableKey"], df["TableName"]), 1):
            print(f"{i:3d}. {key}  —  {name}")

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def get(
        self,
        table_key: str,
        *,
        group: str = "",
        numeric: bool = True,
    ) -> pd.DataFrame:
        """Return one ETABS table as a DataFrame.

        Args:
            table_key: The ETABS table key (see :meth:`available`), e.g.
                ``"Story Forces"``, ``"Joint Drifts"``,
                ``"Design Forces - Piers"``.
            group: Optional ETABS group name to filter the table.
            numeric: Coerce fully-numeric columns to numbers (default True).

        Returns:
            A DataFrame; empty (with correct columns when known) if the
            table has no rows.

        Raises:
            ETABSError: If the API call fails.
        """
        headers, flat = self._fetch(table_key, group)
        if not headers:
            return pd.DataFrame()
        ncols = len(headers)
        if not flat:
            return pd.DataFrame(columns=list(headers))

        data = np.asarray(flat, dtype=object).reshape(-1, ncols)
        df = pd.DataFrame(data, columns=list(headers))
        if numeric:
            df = _coerce_numeric(df)
        return df

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch(self, table_key: str, group: str) -> tuple[list[str], list[str]]:
        """Call GetTableForDisplayArray; return (headers, flat_data)."""
        # Out order: FieldKeyList, TableVersion, FieldsKeysIncluded,
        #            NumberRecords, TableData, ret
        result = self._parent.SapModel.DatabaseTables.GetTableForDisplayArray(
            table_key, [], group, 0, [], 0, []
        )
        *outs, ret = result
        if ret != 0:
            raise ETABSError(
                f"GetTableForDisplayArray('{table_key}') failed (ret={ret}). "
                f"Check the table key with .available()."
            )
        _field_keys, _version, fields_included, _num_records, table_data = outs
        headers = list(fields_included) if fields_included else []
        flat = list(table_data) if table_data else []
        if self._parent._verbose and not flat:
            print(f"Table '{table_key}' returned no rows.")
        return headers, flat


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert each fully-numeric column to numbers; leave others as strings."""
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        # Only adopt the conversion if nothing that was non-null became NaN
        # (i.e. the whole column is genuinely numeric).
        if converted.notna().all():
            df[col] = converted
    return df
