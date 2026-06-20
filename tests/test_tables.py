"""Tests for the Tables composite: reshape, numeric coercion, empty handling."""

from __future__ import annotations

import pandas as pd
import pytest

from apeETABS.errors import ETABSError

from .conftest import bind, make_mock


def test_get_reshapes_flat_data_into_dataframe(etabs):
    df = etabs.tables.get("Story Drifts")
    assert list(df.columns) == ["Story", "OutputCase", "StepType", "Direction", "Drift"]
    assert len(df) == 3
    assert df["Story"].tolist() == ["Story3", "Story2", "Story1"]


def test_numeric_columns_are_coerced(etabs):
    df = etabs.tables.get("Story Drifts")
    assert pd.api.types.is_numeric_dtype(df["Drift"])
    assert df["Drift"].iloc[1] == pytest.approx(0.0018)


def test_mixed_column_stays_string(etabs):
    df = etabs.tables.get("Mixed Column")
    assert pd.api.types.is_numeric_dtype(df["A"])
    assert not pd.api.types.is_numeric_dtype(df["B"])


def test_numeric_false_keeps_strings(etabs):
    df = etabs.tables.get("Story Drifts", numeric=False)
    assert df["Drift"].iloc[0] == "0.0012"


def test_empty_table_returns_empty_with_columns(etabs):
    df = etabs.tables.get("Empty Table")
    assert df.empty
    assert list(df.columns) == ["Story", "Value"]


def test_truly_empty_table_returns_bare_dataframe():
    # A real ETABS table with no data can return an empty FieldsKeysIncluded
    # (no headers at all). Tables.get must hit its "no headers" branch and
    # return a bare, column-less empty DataFrame rather than erroring.
    app = make_mock()
    app.SapModel.DatabaseTables._empty = {"Story Drifts"}
    e = bind(app)
    df = e.tables.get("Story Drifts")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == []


def test_unknown_table_raises(etabs):
    with pytest.raises(ETABSError):
        etabs.tables.get("No Such Table")


def test_available_lists_keys_and_names(etabs):
    df = etabs.tables.available()
    assert set(["TableKey", "TableName"]).issubset(df.columns)
    assert "Story Forces" in df["TableKey"].tolist()
