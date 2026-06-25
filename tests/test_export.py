"""Round-trip tests for the ``e.export`` composite (ADR 0009, W2).

The exporter assembles a :class:`StructuralModel` from ``e.geometry`` and
writes the neutral ``.sm.json``. These assert: counts match the source model,
the document validates against the schema, and the written JSON re-parses to an
identical tree (build-plan W2 gate, mock-backed).
"""

from __future__ import annotations

import json

import pytest

from apeETABS.export.StructuralModel import SchemaError, StructuralModel, validate_document


def test_counts_match_source(geo_etabs):
    model = geo_etabs.export.structural_model()
    assert len(model.nodes) == 8
    assert len(model.frames) == 7
    assert len(model.areas) == 2
    assert len(model.sections) == 4
    assert len(model.materials) == 1
    assert len(model.restraints) == 4
    assert len(model.diaphragms) == 1


def test_units_block(geo_etabs):
    doc = geo_etabs.export.structural_model().to_dict()
    assert doc["schema_version"] == "0.1"
    assert doc["units"] == {"length": "m", "force": "kN"}


def test_area_kind_resolved_from_section(geo_etabs):
    areas = {a.id: a for a in geo_etabs.export.structural_model().areas}
    assert areas["S1"].kind == "slab"
    assert areas["W1"].kind == "wall"


def test_loads_assembled_per_pattern(geo_etabs):
    loads = {p.name: p for p in geo_etabs.export.structural_model().loads}
    assert set(loads) == {"Dead", "Live"}

    dead = loads["Dead"]
    assert len(dead.area) == 1
    assert dead.area[0].area == "S1"
    assert dead.area[0].direction == "Z"
    assert dead.area[0].value == -5.0
    assert len(dead.frame) == 1
    assert dead.frame[0].frame == "B1"

    live = loads["Live"]
    assert len(live.nodal) == 1
    assert live.nodal[0].node == "7"
    assert live.nodal[0].force_xyz == (5.0, 0.0, 0.0)


def test_exotic_props_degrade_gracefully(geo_etabs_exotic):
    # An auto-select section + a uniaxial material + an unreadable material
    # must not abort the export.
    model = geo_etabs_exotic.export.structural_model()  # validates, must not raise
    sections = {s.name: s for s in model.sections}
    # Auto-select: emitted, but no material and no computed props.
    assert sections["AUTO"].material is None
    assert not sections["AUTO"].props
    # Uniaxial rebar material falls back to E with nu=0; Ghost is dropped.
    materials = {m.name: m for m in model.materials}
    assert set(materials) == {"Rebar"}
    assert materials["Rebar"].nu == 0.0
    assert materials["Rebar"].E == 2.0e8


def test_shell_uniform_load_sets(geo_etabs_loadsets):
    # Gravity applied via a named load set assigned to a slab (DatabaseTables
    # path) surfaces as gravity area loads per pattern.
    loads = {p.name: p for p in geo_etabs_loadsets.export.structural_model().loads}
    dead_areas = {(a.area, a.value, a.direction) for a in loads["Dead"].area}
    assert ("S1", 2.94, "gravity") in dead_areas
    live_areas = {(a.area, a.value, a.direction) for a in loads["Live"].area}
    assert ("S1", 1.96, "gravity") in live_areas


def test_springs_exported(geo_etabs):
    model = geo_etabs.export.structural_model()
    springs = {s.node: s for s in model.springs}
    assert set(springs) == {"7"}
    assert springs["7"].k == (100.0, 100.0, 2000.0, 0.0, 0.0, 0.0)
    # And it round-trips through the schema.
    doc = model.to_dict()
    assert doc["springs"] == [{"node": "7", "k": [100.0, 100.0, 2000.0, 0.0, 0.0, 0.0]}]


def test_area_springs_exported(geo_etabs_subgrade):
    model = geo_etabs_subgrade.export.structural_model()
    springs = {s.area: s for s in model.area_springs}
    assert set(springs) == {"F1"}
    assert springs["F1"].k == (0.0, 0.0, 15000.0)
    assert springs["F1"].property == "Suelo"
    # And it round-trips through the schema (validated by structural_model()).
    doc = model.to_dict()
    assert doc["area_springs"] == [
        {"area": "F1", "k": [0.0, 0.0, 15000.0], "property": "Suelo"}
    ]


def test_area_spring_referential_integrity_caught():
    # An area_spring pointing at a non-existent area must fail validation.
    doc = StructuralModel(
        units={"length": "m", "force": "kN"},
        nodes=[],
        frames=[],
    ).to_dict()
    doc["areas"] = [
        {"id": "F1", "nodes": ["1", "2", "3"], "section": "MAT"},
    ]
    doc["nodes"] = [{"id": n, "x": 0.0, "y": 0.0, "z": 0.0} for n in ("1", "2", "3")]
    doc["area_springs"] = [{"area": "GHOST", "k": [0.0, 0.0, 1.0]}]
    with pytest.raises(SchemaError):
        validate_document(doc)


def test_diaphragm_unions_joint_and_area_membership(geo_etabs):
    diaphragms = {d.name: d for d in geo_etabs.export.structural_model().diaphragms}
    assert set(diaphragms) == {"D1"}
    # 5,6 via joint-level; 7,8 via the slab's area-level assignment.
    assert set(diaphragms["D1"].nodes) == {"5", "6", "7", "8"}


def test_validates_against_schema(geo_etabs):
    # structural_model() with no path still validates by default.
    model = geo_etabs.export.structural_model()
    model.validate()  # must not raise
    validate_document(model.to_dict())  # explicit, must not raise


def test_round_trip_json_identical(geo_etabs, tmp_path):
    model = geo_etabs.export.structural_model()
    out = tmp_path / "model.sm.json"
    written = model.write(out)
    assert written == out

    reparsed = json.loads(out.read_text(encoding="utf-8"))
    assert reparsed == model.to_dict()


def test_orphan_joint_dropped(geo_etabs_orphan):
    # Joint 99 connects to no member -> dropped from the export, and every
    # reference to it (restraint, nodal load, diaphragm membership) scrubbed.
    # It also carries a real nodal load -> dropping it warns (silent loss).
    with pytest.warns(UserWarning, match="loaded free joint.*'99'"):
        model = geo_etabs_orphan.export.structural_model()
    ids = {n.id for n in model.nodes}
    assert ids == {"1", "2", "3"}
    assert "99" not in ids
    assert all(r.node != "99" for r in model.restraints)
    assert {r.node for r in model.restraints} == {"1"}
    # The diaphragm keeps its real members (2, 3) without the orphan.
    diaphragms = {d.name: d for d in model.diaphragms}
    assert all("99" not in d.nodes for d in model.diaphragms)
    assert set(next(iter(diaphragms.values())).nodes) == {"2", "3"}
    # The Dead pattern carried only the orphan's load -> dropped entirely.
    assert [p.name for p in model.loads] == []


def test_referential_integrity_caught():
    # A frame pointing at a non-existent node must fail validation.
    bad = StructuralModel(
        units={"length": "m", "force": "kN"},
        nodes=[],
        frames=[],
    )
    doc = bad.to_dict()
    doc["frames"] = [{"id": "B", "i": "999", "j": "998", "section": "S"}]
    with pytest.raises(SchemaError):
        validate_document(doc)


def test_bad_dof_mask_caught():
    doc = StructuralModel(
        units={"length": "m", "force": "kN"},
        nodes=[],
        frames=[],
    ).to_dict()
    doc["restraints"] = [{"node": "1", "dofs": [1, 1, 1]}]  # too short
    # node "1" also absent -> either way validation must reject.
    with pytest.raises(SchemaError):
        validate_document(doc)
