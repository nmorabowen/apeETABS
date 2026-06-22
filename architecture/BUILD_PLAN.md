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

- ☑ P9  Seismic irregularities (ADRs 0003+0004): `criteria.py`
        (`IrregularityCriteria`/`ASCE7`, configurable thresholds) + result
        domains `CentersMassRigidity` (CM/CR eccentricity + mass Type 2),
        `StoryStiffness` (soft story Type 1a/1b), `TorsionIrregularity`
        (TIR Type 1a/1b); pure plotters `center_mass_rigidity`/
        `torsional_irregularity`/`soft_story`/`mass_irregularity` + `e.plot`
        sugar. Ratios + ASCE 7 threshold lines + pass/fail flags. **Weak
        story DEFERRED** (no analysis table for story strength — needs a
        capacity source). DONE (reviewed; 2 independent adversarial reviewers,
        no BLOCKER/MAJOR; 192 tests).

- ◑ P11 Standard presets (ADR 0008 — NEW): `e.standards` composite
        (`Standards`), an opinionated, code-keyed preset tier that composes the
        neutral `e.define`/`e.assign` builders (no COM of its own). SCAFFOLD
        SHIPPED: ADR 0008 written, composite wired into `_COMPOSITES`, all
        methods stubbed (`materials`/`seismic_patterns`/`gravity_loads`/
        `spectrum`/`combos`/`mass_source`), wiring + stub contract tested
        (199 tests). Logic per design code (NEC first) still to build. Needs
        the missing `e.define` compile targets first (see follow-ups).

ALL PLANNED PHASES P0–P9 COMPLETE. P11 (standards) scaffolded; logic pending.

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
- [P9/LIVE-CONFIRM] RESOLVED (live, Casa 17B RevA, ETABS v22, 2026-06-21 via
  `scripts/live_validate.py`). Findings + fixes applied:
  * P5/med ALSO resolved: every `TableKey` == `TableName`; ETABS keys are
    Title-Case.
  * FIX: CM/CR real key is `"Centers Of Mass And Rigidity"` (was lowercase →
    ret=-96). Corrected.
  * FIX: torsion columns are `"Max Drift"`/`"Avg Drift"` (+ ready `"Ratio"`),
    not `Maximum`/`Average`. Column map now maps both (alias kept for version
    drift).
  * Story Stiffness map (`StiffX`/`StiffY`) confirmed correct as-is.
  * All 4 checks produced sane live results: mass found a real Type-2 flag
    (Story1 ratio 1.52); soft story + torsion no flags (ratios ~1.0–2.9);
    eccentricity NaN (see CR-None note). Figures in `scripts/out/p9_*.png`.
- [P9/known] This model reports `XCR/YCR = None` (no rigid-diaphragm center of
  rigidity) → eccentricity is NaN. Handled gracefully (no crash). Validate
  eccentricity numerically on a model that DOES report CR.
- [P9/med] Soft story / torsion are per-direction-PER-CASE (`StiffY≈0` under an
  X case): assess X with the X seismic case (`Sx`), Y with `Sy`. Live-confirmed.
  `live_validate.py` auto-picks the seismic case per axis.
- [P9/low] `soft_story` assumes ONE stiffness row per story (true for static
  lateral cases like `Sx`). A case with multiple step rows per story (some
  RS/nonlinear) would break the adjacency arrays — add a per-story envelope/
  dedupe if such cases are ever fed in.
- [P9/med] CM/CR table may be per-DIAPHRAGM (>1 row/story). Casa 17B (2 rows)
  AND Vive Republica (24 rows, 24 stories) both had 1 diaphragm/story, so the
  plain roof→base shift held. `mass_check` still does NOT groupby diaphragm —
  needs a per-diaphragm aggregate for a genuinely multi-diaphragm model (still
  unexercised; neither reference model triggers it).
- [P9/decided] Mass Type 2 stays the SYMMETRIC test (decided 2026-06-21). Live
  on Vive Republica it flagged a floor below a light roof (481 vs 278, ratio
  1.73), which ASCE 7's roof exemption arguably skips. Kept as intentional
  conservatism (never misses; may over-report) — documented in `mass_check`.
- [P10/PARKED 2026-06-21] Center-of-rigidity recovery (eccentricity is NaN
  because ETABS reports `XCR/YCR = None`). PARKED after live investigation;
  the validated TIR check already covers the ASCE 7 torsion assessment, so CR
  eccentricity is a supplementary diagnostic. Findings (Vive Republica, ETABS
  v22):
  * Root cause is NOT semi-rigid diaphragms — `Diaphragm Definitions` shows D1
    = **Rigid**, assigned to 757 areas, master joints exist (e.g. Point 2036),
    and `Diaphragm Center Of Mass Displacements` is fully populated (UX/UY/RZ).
    ETABS simply does NOT export XCR/YCR via the DatabaseTables API (a table/
    version quirk) even though it models the rigid diaphragm.
  * Dead-end #1 (rigid flip): diaphragm already rigid → nothing to flip;
    `SetDiaphragm(D1, False)` returns ret=1.
  * Dead-end #2 (rotation method): the diaphragm master joint is
    analysis-generated, not a persistent loadable point — `SetLoadForce` on it
    returns ret=0 but produces ZERO response (orphaned on re-analysis).
  * Viable-but-unbuilt paths if revisited: (a) load REAL persistent joints and
    solve each diaphragm's 3×3 flexibility with offset correction (rigorous,
    big); (b) read-only shear-centroid approximation under Sx/Sy (approximate,
    no mutation). The temp-copy safety harness (Save→work→reopen original,
    cleanup all `.$et`/`.ico` artifacts by stem) was built + adversarially
    reviewed and works live — reuse it if (a) is pursued.
- [P9] Weak story (strength irregularity, ASCE 7 Vert Type 5a/5b) DEFERRED:
  story strength = Σ seismic-element shear capacities, not in any analysis
  table. Decide a capacity source (design output vs user-supplied array)
  before building.
- [P11] Build the missing neutral `e.define` compile targets that
  `e.standards` needs (ADR 0008 §2): `response_spectrum_function` (`cFunctionRS`),
  `load_case` incl. response-spectrum (`cLoadCases`/`cCaseResponseSpectrum`),
  `mass_source`; finish the `combo` (`cCombo`) and `assign.loads` stubs. THEN
  build the per-code `e.standards.*` logic (NEC-15 first), with the external
  spectrum-library adapter lazily imported.
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
- P9 (seismic irregularities) done; 2 adversarial reviewers, no BLOCKER/MAJOR
  (engineering review could not refute any of the 4 checks; arch review
  confirmed ADR 0002/0003/0004 conformance); 192 tests, ruff clean. Weak
  story deferred. Not yet committed.
- P5/P9 LIVE VALIDATION done (2026-06-21, Casa 17B RevA, ETABS v22 via
  `scripts/live_validate.py`, attach + auto-analyze). 2 real column-map bugs
  found+fixed (CM/CR Title-Case key; torsion `Max Drift`/`Avg Drift`); P5/med
  key-vs-name question resolved (key==name). All 4 checks render sane figures
  on real data. New instrument: `scripts/live_validate.py` (schema dump + P9
  exercise, forgiving). 192 tests still pass. Not yet committed.
- Post-build: README + follow-up batch (builder↔plotter integration test,
  empty-table coverage, creation-stub coverage, e.plot-required cleanup); 164
  tests pass. Remaining follow-ups: deprecated SetMaterial, P8 audit store,
  numeric-OutputCase edge, Edit.delete bulk targeting, + the P5 live run.
