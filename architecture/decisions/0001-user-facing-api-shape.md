# ADR 0001 — User-facing API shape: imperative-composite first, declarative as a compile-to-core layer

**Status:** Proposed

## Context

apeETABS wraps the CSI ETABS Open API (OAPI). We must choose the shape of
the *user-facing* API. The project has three phases:

1. **Parse + plot** (v1) — read tables/results from an existing model for
   reports and hand calculations, mostly interactively in notebooks.
2. **Report** — repeatable, multi-model reporting.
3. **Build/edit models** — create or modify ETABS models programmatically.

Two broad shapes are on the table:

- **(A) Imperative / fluent composite API.** A connected session exposes
  focused composites; the user calls methods with side effects, step by
  step. This is what the foundation already implements and matches the
  apeGmsh house style (composition, typed composites, `_COMPOSITES`).

  ```python
  with apeETABS(path=r"C:\models\tower.edb") as e:
      e.units.set("kN", "m")
      forces = e.tables.get("Story Forces")
  ```

- **(B) Declarative spec + executor.** The user builds a data description
  (units, source, what to extract, what to plot, or what model to build)
  and hands it to an executor that realizes it.

  ```python
  spec = Report(
      source=Model.open(path),
      units=("kN", "m"),
      extract=[StoryForces(cases=["EQx"])],
      plots=[BaseShear(cases=["EQx"])],
  )
  result = run(spec)
  ```

The owner asked directly: *do we gain by making it declarative?*

Declarative buys specific properties — **idempotency/convergence**
(realize a desired state regardless of current state), **serialization &
diffing** (save/replay/compare a description), **batch fan-out** (one
description over many models), and **up-front validation**. It costs
ceremony and a second vocabulary to learn.

Those properties are **back-loaded**: idempotency and serialization are
decisive for *building/editing models* (Phase 3) and useful for
*repeatable reports* (Phase 2). They are nearly worthless for *interactive
parsing* (Phase 1, our v1), where the user decides the next call from the
previous result, and where `e.tables.<TAB>` discoverability and low
ceremony are the human-centric priorities the owner set.

## Decision

**Imperative-composite is the primary, stable contract. Declarative is an
optional, serializable layer that *compiles down to* the imperative core,
adopted incrementally where it earns its keep — never a parallel engine.**

Concretely:

1. **v1 ships imperative only.** The composite session (`e.units`,
   `e.tables`, `e.stories`, then `e.results`, `e.plot`) is the API.
2. **Declarative arrives per phase, as sugar over the core:**
   - A `ModelSpec` for Phase 3 (building) — this is where idempotency and
     serialization pay for themselves; the executor calls the same
     imperative composites.
   - A `ReportSpec` *iff* repeatable multi-model reporting (Phase 2)
     demands it; likewise compiles to imperative calls.
3. **The one constraint adopted now to keep the door open:** the
   imperative core stays declarative-ready — no hidden global state,
   results returned as typed `@dataclass` values, and every operation
   expressible as a plain call an executor can drive. (The connection
   constructor is also kept "spec-friendly": it may later accept a frozen
   config dataclass without changing the kwargs path.)

This is layered, not competing: there is exactly one engine (the
composites). Declarative specs are a thin front door that emit calls into
it, so we avoid the "two ways to do it" divergence.

## User-facing API — worked examples (Phase 1: parse + plot)

These examples define the *intended* surface for the read side. The
`units`/`tables`/`stories` composites already exist; `results` and `plot`
are designed here and built next. They encode the conventions this ADR
commits to (see notes after each block).

### Setup — connect once, choose units + report system

```python
from apeETABS import apeETABS

# Attach to a model already open in ETABS (or path=... to launch+open).
with apeETABS(attach=True, verbose=True) as e:
    e.units.set("kN", "m").use_report_system()   # report in baseUnits base
    ...
```

### Displacements

```python
    # Joint displacements for one case (or combo=...), as a typed result.
    disp = e.results.displacements(case="EQx")

    disp.df          # tidy, numeric, elevation-mapped DataFrame:
                     #   Story, Point, Label, OutputCase, StepType,
                     #   Ux, Uy, Uz, Rx, Ry, Rz, Elevation
    disp.cases       # ('EQx',)

    # A vertical profile along a repeating point label, in REPORT units:
    ux = disp.profile(label="C12", direction="X")    # -> Profile
    ux.elevation     # np.ndarray  (report length units)
    ux.value         # np.ndarray  (report length units)
    ux.peak          # (value, story) of the maximum
```

### Story drift

```python
    # Story drifts for a combo (drift is a dimensionless ratio — no unit
    # conversion, but elevations are mapped through e.stories).
    drift = e.results.story_drifts(combo="1.0D+1.0EQx")

    drift.df                       # Story, OutputCase, Direction, Drift, Elevation
    dx = drift.profile(direction="X")     # max story drift vs elevation -> Profile
    dx.peak                               # (drift, story)
    drift.exceeds(limit=0.02)             # rows over an allowable drift
```

Selection convention: every results call takes exactly one of
`case=` / `combo=` (a human name; fuzzy-matched when `[fuzzy]` is
installed). The result is a typed dataclass carrying `.df` plus
domain helpers — never a bare DataFrame or a dict.

### Plots — a separate layer, two ways in

```python
    # (1) Ergonomic sugar on the session:
    e.plot.drift(drift, direction="X")
    e.plot.displacement(disp, label="C12", direction="X")
```

```python
    # (2) The pure plotting layer — no session, no global style side
    #     effects; takes a result object + optional Axes, returns (fig, ax):
    from apeETABS.plotting import drift_profile

    fig, ax = drift_profile(drift, direction="X", ax=None, label="EQx")
```

Both render the same thing; `e.plot.*` just forwards the result object to
the `apeETABS.plotting` functions. Plotting only ever *consumes* typed
result objects, so it never touches ETABS or units logic.

### Multi-model overlay (where the user loop lives until `ReportSpec`)

```python
    import matplotlib.pyplot as plt
    from apeETABS.plotting import drift_profile

    fig, ax = plt.subplots()
    for tag, e in models.items():                      # models: dict[str, apeETABS]
        drift_profile(e.results.story_drifts(case="EQx"), ax=ax, label=tag)
```

This hand-written loop is deliberately the v1 answer to batch reporting.
If it becomes common it is the signal to add the declarative layer below.

### The same, later, declaratively (compile-to-core)

When repeatable/multi-model reporting earns it, a `ReportSpec` describes
the *result*; its executor calls the very same `e.results.*` /
`apeETABS.plotting.*` shown above — one engine, thin front door:

```python
    from apeETABS.report import ReportSpec, Attach, DriftProfile, DisplacementProfile

    ReportSpec(
        source=Attach(),                      # or OpenFile(path)
        units=("kN", "m"),
        figures=[
            DriftProfile(case="EQx", direction="X"),
            DisplacementProfile(label="C12", case="EQx", direction="X"),
        ],
    ).run()
```

The spec is a serializable `@dataclass`; running it is equivalent to the
imperative blocks above. This is illustrative of the layering — it is
**not** part of v1.

## Alternatives considered

1. **Declarative-first for the whole API.** Rejected for v1: it taxes the
   interactive parsing workflow (notebooks, exploratory calcs) with
   ceremony and a separate DSL, hurting the discoverability and
   human-centricity that are the stated priorities. Its strengths apply to
   a phase we have not reached.
2. **Imperative-only, forever.** Rejected as a *permanent* stance: Phase 3
   (model building/editing) genuinely benefits from idempotent,
   serializable, diffable specs. Closing that door now would force a
   retrofit later. We keep the core declarative-ready instead.
3. **Hybrid where both forms are first-class from day one.** Rejected:
   maintaining two co-equal surfaces over an immature core doubles the
   work and invites divergent styles before we even know the building API.

## Consequences

**Positive:**

- v1 stays small, discoverable, and notebook-friendly — fastest path to
  the parse+plot goal.
- A single engine (the composites) means one place for correctness; specs
  can never drift from behavior because they call the same code.
- Typed-dataclass results + no global state make the later declarative
  layer cheap to add and easy to serialize/diff.

**Negative:**

- Repeatable/multi-model reporting in v1 is expressed by the user writing
  their own loops over the imperative API until `ReportSpec` lands.
  Acceptable — that is exactly the signal that tells us the declarative
  layer is worth building.
- A future `ModelSpec` will have some surface duplication with the
  imperative builders (the spec field set mirrors the builder arguments),
  mirroring the trade-off accepted in apeGmsh's OpenSees ADRs. Revisit
  with code-gen if it becomes painful.

## Reference

- apeGmsh ADR 0003 — Namespace API + static typing (house style for
  decision records and the "pick one surface" principle).
- `.claude/skills/etabs/` — the ETABS skill family describing the OAPI
  surface this API wraps.
