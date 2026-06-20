# ADR 0002 — Class architecture: layered composites, typed result snapshots, pure plotting

**Status:** Proposed

## Context

ADR 0001 fixed the *user-facing* shape (imperative composites first;
declarative as a later compile-to-core layer). This ADR fixes the
*internal* class architecture that delivers it: how classes are organized,
how they collaborate, what holds data, and how new capabilities are added.

The owner set three hard constraints up front:

- **Composition over mixins.** The old code used a `modelResults_utilities`
  mixin shared by the results classes; that is explicitly rejected here.
- **Use classes to store (mutable) data**, with real class declarations and
  type hints (stdlib `@dataclass`, not dicts-as-records).
- **Human-centric** surface: discoverable, low ceremony, notebook-friendly.

The house style to match is apeGmsh: a session facade over a `_COMPOSITES`
registry, each composite handed the parent session, lifecycle via
`begin()/end()` + context manager.

The foundation already implements the core of this: `apeETABS(_SessionBase)`
with `units` / `tables` / `stories` composites, `errors.ok()`, and IntEnum
units. This ADR generalizes those patterns and commits to how the
*results* and *plotting* layers attach.

## Decision

### 1. Three dependency layers, one direction

```
            ETABS COM (cSapModel)
                    │
   ┌────────────────┼─────────────────┐   Layer A — core composites
   │  units   tables   stories         │   (talk to SapModel; own session refs)
   └────────────────┬─────────────────┘
                    │  reads through _parent.{tables,stories,units}
   ┌────────────────┴─────────────────┐   Layer B — results
   │  Results composite  →  typed       │   (factory + self-contained snapshots:
   │  snapshots: Displacements,         │    Displacements, StoryDrifts, Profile…)
   │  StoryDrifts, StoryForces, …       │
   └────────────────┬─────────────────┘
                    │  consumes snapshots only (no session, no COM)
   ┌────────────────┴─────────────────┐   Layer C — plotting / report
   │  apeETABS.plotting.* pure fns      │
   │  e.plot.* thin sugar → calls C     │
   └───────────────────────────────────┘
```

Dependencies point **down only**: plotting never imports the session;
results never import plotting; core never imports results. This is what
keeps plotting testable without ETABS and lets a result snapshot be
pickled, diffed, or overlaid across models.

### 2. Session facade + composite registry (Layer A)

`apeETABS(_SessionBase)` owns the COM connection and a class-level
`_COMPOSITES` tuple `(attr, module, class, is_optional)`. `begin()`
connects and instantiates each composite with `cls(self)`. Composites are
**plain classes** (not dataclasses) — they are behavior over the live
session, not data.

**Composite Parent Contract** (what a composite may read on `self._parent`):
`SapModel`, `etabs`, `_verbose`, `is_active`, and the sibling composites
`units`, `tables`, `stories`. Composites collaborate **only** through this
contract — never by inheritance.

### 3. Composition replaces the mixin

The ex-`modelResults_utilities` elevation logic lives on the `stories`
composite (`Stories.map_elevation`, `map_elevation_top_bottom`,
`step_axis`). Results obtain it by collaboration — `self._parent.stories` —
not by inheriting a base. Adding shared behavior later means adding a
method to the relevant composite, never widening a mixin.

### 4. Results = a factory of typed, self-contained snapshots (Layer B)

`Results` is a composite whose methods are **builders** that return typed
`@dataclass` snapshots:

```python
e.results.displacements(case="EQx")   -> Displacements
e.results.story_drifts(combo="...")   -> StoryDrifts
e.results.story_forces(case="EQx")    -> StoryForces
```

Each snapshot is **self-contained**: at construction the builder fetches
the data, applies elevation mapping (via `stories`), and **bakes in the
report-unit conversion** (via `units`), then stores plain values. A
snapshot holds **no reference to the live session or COM** — only its
`.df` plus the metadata it needs.

- Domain helpers are **methods on the snapshot** (`.profile(...)`,
  `.peak`, `.exceeds(limit=...)`), returning further dataclasses
  (`Profile`) — OOP and discoverable, per ADR 0001's examples.
- Snapshots are **mutable** plain `@dataclass` (the owner's "classes store
  mutable data"); the user may post-process `.df`.
- Because snapshots are detached, they are the natural unit for
  multi-model overlays and the future serializable `ReportSpec`.

### 5. Plotting is pure functions; `e.plot` is sugar (Layer C)

`apeETABS.plotting` holds free functions that take a **result snapshot**
(+ optional `ax`) and return `(fig, ax)`. No global style mutation at
import; styling is applied explicitly via an opt-in `apeETABS.plotting.style`
helper the caller invokes. `e.plot` is a thin composite forwarding the
snapshot to those functions for ergonomics. Plotting depends on snapshots
only — never on the session or `SapModel`.

### 6. Data freshness: lazy fetch, explicit cache, `refresh()`

- Model-global, stable, expensive data (the stories table) is **cached on
  its composite** and invalidated by `composite.refresh()`.
- Results builders are **not implicitly cached** — each call hits ETABS and
  returns a fresh snapshot; the user caches by holding the returned object.
  This keeps freshness predictable (no stale hidden state, aligned with
  ADR 0001's "no hidden global state").

### 7. Cross-cutting placement & naming

- `errors.py` — `ETABSError`, `ConnectionError`, and `ok()` (the
  `[outputs…, ret]` convention). Every COM call routes returns through `ok`.
- `enums.py` — API enums as `IntEnum` (pass straight to COM).
- One public class per file, **filename = class name** (`Units.py`,
  `Tables.py`, `Stories.py`, `Results.py`, `Displacements.py`).
  Private infra is underscored (`_session.py`, `_core.py`).
- Subpackages by layer: `core/` (A), `results/` (B), `plotting/` and later
  `report/` (C).

### 8. How to add a capability (the recipe)

- **New table-backed result:** add a builder method to `Results` and a
  snapshot dataclass under `results/`; it pulls via `_parent.tables`,
  maps via `_parent.stories`, converts via `_parent.units`.
- **New plot:** add a pure function under `plotting/` taking that snapshot;
  optionally a one-line `e.plot.*` forwarder.
- **New core surface (model building, Phase 3):** add a composite to
  `_COMPOSITES`; it follows the Parent Contract.

## Alternatives considered

1. **Shared results base class / mixin** (the old design). Rejected by
   constraint — composition via the `stories` composite gives the same
   reuse without inheritance coupling, and keeps "what reads ETABS"
   (composites) separate from "what holds data" (snapshots).
2. **Results objects that keep a live session reference** and convert
   units lazily on access. Rejected: it couples snapshots to an open COM
   connection, breaks pickling/overlay/`ReportSpec`, and reintroduces
   hidden state. Baking conversion at build time is the price for detached,
   portable snapshots.
3. **`results` as nested sub-composites** (`e.results.drift.story(...)`).
   Rejected for v1 as over-nesting; flat builder methods
   (`e.results.story_drifts(...)`) read better and match ADR 0001's
   examples. Revisit only if the method count on `Results` grows unwieldy.
4. **Plot methods on the snapshots** (`drift.plot()`). Rejected as the
   *primary* form: it would make Layer B depend on matplotlib and blur the
   data/figure split. `e.plot.*` sugar covers the ergonomic case while the
   pure functions stay the contract.
5. **Implicitly caching results builders.** Rejected: stale-by-default
   surprises during iterative report building; explicit object-holding is
   clearer.

## Consequences

**Positive:**

- One collaboration mechanism (the Parent Contract); no inheritance webs.
- Snapshots are portable: testable without ETABS, picklable, overlay-ready,
  and the exact unit a future `ReportSpec` serializes.
- Plotting is unit-testable on synthetic snapshots; no COM, no globals.
- The "add a capability" recipe is mechanical, which keeps Phase 2/3 growth
  consistent.

**Negative:**

- Baking units at snapshot-build time means re-reporting in different units
  requires re-fetching (or a `with_units()` transform we may add later).
  Accepted: report unit choice is set once per study in practice.
- Builder methods accrete on `Results`; if that file grows large we revisit
  alternative 3 (sub-composites) behind the same surface.
- Snapshot construction does several things (fetch + map + convert); kept
  cohesive per result type rather than split, to keep call sites simple.

## Reference

- ADR 0001 — User-facing API shape (the surface this architecture serves).
- apeGmsh `_session.py` / `_core.py` — the composite-registry house style.
- `.claude/skills/etabs-oapi/` — the OAPI surface Layer A wraps.
