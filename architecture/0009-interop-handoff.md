# ETABS → apeGmsh interop — Handoff

Snapshot for whoever (human or agent) picks up the ETABS → apeGmsh meshing
pipeline next. Pairs with [ADR 0009](decisions/0009-apegmsh-export-meshing-pipeline.md)
(the decision) and [0009-build-plan.md](0009-build-plan.md) (the work breakdown).

## What this is

Take an analytical ETABS model and re-mesh it in **apeGmsh** so Gmsh produces a
refined, *conformal* FE mesh (shells + beams) that ETABS can't, then export an
OpenSees model. Two repos, decoupled by a neutral JSON contract:

```
apeETABS  ──.sm.json──▶  StructuralModel  ──▶  apeGmsh.interop  ──▶ OpenSees
(exporter, OAPI)         (this contract)       (import → mesh → apeSees)
```

## Status at handoff

| Piece | Where | State |
|---|---|---|
| Neutral contract (schema + 2 fixtures) | apeETABS `schema/` | ✅ **this PR** |
| ADR 0009 + build plan | apeETABS `architecture/` | ✅ **this PR** |
| apeGmsh importer — frames → beams (Phase 2) | apeGmsh `src/apeGmsh/interop/` | ✅ merged [apeGmsh#724](https://github.com/nmorabowen/apeGmsh/pull/724) |
| apeGmsh importer — areas → conformal shells (Phase 3) | apeGmsh | ✅ merged [apeGmsh#724](https://github.com/nmorabowen/apeGmsh/pull/724) |
| Distributed loads, self-mass, rigid diaphragms (Phase 4) | apeGmsh | ✅ merged [apeGmsh#725](https://github.com/nmorabowen/apeGmsh/pull/725) |
| **apeETABS extractor (`e.geometry` + `e.export`) — Phase 1** | apeETABS `src/` | ❌ **NOT built — the missing half** |
| Local-axis fidelity, openings, ETABS cross-check (Phase 5) | both | ❌ not started |

**The apeGmsh import side is done and proven against fixtures. The apeETABS
export side does not exist yet** — apeETABS today is a results reader with no
geometry enumeration. That extractor (build-plan W1/W2) is the critical next
piece: until it exists, the pipeline can't ingest a real `.EDB`.

## The contract (`schema/`)

- `structural_model.schema.json` — JSON Schema draft 2020-12, the source of
  truth. `schema_version` is pinned (`"0.1"`); both repos validate against it.
- `VERSION` — `0.1`.
- `examples/two_story_frame.sm.json` — frames-only fixture (Phase 2 gate).
- `examples/wall_slab_frame.sm.json` — wall+slab+frame (Phase 3/4 gate;
  exercises conformal junctions + a shell-backed diaphragm).

Both fixtures validate clean (`jsonschema` Draft202012Validator).

Key contract rules: IDs are ETABS names verbatim (traceability); geometry by
reference (coords only on nodes); sections/materials named once; `units` block
is a pinned contract with no cross-seam conversion.

## What the apeGmsh importer does (already on apeGmsh `main`)

`apeGmsh.interop.import_structural_model(g, model)` + `build_opensees(fem, model, result)`:

- nodes → points; **frames and area boundaries share one line per node-pair**
  (dedup edge map) → surfaces are conformal with frames by construction, no OCC
  `fragment` step.
- frames → `elasticBeamColumn` (bucketed by section + orientation for a valid
  geomTransf); areas → `ASDShellT3` + `ElasticMembranePlateSection`.
- loads (nodal / frame uniform / area pressure) → tributary **nodal** loads via
  `g.loads` + `pattern.from_model`.
- self-mass from density (`ρ·A`, `ρ·t`) → `mass_from_model`.
- rigid diaphragms → `rigidDiaphragm`, **auto-skipped when a shell area backs
  the diaphragm** (the shell provides the diaphragm action).

Verified: both fixtures solve static + modal; a frames-only model emits
`rigidDiaphragm` and solves. 8 self-contained tests (no live ETABS).

## Environment (critical)

- venv: `C:\Users\nmb\venv\opensees_env\Scripts\python.exe` — has
  gmsh + apeGmsh (editable) + openseespy + apeETABS.
- **Always `LADRUNO_OPENSEES_QUIET=1`** or a huge banner floods output.
- Run the apeGmsh interop demo / tests:
  ```bash
  LADRUNO_OPENSEES_QUIET=1 <venvpy> apeGmsh/examples/etabs_import_demo.py <fixture.sm.json>
  LADRUNO_OPENSEES_QUIET=1 <venvpy> -m pytest apeGmsh/tests/interop -q
  ```

## Key decisions (revisit if assumptions change)

- **Analytical target** (shells + beams), not solid continuum.
- **Conformality by shared topology**, not OCC `fragment` — explicit
  connectivity makes welding-by-construction simpler and more robust.
- **Loads → tributary nodal** (good with subdivided members); exact
  `eleLoad -beamUniform` / shell surface elements deferred.
- **Diaphragm auto-skip when shell-backed** — structurally correct, but a
  judgment call; flip to always-emit / always-shell if preferred.
- **Self-mass = self-weight** from `ρ`; real ETABS mass source (dead + fraction
  of live) is a Phase 5 refinement.

## Next action for the next session

**Build the apeETABS extractor (build-plan W1 + W2).** Add a read-only
`e.geometry` composite (`PointObj.GetAllPoints`, `FrameObj.GetAllFrames` +
`GetPoints`/`GetSection`/`GetLocalAxes`/`GetReleases`, `AreaObj.GetNameList` +
`GetPoints`/`GetProperty`, restraint/diaphragm queries) and an `e.export`
composite that assembles a `StructuralModel` and writes a `.sm.json` validated
against the schema. Gate: round-trip a reference `.EDB` and match ETABS' own
table counts. Then the demo runs on a *real* model, not just fixtures.
