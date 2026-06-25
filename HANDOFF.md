# apeETABS — Handoff

Snapshot for whoever (human or agent) picks this up next. Pairs with
[`README.md`](README.md) (user-facing) and
[`architecture/BUILD_PLAN.md`](architecture/BUILD_PLAN.md) (build state).

## What this is

A human-centric Python wrapper over the **CSI ETABS Open API (OAPI)**, in the
apeGmsh house style (session facade + composites). **Parse + plot + seismic
irregularities** are complete and tested; the **ETABS→apeGmsh interop**
(`e.geometry` extractor + `e.export`, ADR 0009) is complete and live-validated;
editing / creation / standards / agentic are **scaffolded**.

- Repo: https://github.com/nmorabowen/apeETABS (public, `main`)
- Replaces an old class (reference only): `C:\Users\nmb\Documents\Github\APE_Public\ETABS_to_python`

## Status at handoff

- Planned phases **P0–P9 complete** + the **ADR 0009 ETABS→apeGmsh interop**
  (extractor + exporter) built and **validated end-to-end on real models**.
- **250 tests pass, ruff clean.** Automated tests are mock-backed (no live ETABS);
  the interop has additionally been live-validated against the reference `.EDB`s.
- Pushed to GitHub `main`; PRs #4–#8 merged.

| Area | State |
|---|---|
| Connection, units (+baseUnits bridge), tables, stories | complete |
| Results: Displacements, StoryDrifts, StoryForces, WallForces, Profile | complete |
| Plotting: drift/displacement/story_shear/story_forces/wall_forces + style | complete |
| Seismic irregularities (CM/CR, soft story, torsion, mass) | complete |
| **ADR 0009 `e.geometry`** (points/frames/areas/restraints/springs/diaphragms/sections/materials) | **complete + live-validated** |
| **ADR 0009 `e.export`** (`StructuralModel` → `.sm.json`, schema-validated) | **complete + live-validated** |
| Editing: lock guard + `e.edit`/`e.assign` | **scaffold** (rename/delete/restraint impl; rest stubs) |
| Creation: `e.define`/`e.create`/`e.new` | **scaffold** (material/frame_rect/load_pattern/point/frame impl; rest stubs) |
| Standards presets `e.standards` (ADR 0008) | **scaffold** (define/assign primitives done; per-code logic pending) |
| Agentic: spec pipeline, AgentPolicy, ReportSpec | **scaffold** (read tier real; Model/EditSpec stubs) |

## ADR 0009 — ETABS → apeGmsh interop (the latest work)

The big new capability: extract a real ETABS model into a neutral
`StructuralModel` JSON document that apeGmsh re-meshes into a **solving**
OpenSees model. See [`architecture/decisions/0009-*.md`](architecture/decisions/)
and the schema at `schema/structural_model.schema.json` (mirrored read-side in
the apeGmsh repo).

**Built (all merged to `main`):**
- `e.geometry` — read-only object-API enumerator: `points`, `frames`, `areas`,
  `restraints`, `springs`, `diaphragms`, `sections`, `materials`. Best-effort
  property reads (auto-select / nonprismatic sections, uniaxial materials never
  abort the export).
- `e.export.structural_model(path)` — assembles + validates (structural check +
  full JSON Schema when `jsonschema` present) + writes `.sm.json`.
- Diaphragms captured at the **area level** (`AreaObj.GetDiaphragm` ∪ joint
  level) and **split per floor by elevation** (ETABS reuses one name across
  stories).
- Loads: object-API nodal/frame/area **plus** the **DatabaseTables fallback**
  for *shell uniform load sets* (`Shell Uniform Load Sets` ⋈
  `Area Load Assignments - Uniform Load Sets`), emitted as `gravity` area loads.
- Export drops **analysis-only orphan joints** (e.g. diaphragm CM masters) that
  would become singular free nodes downstream.

**End-to-end gate (the real validation):** `scripts/live_export.py "<model>.EDB"`
round-trips a model and checks `e.geometry` counts against ETABS' own `Count()`.
The full apeGmsh pipeline (`StructuralModel.from_json` → `import_structural_model`
→ mesh → `build_opensees`) then meshes Casa 17B (3223 nodes) into an OpenSees
deck that **solves a static gravity step to convergence** (UmfPack, ~14 mm slab
sag, loads consistent-nodal with **0 `eleLoad`**). Counts pass on all five
reference models (up to 2059 joints).

**Open follow-ups (ADR 0009):**
- **Area (subgrade) springs — extraction DONE** (`e.geometry.area_springs()` →
  `AreaObj.GetSpringAssignment` → `cPropAreaSpring.GetAreaSpringProp`, emitted as
  the schema's `area_springs` array: `{area, property, k:[U1,U2,U3]}` per-unit-area,
  U3 = surface-normal subgrade). Best-effort like the prop reads; area-ref
  integrity validated. **Still TODO — the apeGmsh-side consumption**: a
  Winkler application (tributary-area → nodal spring) in `interop/etabs_import.py`.
  The apeGmsh reader currently ignores the new key (selective `d.get`, no strict
  schema), so foundation models export cleanly but the base is still unsupported
  downstream until the Winkler step lands. Point springs (`GetSpring`) already
  apply on both sides.
- **Solve cross-check** — validate apeGmsh reactions/displacements against
  ETABS' own analysis output within tolerance.
- `_drop_orphan_nodes` silently scrubs orphan-joint restraints/loads; add a
  `log`/warn if a genuinely loaded free joint is ever dropped.
- Loads applied via apeGmsh `g.loads` (consistent nodal), never OpenSees
  `eleLoad` — a deliberate decision (element loads are finnicky); the importer
  already honors it (`target_form="nodal"` default).

## Environment (critical)

- venv: `C:\Users\nmb\venv\opensees_env\Scripts\python.exe` (apeETABS editable;
  has numpy/pandas/baseUnits/matplotlib/rapidfuzz/comtypes/pytest/ruff).
- **Always set `LADRUNO_OPENSEES_QUIET=1`** when invoking that python — it
  otherwise prints a huge OpenSees/Ladruno banner that floods output/context.
- **No live ETABS in automated tests / CI** — COM needs the GUI + license.
  Tests use a mock SapModel (`tests/_mock_sapmodel.py`) emulating the
  `[outputs…, ret]` convention. Live checks are manual.

```bash
# from repo root, with the venv python:
LADRUNO_OPENSEES_QUIET=1 <venvpy> -m pytest -q
LADRUNO_OPENSEES_QUIET=1 <venvpy> -m ruff check src tests
LADRUNO_OPENSEES_QUIET=1 <venvpy> scripts/live_smoke.py    # results/plot — needs ETABS open
LADRUNO_OPENSEES_QUIET=1 <venvpy> scripts/live_export.py "reference models/Casa 17B RevA.EDB"
#   ^ ADR 0009 gate: launches ETABS, count-checks vs Count(), writes <model>.sm.json
```

The apeGmsh side of the round-trip lives in the **apeGmsh repo**
(`src/apeGmsh/interop/etabs_import.py`): `StructuralModel.from_json` →
`import_structural_model(g, model)` → mesh (`generate(dim=2)`) →
`build_opensees(fem, model, result)` → `ops.tcl(...)`/`ops.py(...)`. Both repos
own their own parse layer; the **schema is the contract** (`schema_version`
mismatch is loud).

## Architecture & conventions (enforce these)

Three layers, dependencies **down only**: core composites → results snapshots →
plotting. Decisions are recorded as ADRs in `architecture/decisions/` (0001–0007)
— **read them before changing the shape**, and add a new ADR for new decisions.

- Composition over mixins; composites collaborate via `self._parent.*` only
  (Parent Contract in `_session.py`: `SapModel, etabs, _verbose, is_active,
  units, tables, stories, results, plot`).
- Results are **detached typed `@dataclass` snapshots** — no live session ref,
  report units **baked at build time**.
- **Every COM return goes through `errors.ok()`** (raises on nonzero).
- Mutations are **lock-safe**: `e.unlock()` is explicit, warns it discards
  results, never implicit; `_require_unlocked()` guards every mutation.
- Plotting is pure: snapshot in → `(fig, ax)` out, no import-time side effects.
- One public class per file; layers `core/ results/ plotting/ editing/
  creation/ agentic/`.

## How the build was run (and how to continue it)

Autonomous loop driven by `architecture/BUILD_PLAN.md`: each phase = parallel
build agents → a **verify** pass → an **adversarial review** workflow (reviewers
try to *refute* correctness vs the ADR + OAPI ref; blockers gate the commit) →
fix → commit. This caught 2 real blockers (a Parent-Contract violation and a
scrambled shear staircase). To continue: pick the next item, build, **review
adversarially**, verify green, commit.

OAPI grounding for any API work: `.claude/skills/etabs-oapi/reference/`
(`interfaces.md`, `method-index.txt`, `api/<iface>.md`, `enums.md`) — plus the
`etabs` / `etabs-design` / `etabs-analysis` skills.

## Open items

Needs a human / live ETABS:
- **P5 live validation** — open a `reference models/*.EDB` in ETABS, run
  `scripts/live_smoke.py`. Confirms display-table **column maps** and the
  **TableKey vs TableName** assumption (results builders use display names as
  keys; a real model may differ).
- **`gh auth login`** — required for true PR-per-phase and to let an agent
  open/merge PRs (pushes already work via Git Credential Manager).

Deferred by design:
- `Define.material` uses the **deprecated `cPropMaterial.SetMaterial`**; migrate
  to `AddMaterial` (Region/Standard/Grade) — but validate against a live model
  first (the mock can't).
- Agentic **audit/persistence store** (ADR 0007 record stage is in-memory only);
  `ModelSpec`/`EditSpec` are stubs; declarative `ModelSpec` (ADR 0006) deferred.

Low priority:
- Numeric-OutputCase coercion edge; `Edit.delete` bulk targeting via `_Target`.

## Memory

Durable notes live in the project memory dir
(`…\.claude\projects\…apeETABS\memory\`): `project-apeetabs`, `env-build`,
`feedback-style`.
