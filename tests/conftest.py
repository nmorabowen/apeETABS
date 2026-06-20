"""Shared pytest fixtures: a real apeETABS instance bound to a mock SapModel.

The ``etabs`` fixture instantiates ``apeETABS(attach=True)`` but never touches
COM: we hand it a :class:`MockETABS` / :class:`MockSapModel`, call the same
``_create_composites()`` the live ``begin()`` would, and flip ``_active`` on.
Composites (``e.units``, ``e.tables``, ``e.stories``) are the real classes, so
tests exercise production code against deterministic in-memory data.

Results/plotting tests should reuse this: build their fixture tables/stories via
``make_mock`` (or extend ``DEFAULT_TABLES`` / ``DEFAULT_STORIES``), bind them the
same way, then assert on the snapshots the composites produce.
"""

from __future__ import annotations

import pytest

from apeETABS import apeETABS

from ._mock_sapmodel import MockETABS, MockSapModel, StoriesSpec

# Stories: top-first (Story3 .. Story1), base at 0.0. Heights are per-story.
DEFAULT_STORIES = StoriesSpec(
    names=["Story3", "Story2", "Story1"],
    elevations=[12.0, 8.0, 4.0],
    heights=[4.0, 4.0, 4.0],
    base_name="Base",
    base_elevation=0.0,
    is_master=[True, False, False],
)

DEFAULT_TABLES: dict[str, tuple[list[str], list[list]]] = {
    "Story Drifts": (
        ["Story", "OutputCase", "StepType", "Direction", "Drift"],
        [
            ["Story3", "EQX", "Max", "X", "0.0012"],
            ["Story2", "EQX", "Max", "X", "0.0018"],
            ["Story1", "EQX", "Max", "X", "0.0009"],
        ],
    ),
    "Joint Displacements": (
        ["Story", "UniqueName", "OutputCase", "StepType", "Ux", "Uy", "Uz"],
        [
            ["Story3", "12", "EQX", "Max", "10.5", "0.1", "0.0"],
            ["Story2", "8", "EQX", "Max", "6.2", "0.05", "0.0"],
            ["Story1", "4", "EQX", "Max", "2.1", "0.02", "0.0"],
        ],
    ),
    "Story Forces": (
        ["Story", "OutputCase", "Location", "StepType",
         "P", "VX", "VY", "T", "MX", "MY"],
        [
            ["Story3", "EQX", "Top", "Max", "0.0", "100.0", "0.0", "0.0", "0.0", "400.0"],
            ["Story3", "EQX", "Bottom", "Max", "0.0", "100.0", "0.0", "0.0", "0.0", "0.0"],
            ["Story2", "EQX", "Top", "Max", "0.0", "200.0", "0.0", "0.0", "0.0", "0.0"],
            ["Story2", "EQX", "Bottom", "Max", "0.0", "200.0", "0.0", "0.0", "0.0", "0.0"],
            ["Story1", "EQX", "Top", "Max", "0.0", "300.0", "0.0", "0.0", "0.0", "0.0"],
            ["Story1", "EQX", "Bottom", "Max", "0.0", "300.0", "0.0", "0.0", "0.0", "0.0"],
        ],
    ),
    "Design Forces - Piers": (
        ["Story", "Pier", "Combo", "Location", "P", "V2", "V3", "T", "M2", "M3"],
        [
            ["Story3", "P1", "DStl1", "Top", "-100.0", "20.0", "1.0", "0.0", "5.0", "50.0"],
            ["Story3", "P1", "DStl1", "Bottom", "-110.0", "22.0", "1.0", "0.0", "5.0", "80.0"],
            ["Story3", "P1", "DStlE1", "Top", "-90.0", "40.0", "2.0", "0.0", "6.0", "120.0"],
            ["Story3", "P1", "DStlE1", "Bottom", "-95.0", "42.0", "2.0", "0.0", "6.0", "160.0"],
            ["Story1", "P1", "DStl1", "Top", "-300.0", "30.0", "1.0", "0.0", "5.0", "60.0"],
            ["Story1", "P1", "DStl1", "Bottom", "-320.0", "33.0", "1.0", "0.0", "5.0", "90.0"],
        ],
    ),
    "Tower and Base Story Definitions": (
        ["Tower", "BSName", "BSElev"],
        [["T1", "Base", "0.0"]],
    ),
    # A table with a column that mixes numbers and text -> must stay string.
    "Mixed Column": (
        ["A", "B"],
        [["1", "x"], ["2", "y"]],
    ),
    # A table with headers but zero rows.
    "Empty Table": (["Story", "Value"], []),
}


def make_mock(
    *,
    tables: dict | None = None,
    stories: StoriesSpec | None = None,
    units: tuple[int, int, int] = (4, 6, 2),
    locked: bool = False,
) -> MockETABS:
    """Build a MockETABS app, defaulting to the shared fixture data."""
    sap = MockSapModel(
        tables=DEFAULT_TABLES if tables is None else tables,
        stories=DEFAULT_STORIES if stories is None else stories,
        units=units,
        locked=locked,
    )
    return MockETABS(sap)


def bind(app: MockETABS) -> apeETABS:
    """Bind a real apeETABS to a mock app without any COM, returning it active."""
    e = apeETABS(attach=True)
    e.etabs = app
    e.SapModel = app.SapModel
    e._create_composites()
    e._active = True
    return e


@pytest.fixture
def mock_app() -> MockETABS:
    """A MockETABS application with the default fixtures."""
    return make_mock()


@pytest.fixture
def etabs(mock_app: MockETABS) -> apeETABS:
    """A real apeETABS bound to the default mock (units/tables/stories live)."""
    return bind(mock_app)
