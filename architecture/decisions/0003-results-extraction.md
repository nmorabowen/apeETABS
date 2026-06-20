# ADR 0003 — Results extraction: backend, selection, normalization, units

**Status:** Proposed

## Context

ADR 0001 defined the results *surface* (`e.results.story_drifts(...)` →
typed snapshot) and ADR 0002 defined *where* it sits (Layer B, a factory of
self-contained snapshots). This ADR decides *how* a snapshot is actually
built from ETABS:

1. **Where the numbers come from** — display tables vs the Analysis Results
   API (the open question left by ADR 0001).
2. **How a human case/combo name selects rows.**
3. **How raw ETABS output becomes a tidy, version-tolerant DataFrame.**
4. **How `StepType` (Max/Min/Step) envelopes are handled.**
5. **How report-unit conversion is applied.**
6. **What ships in v1.**

ETABS exposes two read paths:

- **Display tables** (`cDatabaseTables.GetTableForDisplayArray`): pre-laid-out,
  per-story rows (e.g. `"Story Drifts"`, `"Joint Displacements"`,
  `"Design Forces - Piers"`). Minimal assembly to a report-ready frame, but
  column names/contents vary with ETABS version and present units, and the
  table reflects the model's *display* selection state.
- **Analysis Results API** (`cAnalysisResults`: `JointDispl`, `StoryDrifts`,
  `JointDrifts`, `BaseReact`, …): strongly-typed arrays, explicit case
  selection via `Results.Setup`, version-stable. But results come per object
  and some report views require aggregation/joins we'd do ourselves.

The old code used display tables + pandas filtering + `rapidfuzz` fuzzy
matching of `OutputCase` + a `StepType == "Max"` filter. Those patterns
worked and are worth keeping.

## Decision

### 1. Backend: display tables for v1, behind a pluggable source

The v1 extraction backend is **display tables**. It is the fastest path to
the tidy, per-story, report-ready frames Phase 1 needs, and matches the
proven old workflow.

To honor ADR 0002's "no hidden state": builders **do not mutate ETABS
display selection**. They read the whole relevant table once and filter in
pandas. (If a table requires a display selection to be populated at all,
that is set transiently and restored — documented per table, avoided where
possible.)

The backend is isolated behind an internal `_source` seam on the `Results`
composite so the **Analysis Results API can be added later** as an
alternate source *behind the same snapshot surface* — never a second public
API (consistent with ADR 0001's one-engine rule).

### 2. Selection: exactly one human `case=`/`combo=`, filtered in pandas

Each builder takes exactly one of `case=` / `combo=` (a human name). The
builder reads the table, then filters the `OutputCase` column to the
requested name:

- With the optional `[fuzzy]` extra (`rapidfuzz`), the name is resolved to
  the nearest actual `OutputCase` above a threshold; the resolved name is
  recorded on the snapshot (`.case`) so the user sees what matched.
- Without `[fuzzy]`, matching is exact; a miss raises `ETABSError` listing
  the available cases.

A plural `cases=[...]` may be added later; v1 is single-selection to keep
the surface small.

### 3. Normalization: canonical schema per result type

Each result type owns a **column map** from ETABS column names to a canonical
schema, applied after fetch. Example (displacements):

```
canonical: Story, Point, Label, OutputCase, StepType, StepNumber,
           Ux, Uy, Uz, Rx, Ry, Rz, Elevation
```

- Numeric coercion is already done by the `tables` composite.
- `Elevation` is added via `_parent.stories.map_elevation(...)`
  (or `map_elevation_top_bottom` for Top/Bottom-keyed tables like forces).
- The column map is tolerant: unknown extra columns are kept; a missing
  *required* column raises a clear `ETABSError` naming the table and column,
  so version drift fails loudly rather than silently.

### 4. StepType: keep all rows; helpers envelope by default

Response-spectrum / time-history cases produce `StepType` ∈ {Max, Min,
Step}. The snapshot's `.df` keeps **all** rows. Domain helpers
(`.profile()`, `.peak`) default to an **envelope**:

- default `step="Max"` (matches the old behavior);
- `step="abs"` takes the larger magnitude of Max/Min per story;
- `step="Min"` / a specific `StepNumber` are also selectable.

Static cases (single `StepType`/`None`) pass through unchanged.

### 5. Units: bake report units at build time

Per ADR 0002, conversion happens once at construction. Each result type
declares a **dimension per value column** (e.g. `Ux→length`,
`Drift→dimensionless`, `P→force`, `M3→moment`, `V2→force`). The builder
multiplies each column by `_parent.units.factor(dim)` (dimensionless columns
untouched) and records the report-unit labels on the snapshot for plot
annotation. Re-reporting in other units re-fetches (a `with_units()`
transform may be added later).

### 6. Snapshot shape (per ADR 0002)

```python
@dataclass
class StoryDrifts:
    df: pd.DataFrame            # canonical + Elevation, in report units
    case: str                  # resolved OutputCase
    units: dict[str, str]      # column -> report unit label (for axes)
    # methods: .profile(direction="X", step="Max") -> Profile
    #          .peak(direction=...) ; .exceeds(limit=...)
```

`Profile` is the shared small dataclass: `elevation`, `value`, `label`,
`unit`, `.peak`.

### 7. v1 scope

Ship in order, all table-backed:

1. **Displacements** — `"Joint Displacements"` (or diaphragm CM table for
   per-story profiles).
2. **StoryDrifts** — `"Story Drifts"` (and `"Joint Drifts"` for label-keyed
   profiles, mirroring the old `drift` class).

Then port the proven force domains:

3. **StoryForces** — `"Story Forces"` (story shear + per-story force).
4. **WallForces** — `"Design Forces - Piers"` (P/M/V + envelopes, shear
   amplification carried as analysis metadata, not baked into the snapshot).

## Alternatives considered

1. **Analysis Results API as the v1 backend.** Rejected for v1: more
   assembly for per-story report frames and no payoff yet for the
   interactive parse goal. Kept as a future source behind the seam, where
   its version-stability and typing will matter for automated pipelines.
2. **Mutating ETABS display selection per call** to read one case at a time.
   Rejected: side-effects on the user's open model and slower than one read
   + pandas filter; also fights ADR 0001's no-hidden-state rule.
3. **Returning the raw table and letting the user normalize.** Rejected as
   the primary surface — that is the old dict-of-DataFrame ergonomics this
   project is replacing. `e.tables.get()` still exists for power users.
4. **Defaulting `.profile()` to raw rows (no envelope).** Rejected: RS/TH
   cases would silently double rows per story; an explicit `step="Max"`
   default is the least-surprise behavior for reports.

## Consequences

**Positive:**

- Fast, report-ready frames with the old workflow's ergonomics, minus the
  dicts and the mixin.
- Version drift surfaces as a clear error at the column map, not as silent
  wrong numbers.
- The source seam means the Results API can be adopted later with zero
  surface change.

**Negative:**

- Column maps are maintenance surface as ETABS versions shift; mitigated by
  failing loudly and centralizing the maps per result type.
- Tables depend on the model's display state for some views; handled per
  table and documented, but it is a real ETABS quirk we inherit.
- Baked units mean multi-unit reporting re-fetches until `with_units()`.

## Reference

- ADR 0001 — surface; ADR 0002 — layering/snapshots.
- `.claude/skills/etabs-oapi/reference/api/cDatabaseTables.md`,
  `cAnalysisResults.md` — the two read paths.
- Old `modelResults_storyForces` / `modelResults_wallForces` — the proven
  filtering / StepType / fuzzy patterns being carried forward.
