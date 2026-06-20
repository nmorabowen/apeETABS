# apeETABS

A human-centric Python wrapper around the **CSI ETABS Open API (OAPI)** — for
parsing results and producing report-ready figures and calculations, with
scaffolding for model editing, creation, and agent-driven workflows.

Built in the same composition style as [apeGmsh](https://github.com/nmorabowen/apeGmsh):
a connected session exposes focused composites (`e.units`, `e.tables`,
`e.results`, `e.plot`, …) instead of one monolithic class.

> **Status — v1.** The read stack (connect → units → tables → stories →
> results → plots) is complete and tested; editing, creation, and the agentic
> pipeline are scaffolded (lock-safe skeletons + the declarative-spec seam).
> Architecture is fixed by the ADRs in [`architecture/decisions/`](architecture/decisions/).

---

## Install

Requires **Python ≥ 3.10**, Windows, and an installed **ETABS** (with its API
registered) for live use. Automated tests need none of that — they run against a
mock (see [Testing](#testing)).

```bash
pip install -e .
```

Runtime deps: `comtypes`, `numpy`, `pandas`, and
[`baseUnits`](https://github.com/nmorabowen/baseUnits) (the unit-conversion
library this bridges to). Optional extras: `plot` (matplotlib), `fuzzy`
(rapidfuzz — fuzzy case/combo matching), `process` (psutil — attach by PID).

## Quickstart

```python
from apeETABS import apeETABS

# Attach to a model already open in ETABS (or path=... to launch + open):
with apeETABS(attach=True, verbose=True) as e:
    e.units.set("kN", "m")            # readable names, enums, or int codes
    e.units.use_report_system()       # report via baseUnits (default N-mm-tonne-s)

    # --- parse -------------------------------------------------------------
    drift = e.results.story_drifts(case="EQx")
    dx    = drift.profile(direction="X")          # -> Profile (elevation, value, peak)
    print(drift.peak(direction="X"))              # (max drift, story)

    disp   = e.results.displacements(case="EQx")
    forces = e.results.story_forces(case="EQx")

    # --- plot (separate, pure layer; e.plot is session sugar) --------------
    e.plot.drift(drift, direction="X")            # or e.plot.drift(case="EQx")
    e.plot.story_shear(forces, direction="X")
```

Selection is always one of `case=` / `combo=` (human names; fuzzy-matched when
`[fuzzy]` is installed). Results come back as **typed, self-contained snapshots**
(`.df` + domain helpers like `.profile()`, `.peak`, `.exceeds()`), already
converted to your chosen report units.

Without the context manager:

```python
e = apeETABS(path=r"C:\models\tower.edb").connect()
...
e.end()
```

## The session API

| Composite | What it does |
|---|---|
| `e.units` | get/set present units; bridge ETABS values into a `baseUnits` report system |
| `e.tables` | any ETABS database table → tidy `pandas.DataFrame` (`get`, `available`) |
| `e.stories` | story geometry + elevation mapping (the collaborator that replaces the old mixin) |
| `e.results` | `displacements`, `story_drifts`, `story_forces`, `wall_forces` → typed snapshots |
| `e.plot` | `drift`, `displacement`, `story_shear`, `story_forces`, `wall_forces` (sugar over the pure `apeETABS.plotting.*` fns) |
| `e.edit` / `e.assign` | *(scaffold)* model edits + assignments, behind the lock guard |
| `e.define` / `e.create` / `e.new` | *(scaffold)* materials/sections/loads, geometry, templates |

Mutating the model is **lock-safe**: after analysis ETABS locks the model, and
apeETABS never unlocks implicitly — `e.unlock()` is explicit and warns that it
discards analysis results (`ModelLockedError` guards every mutation).

Agent-driven work goes through declarative specs (`apeETABS.agentic`): a
`ReportSpec` / `ModelSpec` / `EditSpec` runs through one gated pipeline
(`propose → validate → plan → gate → run → record`) with `AgentPolicy` risk
tiers — destructive actions are never auto-approved.

## Architecture

Three layers, dependencies pointing **down only** (ADR 0002):

```
core composites (units, tables, stories)        <- talk to ETABS COM
        |
results  (typed, detached snapshots)            <- units baked, session-free
        |
plotting / report                               <- pure fns, no COM, no session
```

Principles: composition over mixins · typed `@dataclass` snapshots · every COM
return checked through `ok()` · plotting is pure (no import-time side effects).
The full reasoning lives in the ADRs:

- [0001 user-facing API shape](architecture/decisions/0001-user-facing-api-shape.md) — imperative-first; declarative compiles to the core
- [0002 class architecture](architecture/decisions/0002-class-architecture.md)
- [0003 results extraction](architecture/decisions/0003-results-extraction.md) · [0004 plotting](architecture/decisions/0004-plotting.md)
- [0005 model editing](architecture/decisions/0005-model-editing.md) · [0006 model creation](architecture/decisions/0006-model-creation.md)
- [0007 agentic workflow](architecture/decisions/0007-agentic-workflow.md)

## Testing

```bash
python -m pytest -q        # mock-backed suite, no live ETABS required
python -m ruff check src tests
```

Tests run against a **mock SapModel** (`tests/_mock_sapmodel.py`) that emulates
the OAPI `[outputs…, ret]` return convention, so the whole suite runs headless.

For **live validation** against a real model, open one of your `.EDB` files in
ETABS, then:

```bash
python scripts/live_smoke.py [--case EQx]
```

## Project layout

```
src/apeETABS/
  _session.py _core.py      # session facade + composite registry
  errors.py enums.py        # ok() checked returns; OAPI enums
  core/                     # Units, Tables, Stories
  results/                  # Displacements, StoryDrifts, StoryForces, WallForces, Profile
  plotting/                 # pure profile/force plots, style, Plot sugar
  editing/  creation/       # lock-safe edit/assign; define/create/new (scaffold)
  agentic/                  # spec pipeline, AgentPolicy, ReportSpec (scaffold)
architecture/decisions/     # ADRs 0001-0007
tests/                      # mock-backed unit + integration tests
scripts/live_smoke.py       # manual live validation
```

## License

See [LICENSE](LICENSE).
