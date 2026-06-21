# apeETABS — Autonomous Build Plan (loop north star)

This file is the durable state for the self-paced build loop. Each iteration:
read this, pick the next `pending` phase, build it (delegating to agents /
workflows), run checks, adversarially review at the marked junctures, update
status here + commit, then schedule the next iteration. **Keep context lean:
delegate heavy work; read conclusions, not file dumps.**

## Goal
A human-centric Python wrapper over the CSI ETABS OAPI, per ADRs 0001–0007
(`architecture/decisions/`). v1 = parse + plot; then editing, creation,
agentic scaffolding.

## Hard environment facts
- Python (venv): `C:\Users\nmb\venv\opensees_env\Scripts\python.exe`
  (apeETABS installed editable; has numpy/pandas/baseUnits/matplotlib/
  rapidfuzz/comtypes/pytest/ruff).
- **Always prefix venv python invocations with `LADRUNO_OPENSEES_QUIET=1`**
  (bash) / `$env:LADRUNO_OPENSEES_QUIET=1` (pwsh) — the venv prints a huge
  banner otherwise and bloats context.
- **No live ETABS in agents/CI.** COM needs the GUI + license. All automated
  tests run against a **mock SapModel** (`tests/_mock_sapmodel.py`) that
  emulates the `[outputs…, ret]` convention. Live validation against the
  reference models is a MANUAL gated juncture (see below).
- Reference models (gitignored): `reference models/*.EDB` (6 real models) —
  for manual live smoke tests only.
- OAPI reference for grounding: `.claude/skills/etabs-oapi/reference/`
  (`interfaces.md`, `method-index.txt`, `api/<iface>.md`, `enums.md`).

## Commands
- Tests: `LADRUNO_OPENSEES_QUIET=1 <venvpy> -m pytest -q`
- Lint: `LADRUNO_OPENSEES_QUIET=1 <venvpy> -m ruff check src tests`
- Import smoke: `<venvpy> -c "import apeETABS"`

## Review protocol (adversarial, at critical junctures)
At each ⚑ juncture, run an adversarial review **workflow**: independent
reviewers each try to REFUTE that the slice is correct vs its ADR + the OAPI
reference + the mock contract; majority-refuted findings block the commit.
Fix, re-run tests, then commit + update status here.

## Phases
Status: ☐ pending · ◑ in progress · ☑ done · ⚑ review juncture

- ☑ P0  Foundation: connection (`_session`/`_core`), `errors.ok`, `enums`,
        `core/Units|Tables|Stories`. (committed baseline)
- ☑ P1  Test harness: `tests/_mock_sapmodel.py` + conftest + P0 tests. DONE.
- ☑ P2  Results layer (ADR 0003): `results/` Results/Displacements/StoryDrifts/
        Profile, column maps, case/combo (+fuzzy), StepType envelope, units
        baking. Wired into `_COMPOSITES`. DONE (reviewed).
- ☑ P3  Plotting layer (ADR 0004): `plotting/` drift/displacement profiles,
        style (opt-in), `e.plot` sugar. Wired. DONE (reviewed).
- ☑ P4  Force domains (ADR 0003 §7): `StoryForces`, `WallForces` + plots
        (stepped shear, barh, P/M/V triptych, envelopes). DONE (reviewed; 1
        HIGH blocker — scrambled shear staircase — found + fixed).
- ☑ P5  Live validation pack: `scripts/live_smoke.py` (attach + exercise
        units/tables/stories/results/plot, save figures). DONE — awaiting the
        MANUAL run against a reference model (needs user + open ETABS).
- ☑ P6  Editing scaffolding (ADR 0005): lock guard (`e.is_locked/lock/unlock`,
        `ModelLockedError`, never-implicit + always-warns), `e.edit`/`e.assign`
        + `eItemType` targeting. DONE (reviewed; lock-safety clean, no blockers).
- ☑ P7  Creation scaffolding (ADR 0006): `e.define`/`e.create`/`e.new`,
        `FrameHandle` (i/j via GetPoints), inbound units, lock-guarded. DONE
        (reviewed; ModelSpec declarative tier deferred by design).
- ☑ P8  Agentic scaffolding (ADR 0007): `Spec` base + `run_spec` pipeline
        (`propose→validate→plan→gate→run→record`), `AgentPolicy` tier gating,
        structured `Outcome`/`Finding`, `ReportSpec` (read tier, real). DONE
        (reviewed; all claims held, no blockers).

ALL PLANNED PHASES P0–P8 COMPLETE.

## Conventions (from ADRs — enforce in review)
- Composition only; no mixins. Composites talk via `self._parent.*`.
- Typed `@dataclass` snapshots; results detached from session, units baked.
- `ok()` wraps every COM return; raise on nonzero.
- One public class per file, filename = class name; layers `core/`,
  `results/`, `plotting/`.
- Plotting: pure fns return `(fig, ax)`, no import-time side effects.

## Follow-ups (non-blocking, from P1–P3 adversarial review)
- [P4] RESOLVED (in P4): `bake_units` now emits real unit labels for non-length dims.
- [med] RESOLVED: `e.plot` made genuinely required (matplotlib lazy); dropped
  the dead "degrade to None" claim.
- [med] RESOLVED: empty-table `Tables.get` "no headers" branch now covered
  (mock `empty_tables` fixture + test).
- [low] numeric OutputCase coercion edge (float/mixed numeric case names).
- [low] `StoryTable` is a 2nd public class in `Stories.py` (accepted snapshot
  pairing; revisit only if it bites).
- [P5] Confirm display-table column maps against a real table dump (live).
- [P5/med] TableKey vs TableName: results builders + live_smoke use display
  names ("Story Drifts", "Joint Displacements", "Design Forces - Piers") as
  the GetTableForDisplayArray key; on a real model the key may differ from the
  human name. Confirm/normalize against a live `e.tables.available()` dump.
- [low] `Edit.delete` hardcodes eItemType.Objects (single-name only); adopt
  `_Target` if/when bulk delete is added.
- [P7/low] RESOLVED (decision): `material()` stays on `SetMaterial` — the
  correct primitive for CUSTOM-property materials (AddMaterial is catalog-only
  and can't express arbitrary E/nu). Added `material_from_catalog()` using
  `AddMaterial` for the catalog path (Region/Standard/Grade strings need live
  validation). See PR #2.
- [P8] `record` stage is in-memory only; add a persistence/audit store when
  realizing ADR 0007 beyond scaffolding. `ModelSpec`/`EditSpec` are stubs.
- [low] RESOLVED: creation stub `NotImplementedError`s now tested.
- [med] RESOLVED: builder↔plotter drift — added an integration test
  (`e.plot.story_shear` over the real `StoryForces` via the mock; asserts the
  plotted line matches `shear().value/.elevation`).

## GitHub
- Repo: PUBLIC https://github.com/nmorabowen/apeETABS — PUBLISHED (`main`).
- Pushed via Git Credential Manager (no `gh` auth). Future PR-per-phase needs
  `gh auth login` or the web UI; current history is linear on `main`.

## Progress log (append one line per iteration)
- P0 done (baseline commit 006710a).
- P1+P2+P3 done via workflow ws18kft3o (8 agents); 1 arch blocker found +
  fixed (Parent Contract widened, COM calls routed through ok(), loud
  unmapped-story failure); ruff clean, 67 tests pass.
- P4 done via wn5ewzvlx; HIGH blocker (scrambled shear staircase) found+fixed; 92 tests.
- P5+P6 done via wwtu4qsed; lock-safety review clean, no blockers; 121 tests.
- P7+P8 done via whghnszy7; no blockers (1 low: deprecated SetMaterial); 158 tests.
- ALL P0-P8 COMPLETE. Pushed to GitHub (public main).
- Post-build: README + follow-up batch (builder↔plotter integration test,
  empty-table coverage, creation-stub coverage, e.plot-required cleanup); 164
  tests pass. Remaining follow-ups: deprecated SetMaterial, P8 audit store,
  numeric-OutputCase edge, Edit.delete bulk targeting, + the P5 live run.
