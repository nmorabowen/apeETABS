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
