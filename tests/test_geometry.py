"""Mock-backed shape tests for the ``e.geometry`` enumerator (ADR 0009, W1).

These exercise the real ``Geometry`` composite against the in-memory geometry
fixture (no ETABS), asserting the object-API getters are wired and shaped
correctly. The live gate (counts match ETABS' own tables) is a manual run.
"""

from __future__ import annotations


def test_points(geo_etabs):
    points = geo_etabs.geometry.points()
    assert len(points) == 8
    p1 = next(p for p in points if p["id"] == "1")
    assert (p1["x"], p1["y"], p1["z"]) == (0.0, 0.0, 0.0)
    p7 = next(p for p in points if p["id"] == "7")
    assert (p7["x"], p7["y"], p7["z"]) == (4.0, 4.0, 3.0)


def test_frames_connectivity_and_section(geo_etabs):
    frames = {f["id"]: f for f in geo_etabs.geometry.frames()}
    assert len(frames) == 7
    assert frames["C1"]["i"] == "1" and frames["C1"]["j"] == "5"
    assert frames["C1"]["section"] == "COL400"
    assert frames["B1"]["section"] == "BEAM300"


def test_frame_kind_classification(geo_etabs):
    frames = {f["id"]: f for f in geo_etabs.geometry.frames()}
    assert frames["C1"]["kind"] == "column"  # vertical
    assert frames["B1"]["kind"] == "beam"     # horizontal


def test_frame_releases_only_when_present(geo_etabs):
    frames = {f["id"]: f for f in geo_etabs.geometry.frames()}
    # B1 has an end moment release at J about local 3 (index 5).
    assert frames["B1"]["releases_j"] == [0, 0, 0, 0, 0, 1]
    # Columns are fully fixed -> no release keys emitted.
    assert "releases_i" not in frames["C1"]
    assert "releases_j" not in frames["C1"]


def test_areas(geo_etabs):
    areas = {a["id"]: a for a in geo_etabs.geometry.areas()}
    assert len(areas) == 2
    assert areas["S1"]["nodes"] == ["5", "6", "7", "8"]
    assert areas["S1"]["section"] == "SLAB200"
    assert areas["S1"]["is_opening"] is False


def test_restraints(geo_etabs):
    restraints = {r["node"]: r for r in geo_etabs.geometry.restraints()}
    assert set(restraints) == {"1", "2", "3", "4"}
    assert restraints["1"]["dofs"] == [1, 1, 1, 1, 1, 1]


def test_springs(geo_etabs):
    springs = {s["node"]: s for s in geo_etabs.geometry.springs()}
    assert set(springs) == {"7"}  # only joints with nonzero stiffness
    assert springs["7"]["k"] == [100.0, 100.0, 2000.0, 0.0, 0.0, 0.0]


def test_area_springs(geo_etabs_subgrade):
    springs = {s["area"]: s for s in geo_etabs_subgrade.geometry.area_springs()}
    assert set(springs) == {"F1"}  # only areas with an assigned property
    assert springs["F1"]["property"] == "Suelo"
    assert springs["F1"]["k"] == [0.0, 0.0, 15000.0]  # subgrade in local-3 (normal)


def test_no_area_springs_when_unassigned(geo_etabs):
    # The default fixture's areas carry no spring assignment.
    assert geo_etabs.geometry.area_springs() == []


def test_diaphragms(geo_etabs):
    diaphragms = geo_etabs.geometry.diaphragms()
    assert len(diaphragms) == 1
    d1 = diaphragms[0]
    assert d1["name"] == "D1"
    assert set(d1["nodes"]) == {"5", "6", "7", "8"}


def test_diaphragm_split_per_floor(geo_etabs_multistory):
    # One ETABS diaphragm name reused on two floors must split into two planar
    # rigid diaphragms, one per elevation.
    diaphragms = {d["name"]: d for d in geo_etabs_multistory.geometry.diaphragms()}
    assert set(diaphragms) == {"D1@3", "D1@6"}
    assert set(diaphragms["D1@3"]["nodes"]) == {"1", "2", "3", "4"}
    assert set(diaphragms["D1@6"]["nodes"]) == {"5", "6", "7", "8"}


def test_sections(geo_etabs):
    sections = {s["name"]: s for s in geo_etabs.geometry.sections()}
    assert set(sections) == {"COL400", "BEAM300", "SLAB200", "WALL250"}

    col = sections["COL400"]
    assert col["kind"] == "frame"
    assert col["material"] == "C30"
    assert col["props"]["A"] == 0.16
    assert col["props"]["J"] == 3.604e-3

    slab = sections["SLAB200"]
    assert slab["kind"] == "shell"
    assert slab["thickness"] == 0.20
    assert slab["area_kind"] == "slab"
    assert sections["WALL250"]["area_kind"] == "wall"


def test_materials(geo_etabs):
    materials = {m["name"]: m for m in geo_etabs.geometry.materials()}
    assert set(materials) == {"C30"}
    c30 = materials["C30"]
    assert c30["E"] == 2.5e7
    assert c30["nu"] == 0.2
    assert c30["rho"] == 2.4
