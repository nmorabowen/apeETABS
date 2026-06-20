# apeETABS — Handoff

Snapshot for whoever (human or agent) picks this up next. Pairs with
[`README.md`](README.md) (user-facing) and
[`architecture/BUILD_PLAN.md`](architecture/BUILD_PLAN.md) (build state).

## What this is

A human-centric Python wrapper over the **CSI ETABS Open API (OAPI)**, in the
apeGmsh house style (session facade + composites). **v1 = parse + plot**
(complete, tested); editing / creation / agentic are **scaffolded**.

- Repo: https://github.com/nmorabowen/apeETABS (public, `main`)
- Replaces an old class (reference only): `C:\Users\nmb\Documents\Github\APE_Public\ETABS_to_python`

## Status at handoff

- All planned phases **P0–P8 complete**, each adversarially reviewed before commit.
- **164 tests pass, ruff clean.** No live ETABS needed (mock-backed).
- Pushed to GitHub `main`; full reviewed commit history preserved.

| Area | State |
|---|---|
| Connection, units (+baseUnits bridge), tables, stories | complete |
| Results: Displacements, StoryDrifts, StoryForces, WallForces, Profile | complete |
| Plotting: drift/displacement/story_shear/story_forces/wall_forces + style | complete |
| Editing: lock guard + `e.edit`/`e.assign` | **scaffold** (rename/delete/restraint impl; rest stubs) |
| Creation: `e.define`/`e.create`/`e.new` | **scaffold** (material/frame_rect/load_pattern/point/frame impl; rest stubs) |
| Agentic: spec pipeline, AgentPolicy, ReportSpec | **scaffold** (read tier real; Model/EditSpec stubs) |

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
LADRUNO_OPENSEES_QUIET=1 <venvpy> scripts/live_smoke.py   # needs ETABS + a model open
```

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
