"""Tests for the Stories composite: elevation mapping + step axis."""

from __future__ import annotations

import numpy as np
import pandas as pd


def test_names_include_base_last(etabs):
    assert etabs.stories.names == ["Base", "Story3", "Story2", "Story1"]


def test_mapping_includes_base(etabs):
    m = etabs.stories.mapping
    assert m == {"Base": 0.0, "Story3": 12.0, "Story2": 8.0, "Story1": 4.0}


def test_base_story_read_from_base_table(etabs):
    # "Tower and Base Story Definitions" provides Base/0.0.
    assert etabs.stories.data.base_name == "Base"
    assert etabs.stories.data.base_elevation == 0.0


def test_map_elevation_adds_column(etabs):
    df = pd.DataFrame({"Story": ["Story3", "Story1", "Base"]})
    out = etabs.stories.map_elevation(df)
    assert out["Elevation"].tolist() == [12.0, 4.0, 0.0]


def test_map_elevation_top_bottom(etabs):
    df = pd.DataFrame(
        {
            "Story": ["Story3", "Story3", "Story1"],
            "Location": ["Top", "Bottom", "Bottom"],
        }
    )
    out = etabs.stories.map_elevation_top_bottom(df)
    # Top -> own elevation; Bottom -> the story below.
    # Story3 below is Story2 (8.0); Story1 below is Base (0.0).
    assert out["Elevation"].tolist() == [12.0, 8.0, 0.0]


def test_step_axis_shape_and_endpoints(etabs):
    elevs = etabs.stories.elevations  # [0, 12, 8, 4] in insert order
    axis = etabs.stories.step_axis()
    # repeat-each then trim first/last, flipped: length = 2*N - 2.
    assert axis.shape[0] == 2 * len(elevs) - 2
    expected = np.flip(np.repeat(elevs, 2)[1:-1])
    np.testing.assert_allclose(axis, expected)


def test_step_axis_scale(etabs):
    a1 = etabs.stories.step_axis()
    a2 = etabs.stories.step_axis(scale=1000.0)
    np.testing.assert_allclose(a2, a1 / 1000.0)


def test_refresh_clears_cache(etabs):
    _ = etabs.stories.data
    assert etabs.stories._cache is not None
    etabs.stories.refresh()
    assert etabs.stories._cache is None
