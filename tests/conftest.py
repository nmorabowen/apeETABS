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

from ._mock_sapmodel import (
    AreaSpec,
    AreaUnifLoad,
    FrameDistLoad,
    FrameSpec,
    GeometrySpec,
    MockETABS,
    MockSapModel,
    PointLoad,
    StoriesSpec,
)

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


# Geometry-read fixture (ADR 0009): a small wall+slab+frame box. 8 joints,
# 4 columns + 3 beams, a slab + a wall, 4 fixed base joints, one rigid
# diaphragm at the top story, and Dead/Live loads exercising all three load
# getters. Mirrors schema/examples/wall_slab_frame.sm.json.
DEFAULT_GEOMETRY = GeometrySpec(
    points={
        "1": (0.0, 0.0, 0.0), "2": (4.0, 0.0, 0.0),
        "3": (4.0, 4.0, 0.0), "4": (0.0, 4.0, 0.0),
        "5": (0.0, 0.0, 3.0), "6": (4.0, 0.0, 3.0),
        "7": (4.0, 4.0, 3.0), "8": (0.0, 4.0, 3.0),
    },
    restraints={n: [True] * 6 for n in ("1", "2", "3", "4")},
    # A soil-type support spring on a free joint (translational only).
    springs={"7": [100.0, 100.0, 2000.0, 0.0, 0.0, 0.0]},
    # Joints 5,6 carry the diaphragm at the joint level (2 = FromShellObject);
    # joints 7,8 do NOT — they reach D1 only via the slab's area-level
    # assignment (AreaObj.GetDiaphragm on S1), exercising both capture paths.
    point_diaphragm={"5": (2, "D1"), "6": (2, "D1")},
    frames={
        "C1": FrameSpec("1", "5", "COL400"),
        "C2": FrameSpec("2", "6", "COL400"),
        "C3": FrameSpec("3", "7", "COL400"),
        "C4": FrameSpec("4", "8", "COL400"),
        "B1": FrameSpec("6", "7", "BEAM300",
                        releases_j=[False, False, False, False, False, True]),
        "B2": FrameSpec("7", "8", "BEAM300"),
        "B3": FrameSpec("8", "5", "BEAM300"),
    },
    areas={
        "S1": AreaSpec(["5", "6", "7", "8"], "SLAB200", diaphragm="D1"),
        "W1": AreaSpec(["1", "2", "6", "5"], "WALL250"),
    },
    frame_sections={
        "COL400": {"material": "C30",
                   "props": {"A": 0.16, "Iy": 2.133e-3, "Iz": 2.133e-3, "J": 3.604e-3}},
        "BEAM300": {"material": "C30",
                    "props": {"A": 0.12, "Iy": 9.0e-4, "Iz": 1.6e-3, "J": 1.78e-3}},
    },
    slab_sections={"SLAB200": {"material": "C30", "thickness": 0.20}},
    wall_sections={"WALL250": {"material": "C30", "thickness": 0.25}},
    materials={"C30": {"E": 2.5e7, "nu": 0.2, "rho": 2.4}},
    area_loads={"S1": [AreaUnifLoad("Dead", -5.0, direction=6)]},      # 6 = global Z
    frame_loads={"B1": [FrameDistLoad("Dead", -10.0, direction=6)]},
    point_loads={"7": [PointLoad("Live", f=(5.0, 0.0, 0.0))]},
)


def make_mock(
    *,
    tables: dict | None = None,
    stories: StoriesSpec | None = None,
    units: tuple[int, int, int] = (4, 6, 2),
    locked: bool = False,
    geometry: GeometrySpec | None = None,
) -> MockETABS:
    """Build a MockETABS app, defaulting to the shared fixture data."""
    sap = MockSapModel(
        tables=DEFAULT_TABLES if tables is None else tables,
        stories=DEFAULT_STORIES if stories is None else stories,
        units=units,
        locked=locked,
        geometry=geometry,
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


@pytest.fixture
def geo_etabs() -> apeETABS:
    """A real apeETABS bound to a mock carrying the geometry fixture (ADR 0009)."""
    return bind(make_mock(geometry=DEFAULT_GEOMETRY))


# Shell uniform load sets (the DatabaseTables load path): the set "Entrepiso"
# defines Dead/Live pressures; the assignment table maps area S1 to that set.
GEO_LOADSET_TABLES = {
    "Shell Uniform Load Sets": (
        ["Name", "LoadPattern", "LoadValue", "GUID"],
        [["Entrepiso", "Dead", "2.94", ""], ["Entrepiso", "Live", "1.96", ""]],
    ),
    "Area Load Assignments - Uniform Load Sets": (
        ["Story", "Label", "UniqueName", "LoadSet"],
        [["Story1", "S1", "S1", "Entrepiso"]],
    ),
}


# Exotic properties that the basic getters can't fully read (real-model
# variety): an auto-select frame section (no material/props), a uniaxial
# rebar material (not isotropic), and a fully-unreadable material.
EXOTIC_GEOMETRY = GeometrySpec(
    points={"1": (0.0, 0.0, 0.0), "2": (0.0, 0.0, 3.0)},
    frames={
        "X": FrameSpec("1", "2", "AUTO"),   # AUTO absent below -> getters ret=1
        "Y": FrameSpec("1", "2", "COLR"),
        "Z": FrameSpec("1", "2", "COLZ"),
    },
    frame_sections={
        "COLR": {"material": "Rebar", "props": {"A": 0.1}},
        "COLZ": {"material": "Ghost", "props": {"A": 0.1}},
    },
    materials={"Rebar": {"E": 2.0e8, "nu": 0.0, "uniaxial": True}},  # Ghost absent
)


@pytest.fixture
def geo_etabs_exotic() -> apeETABS:
    """apeETABS whose model has sections/materials the basic getters can't read."""
    return bind(make_mock(geometry=EXOTIC_GEOMETRY))


# Two slabs at different elevations sharing the single diaphragm name "D1"
# (how ETABS models a multi-story rigid floor) — must split into one planar
# diaphragm per floor.
MULTISTORY_GEOMETRY = GeometrySpec(
    points={
        "1": (0.0, 0.0, 3.0), "2": (4.0, 0.0, 3.0),
        "3": (4.0, 4.0, 3.0), "4": (0.0, 4.0, 3.0),
        "5": (0.0, 0.0, 6.0), "6": (4.0, 0.0, 6.0),
        "7": (4.0, 4.0, 6.0), "8": (0.0, 4.0, 6.0),
    },
    areas={
        "S1": AreaSpec(["1", "2", "3", "4"], "SLAB", diaphragm="D1"),
        "S2": AreaSpec(["5", "6", "7", "8"], "SLAB", diaphragm="D1"),
    },
    slab_sections={"SLAB": {"material": "C30", "thickness": 0.2}},
    materials={"C30": {"E": 2.5e7, "nu": 0.2, "rho": 2.4}},
)


@pytest.fixture
def geo_etabs_multistory() -> apeETABS:
    """apeETABS with one diaphragm name reused across two floors."""
    return bind(make_mock(geometry=MULTISTORY_GEOMETRY))


@pytest.fixture
def geo_etabs_loadsets() -> apeETABS:
    """apeETABS whose model applies gravity via shell uniform load sets."""
    return bind(
        make_mock(
            geometry=DEFAULT_GEOMETRY,
            tables={**DEFAULT_TABLES, **GEO_LOADSET_TABLES},
        )
    )
