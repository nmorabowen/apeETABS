# ADR 0009 — ETABS → apeGmsh export & meshing pipeline

**Status:** Proposed

## Context

We want to take an analytical ETABS model and re-mesh it in
[apeGmsh](../../../apeGmsh), letting Gmsh produce a refined, *conformal* FE
mesh that ETABS cannot. The end product is an OpenSees model emitted by
apeGmsh's existing broker (`FEMData` → `g.opensees.export`).

The two libraries have fundamentally different mental models:

- **ETABS** is an *analytical line/area model*. Frames are 1-D members
  (one element ≈ one member), areas are 2-D shells, joints are points.
  Section/material/restraint/diaphragm/load data hang off those objects.
- **apeGmsh** is *geometry-first*. It builds OCC entities, meshes them
  conformally, attaches physical groups / constraints / loads, and exports
  to a solver. Its public API today is OCC-solid oriented (boxes, cylinders,
  `fragment_all`, `W_solid` sections), but it supports explicit
  point→curve→surface geometry and 1-D/2-D meshing (`generate(dim=2)`).

apeETABS today (v0.1.0) is a **results reader**. It has no geometry
enumeration layer — there is no extractor that returns *all* points, frames,
and areas of a model. That layer must be built regardless of the meshing
target.

Three decisions were taken before writing this ADR (see "Decisions locked"
below): the meshing target, the integration seam, and that this ADR is a
plan-only deliverable (no code yet).

## Decisions locked (by the engineer)

1. **Meshing target: analytical shells + beams.** Frames → 1-D beam mesh;
   areas → 2-D shell mesh. We *preserve the ETABS idealization* and add the
   things ETABS does poorly: conformal wall/slab/beam interfaces, controlled
   per-member refinement, beam-in-shell embedding. **Not** solid-continuum
   (3-D section extrusion) — that is a separate, heavier track, explicitly
   out of scope here.
2. **Integration seam: a neutral JSON schema.** apeETABS *writes* a versioned
   `StructuralModel` document; apeGmsh *reads* it. Neither library imports the
   other. The schema is the contract; each end is testable in isolation
   against a fixture JSON.
3. **This ADR is plan-only.** No production code lands with it.

## Architecture

```
 apeETABS                    neutral contract                 apeGmsh
 ┌──────────────┐    write   ┌────────────────────┐   read   ┌──────────────┐
 │ e.geometry   │ ─────────▶ │ StructuralModel    │ ───────▶ │ importer →   │
 │  (OAPI       │  *.sm.json │  nodes / frames /  │          │ geometry →   │
 │   enumerator)│            │  areas / sections /│          │ mesh → PGs → │
 └──────────────┘            │  materials /       │          │ constraints →│
                             │  restraints /      │          │ OpenSees     │
                             │  diaphragms / loads│          └──────────────┘
                             └────────────────────┘
```

The seam is a serializable document, *not* a Python import. Consequences:

- apeETABS gains an **exporter** (`e.export.structural_model(path)`), built
  on a new read-only **geometry enumerator** composite (`e.geometry`).
- apeGmsh gains an **importer** (`g.import_structural_model(path)` or a small
  free function) that builds geometry + physical groups from the document.
- The schema lives once, versioned, with a `schema_version` field. A fixture
  `.sm.json` checked into both repos lets each side develop and test without
  the other (and without live ETABS or a Gmsh session).

## The neutral schema (`StructuralModel`)

A single JSON document. Sketch (field names indicative, not final):

```jsonc
{
  "schema_version": "0.1",
  "units": { "length": "m", "force": "kN" },     // pinned contract, see Risk U
  "source": { "tool": "ETABS", "model": "tower.EDB", "exported": "..." },

  "nodes": [
    { "id": "12", "x": 0.0, "y": 0.0, "z": 3.0, "story": "Story1" }
  ],
  "frames": [
    { "id": "B7", "i": "12", "j": "18", "section": "W360", "material": "A992",
      "rotation": 0.0, "releases_i": [0,0,0,0,0,0], "releases_j": [0,0,0,0,0,0],
      "kind": "beam" }                            // beam | column | brace
  ],
  "areas": [
    { "id": "W3", "nodes": ["12","18","42","36"], "section": "WALL300",
      "material": "C30", "thickness": 0.30, "kind": "wall",   // wall | slab | shell
      "openings": [ ["a","b","c","d"] ],
      "local_axis_deg": 0.0 }
  ],
  "sections": [
    { "name": "W360", "kind": "frame", "props": { "A": ..., "Iy": ..., "Iz": ..., "J": ... } },
    { "name": "WALL300", "kind": "shell", "thickness": 0.30 }
  ],
  "materials": [
    { "name": "A992", "E": 2.0e8, "nu": 0.3, "rho": 7.85, "fy": 3.45e5 }
  ],
  "restraints": [ { "node": "1", "dofs": [1,1,1,1,1,1] } ],
  "diaphragms": [ { "name": "D1", "story": "Story1", "nodes": ["12","18","42"] } ],
  "loads": {
    "Dead":   { "nodal": [...], "frame": [...], "area": [...] },
    "Live":   { ... }
  }
}
```

Design rules:

- **IDs are strings, carried verbatim from ETABS object names.** This is the
  traceability key (Risk T): ETABS name → schema id → Gmsh physical group →
  mesh node, so results map back.
- **Geometry by reference, not by coordinate.** Frames/areas reference node
  ids; coordinates live only on nodes. One source of truth for position.
- **Section/material are names**, defined once in their own arrays. The
  importer turns each unique name into a physical group and an OpenSees
  material/section.
- The schema is **solver-neutral** in spirit but practical: it encodes what
  apeGmsh needs to build geometry + the metadata OpenSees needs downstream.

## ETABS → apeGmsh → OpenSees mapping

| ETABS object | Schema | apeGmsh build | OpenSees target |
|---|---|---|---|
| Point / joint | `node` | geometry point | `node` |
| Frame (beam/col/brace) | `frame` | curve → 1-D mesh; PG per section | `forceBeamColumn` + `geomTransf` |
| Area (wall/slab/shell) | `area` | planar surface → 2-D mesh; PG per section | `ShellMITC4` / `ShellDKGT` |
| Restraint | `restraint` | PG of points → `fix` / `face_sp` | `fix` |
| Rigid diaphragm | `diaphragm` | `g.constraints.rigid_diaphragm` | `rigidDiaphragm` |
| Frame–shell joint | (implicit) | `fragment_all` + `embed` / `tie` | conformal nodes / `ASDEmbeddedNodeElement` |
| Load pattern | `loads` | `g.loads.pattern(...)` | `pattern` / `load` / `eleLoad` |
| Section / material | `sections`/`materials` | PG names | `nDMaterial` / `section` |

The meshing value-add (the reason to do this at all): Gmsh delivers
**conformal wall–slab–beam interfaces**, **per-member / per-story
refinement**, **beam-in-shell embedding**, and traceable PG naming — all
things that are manual or impossible in ETABS.

## Phased plan

Each phase has an explicit verification gate (CLAUDE.md §4).

1. **Schema + extractor.**
   New read-only `e.geometry` composite wrapping `cPointObj.GetAllPoints`,
   `cFrameObj.GetAllFrames`, `cAreaObj.GetAllNames` (+ `GetPoints`,
   `GetProperty`, restraint/diaphragm queries). New `e.export.structural_model`.
   *Verify:* round-trip a reference `.EDB` to `.sm.json`; node/frame/area
   counts match ETABS' own table counts.

2. **MVP skeleton (points + frames only).**
   apeGmsh importer builds points + curves, meshes 1-D, PG per section,
   exports OpenSees. *Verify:* a 2-story moment frame meshes as beams and the
   exported model runs a gravity analysis to convergence.

3. **Areas → shells, conformal.**
   Planar surfaces from area node loops; `fragment_all`; frames embedded into
   shells. *Verify:* a wall+slab+frame model produces **one conformal mesh** —
   interfaces share nodes; no orphan/duplicate nodes at junctions.

4. **BCs / diaphragms / loads / masses.**
   Restraints → `fix`; diaphragms → `rigid_diaphragm`; load patterns →
   `g.loads`. *Verify:* restraints, a rigid diaphragm, and one load pattern
   survive end-to-end into the OpenSees export and the model solves.

5. **Fidelity & validation.**
   Frame local-axis rotation → `geomTransf`; shell local axes; wall/slab
   openings as surface holes; per-member/per-story mesh-size controls; a
   benchmark cross-check of static response (e.g. base shear, a roof
   displacement) against ETABS' own analysis within tolerance.

## Key risks

- **Risk P — non-planar ETABS quads.** Area objects need not be planar.
  Gmsh planar surfaces require valid faces → add a coplanarity check + warn /
  triangulate / project. Surface healing in Phase 3.
- **Risk A — local axes.** Frame local-2 rotation and shell local-1 must
  carry through to `geomTransf` / shell orientation, or member forces are
  wrong. Encoded in the schema (`rotation`, `local_axis_deg`); consumed in
  Phase 5.
- **Risk U — units.** apeETABS has a report-unit system; apeGmsh is
  unit-agnostic numeric. The schema's `units` block is the pinned contract;
  the extractor emits in one declared system, the importer trusts it. No
  implicit conversion across the seam.
- **Risk T — traceability.** ETABS name ↔ schema id ↔ Gmsh PG ↔ mesh node,
  preserved by string ids + PG naming convention, so post-solve results map
  back to ETABS objects.
- **Risk C — conformality at junctions.** Walls, slabs, and frames meeting at
  a story line must share nodes after meshing. `fragment_all` + `embed`/`tie`
  is the mechanism; Phase 3 is where this is proven, and it is the highest-risk
  technical step.

## Open questions (deferred, not blocking the plan)

- Frame section fidelity: pass ETABS computed `A/I/J` properties through, or
  re-derive from a named section library on the apeGmsh side?
- Shell formulation choice (`ShellMITC4` vs `ShellDKGT`) — fixed default or
  schema-driven per area?
- Mesh-size policy: global default vs per-story vs per-member field; where
  does the engineer express intent — in the schema, or only on the apeGmsh
  session?
- Links / springs / panel zones: out of the v1 schema; revisit after Phase 4.

## Consequences

- apeETABS grows a **geometry-read** capability it does not have today
  (complements the existing results-read). This is reusable beyond apeGmsh
  (e.g. any external FE export).
- The neutral schema is a maintained artifact with its own version. A breaking
  change to it is a coordinated change across both repos — the `schema_version`
  field makes mismatches loud.
- We deliberately defer solid-continuum (3-D) modeling. If it is ever wanted,
  it reuses the same extractor and schema; only the apeGmsh importer changes
  (curves/surfaces → swept solids).
```
