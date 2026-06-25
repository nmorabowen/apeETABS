# Build plan — ETABS → apeGmsh export & meshing pipeline

Companion to [ADR 0009](decisions/0009-apegmsh-export-meshing-pipeline.md).
Translates the five ADR phases into concrete packages, classes, and methods
across both repos, with sequencing and verification gates.

## New code, by repo

```
apeETABS/
  schema/                          ← shared contract (canonical, mirror into apeGmsh)
    structural_model.schema.json   ← JSON Schema (draft 2020-12), source of truth
    VERSION                         ← "0.1"
    examples/
      two_story_frame.sm.json       ← fixture, Phase 2 gate
      wall_slab_frame.sm.json       ← fixture, Phase 3 gate
  src/apeETABS/
    geometry/                       ← NEW read composite (e.geometry)
      Geometry.py                   ← facade, registered in _session.py
      _points.py _frames.py _areas.py
      _restraints.py _diaphragms.py _props.py
    export/                         ← NEW serialization composite (e.export)
      StructuralModel.py            ← dataclasses + to_dict/from_dict/validate
      _builder.py                   ← assembles model from e.geometry
      _loads.py                     ← load-pattern assembly

apeGmsh/
  src/apeGmsh/interop/             ← NEW
    etabs_import.py                ← import_structural_model(g, model)
    _schema.py                     ← mirror reader dataclasses (parses the SAME JSON)
```

## Workstreams

### W0 — Contract (build first; unblocks everything)

- `structural_model.schema.json` — canonical JSON Schema. Both repos validate
  against it; mismatch is loud via `schema_version`.
- Two fixture `.sm.json` files, hand-authored. These are the test doubles:
  apeGmsh's importer is built/tested against them with **no** ETABS or
  apeETABS dependency; apeETABS's exporter is done when it *reproduces* a
  fixture from a real `.EDB`.

### W1 — apeETABS geometry extractor (`e.geometry`)

Read-only composite, OAPI **object-API** backend (not display tables —
connectivity needs `GetPoints`; note this departure from ADR 0003).

| Method | OAPI calls | Returns |
|---|---|---|
| `points()` | `PointObj.GetAllPoints` / `GetCoordCartesian` | `[{id,x,y,z,story}]` |
| `frames()` | `FrameObj.GetAllFrames`, `GetPoints`, `GetSection`, `GetLocalAxes`, `GetReleases` | `[{id,i,j,section,rotation,releases…}]` |
| `areas()` | `AreaObj.GetNameList`, `GetPoints`, `GetProperty`, `GetLocalAxes` | `[{id,nodes[],section,local_axis}]` |
| `restraints()` | `PointObj.GetRestraint` | `[{node,dofs}]` |
| `diaphragms()` | `PointObj.GetDiaphragm` (+ story diaphragms) | `[{name,story,nodes[]}]` |
| `sections()` / `materials()` | `PropFrame.*`, `PropArea.*`, `PropMaterial.GetMaterial`/`GetMPIsotropic` | named property bags |

**Verify:** extend `tests/_mock_sapmodel.py`; mock-backed shape tests. Live
gate: counts match ETABS table counts on a reference `.EDB`.

### W2 — apeETABS exporter (`e.export`)

- `StructuralModel.py` — dataclasses mirroring the schema + `validate()`.
- `_builder.py` — `e.export.structural_model(path)`: pull from `e.geometry`,
  assemble, write JSON, validate.
- `_loads.py` — per-pattern nodal/frame/area loads.

**Verify:** round-trip a reference `.EDB` → JSON → re-parse → identical tree;
validates against schema.

### W3 — apeGmsh importer (critical path)

- `_schema.py` — parses the same JSON.
- `import_structural_model(g, model)`:
  1. nodes → `g.model.geometry.add_point`, keep `etabs_id → gmsh_tag` map
  2. frames → curves; label per frame, PG per section
  3. areas → planar surface from node loop; PG per section *(Phase 3)*
  4. `fragment_all()`; `embed` frames into shells *(Phase 3)*
  5. restraints → PG; diaphragms → `rigid_diaphragm`; loads → `g.loads.pattern`

**Verify (Phase 2):** import `two_story_frame.sm.json`, mesh 1-D, export
OpenSees, gravity converges. **(Phase 3):** import `wall_slab_frame.sm.json`
→ one conformal mesh, no duplicate nodes at junctions.

## Sequencing & critical path

```
W0 schema+fixtures ──┬──▶ W1 e.geometry ──▶ W2 e.export ──┐
                     │                                     ├──▶ live round-trip
                     └──▶ W3 importer (P2) ──▶ (P3) ───────┘
```

- Critical path runs through **apeGmsh W3** (importer + conformality), not the
  extractor — the extractor is mechanical OAPI wrapping.
- W1/W2 and W3 are fully parallel after W0 (fixtures decouple them).
- Phases 4–5 layer onto whichever fixture exists.

## Build-time decisions

1. **Schema dataclasses duplicated per repo** (canonical = the JSON Schema).
   Consistent with "neutral JSON, not shared package."
2. **Importer = free function** `import_structural_model(g, model)` for v1 — no
   new composite to register.
3. **Extractor uses object-API throughout** (loads included), tables only as a
   fallback for a load type with no clean object getter.
