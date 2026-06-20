# ADR 0004 — Plotting: pure functions over snapshots, opt-in theming, session sugar

**Status:** Proposed

## Context

ADR 0002 placed plotting in Layer C: pure functions that consume result
snapshots and return `(fig, ax)`, with `e.plot.*` as thin session sugar and
no import-time side effects. This ADR fixes the details: the function
contract, theming, composition/overlay, axis conventions, and what
`e.plot.*` is allowed to do.

The old code is the cautionary tale to fix:

- `set_default_plot_params()` ran **at import** in every results module — a
  global side effect on the user's matplotlib.
- Plot methods lived **on the data classes**, fusing data and figures.
- It depended on an external `plotApeConfig` (`blueAPE`, `grayConcrete`,
  `color_palette`) not shipped with the package.
- Multi-model plotting was a pair of free functions taking a dict of models.

The good ideas to keep: an APE house theme + color palette, `ax`-injection
for composition, mirrored ± profiles for symmetric quantities, stepped
story-shear / `barh` story-force styles.

## Decision

### 1. Function contract

Every plot is a free function in `apeETABS.plotting`:

```python
def drift_profile(
    snapshot,                 # a results snapshot (Layer B), already in report units
    *,
    direction: str = "X",
    ax: "matplotlib.axes.Axes | None" = None,
    label: str | None = None,
    step: str = "Max",
    **line_kwargs,            # color, linewidth, linestyle, marker, ...
) -> tuple["Figure", "Axes"]:
    ...
```

Rules:

- **Input is a snapshot, never the session or `SapModel`.** Plotting cannot
  reach ETABS — it is unit-testable on synthetic snapshots.
- **`ax=None` creates a new `(fig, ax)`; a given `ax` is drawn on** and its
  parent figure is returned. This is the single mechanism for subplots,
  composition, and overlays.
- **Returns `(fig, ax)`; never calls `plt.show()` or closes the figure.**
  The caller owns display and layout (notebooks show the returned figure).
- **Axis labels/units come from the snapshot** (`snapshot.units` /
  `Profile.unit`), so axes are annotated correctly without the plotter
  knowing unit logic.

### 2. No import-time side effects; theming is opt-in

Importing `apeETABS.plotting` mutates nothing. The house style lives in
`apeETABS.plotting.style`:

```python
from apeETABS.plotting import style

style.apply()                      # explicitly set APE rcParams (global, caller's choice)
with style.theme():                # or scoped, restored on exit
    drift_profile(drift, ax=ax)
style.PALETTE                      # ordered colors for multi-series
style.BLUE, style.GRAY            # named brand colors (the ex-plotApeConfig set)
```

Default behavior with no `style` call respects the user's current
`rcParams`. The palette/colors ship **inside** the package (no external
`plotApeConfig` dependency).

### 3. Color cycling is explicit

For multi-series/multi-model overlays, color is chosen by the caller (pass
`color=`), or pulled from `style.PALETTE[i]` in their loop. Functions do not
maintain hidden cross-call color state.

### 4. `e.plot.*` sugar — may fetch, then delegates

`e.plot` is a session-bound composite, so for one-liners it may accept
**either** a snapshot **or** selection kwargs; in the latter case it fetches
via `_parent.results` and forwards to the pure function:

```python
e.plot.drift(drift, direction="X")          # snapshot in hand
e.plot.drift(case="EQx", direction="X")     # sugar: fetch via results, then plot
```

The **pure functions remain snapshot-only** (Layer C stays clean); only the
session-bound `e.plot` is allowed to fetch (it already holds `_parent`).
This keeps the ergonomic one-liner without leaking session access into the
plotting layer.

### 5. Axis & rendering conventions

- **Profiles** (drift, displacement) plot value on x, `Elevation` on y, with
  story y-ticks; report-unit labels on both axes.
- **Symmetric quantities** (story shear, base shear) draw mirrored ±curves,
  as in the old code.
- **Story forces** use `barh` + line overlay; **story shear** uses the
  stepped elevation axis from `e.stories.step_axis()`.
- **Wall forces** use a 3-panel P/M/V layout with optional min/max envelopes
  and an amplified-shear overlay.
- `tight_layout` / titles are opt-in via kwargs; the function sets sensible
  defaults but never forces global layout.

### 6. Overlay helper (thin)

A small `apeETABS.plotting.overlay(snapshots, plot_fn, *, labels=None, ax=None, **kw)`
applies a plot function across snapshots on one `ax`, cycling
`style.PALETTE` and labelling each — the packaged form of ADR 0001's
multi-model loop. It is sugar over the contract in §1, not a new mechanism.

### 7. v1 scope

1. `drift_profile`, `displacement_profile` (the ADR 0001 examples).
2. Then `story_shear`, `story_forces`, `wall_forces` / `wall_force_envelopes`
   (ports of the proven old plots), once those snapshots exist (ADR 0003 §7).

## Alternatives considered

1. **Plot methods on snapshots (`drift.plot()`) as primary.** Rejected:
   makes Layer B depend on matplotlib and re-fuses data with figures. The
   `e.plot.*` sugar covers the ergonomic case while pure functions stay the
   contract (also rejected in ADR 0002 alt 4).
2. **Auto-applying the APE theme on import** (old behavior). Rejected: a
   library must not mutate a user's matplotlib globally without being asked.
   Opt-in `style.apply()` / `style.theme()` preserves control.
3. **`e.plot.*` taking snapshots only (no fetch).** Considered; allowing the
   fetch form is a deliberate, contained ergonomic exception justified by
   `e.plot` already being session-bound. The purity rule is preserved where
   it matters — the free functions.
4. **Returning only `ax`** (matplotlib-conventional). Rejected: returning
   `(fig, ax)` is friendlier for the report use case (saving the figure)
   and still composes via `ax=`.
5. **A plotting backend abstraction (plotly/bokeh).** Rejected for v1:
   matplotlib only, for static report figures. The snapshot→figure split
   means another backend could be added later without touching Layer B.

## Consequences

**Positive:**

- Plotting is testable without ETABS and without a display; pure functions
  over dataclasses.
- No surprise global rcParams changes; theming is explicit and scoped.
- The package is self-contained (palette/colors inside), fixing the missing
  `plotApeConfig` dependency.
- One composition mechanism (`ax=`) serves subplots, overlays, and reports.

**Negative:**

- `e.plot.*` has two input forms (snapshot or selection kwargs); a small,
  documented ergonomic concession, justified above.
- Report-unit axis labels depend on snapshots carrying unit metadata (ADR
  0003 §5); if that metadata is wrong, axes mislabel — handled by sourcing
  labels from the same place conversion happens.

## Reference

- ADR 0001 — plotting surface examples; ADR 0002 — Layer C placement;
  ADR 0003 — snapshots and their unit metadata.
- Old `modelResults_storyForces` / `modelResults_wallForces` — the stepped
  shear / `barh` / mirrored ± / envelope patterns being carried forward
  (minus the import-time `set_default_plot_params()` and the data/plot
  fusion).
