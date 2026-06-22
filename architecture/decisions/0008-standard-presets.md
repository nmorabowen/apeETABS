# ADR 0008 — Standard presets: an opinionated imperative tier (`e.standards`)

**Status:** Proposed

## Context

ADR 0006 split model creation into two tiers: **neutral imperative builders**
(`e.define` / `e.create` / `e.assign` — one thing, explicit, no opinion) and a
**declarative `ModelSpec`** (a serializable whole-model description, currently
deferred).

Real model setup needs a *third* thing those two tiers don't cover well:
**opinionated "standard" bundles** that encode code/practice conventions —

- standard **materials** (e.g. the NEC/ACI concrete + steel set),
- standard **seismic load patterns** (Sx/Sy/Ex/Ey),
- **response spectra** (a code formula, or values from a library we own),
- standard **load combinations**,
- a standard **mass source** (e.g. Dead + a fraction of Live).

These are imperative ("do this now to my model"), not a declarative end-state,
so `ModelSpec` is the wrong altitude. And they carry **opinion** (a code, a
convention), so they must NOT be baked into the neutral `define`/`assign`
primitives — doing so would make those primitives non-neutral and code-coupled.

## Decision

### 1. A new composite `e.standards` for opinionated presets

Add a `Standards` composite (`e.standards`), a peer of the builders, that holds
**conventions only** and **composes the neutral primitives** through the
ADR 0002 Parent Contract (`self._parent.define.*`, `self._parent.assign.*`).
It issues **no COM calls of its own** — every write still goes through a
`define`/`assign` primitive, so the lock guard (ADR 0005) and unit contract
(ADR 0006 §3) are inherited unchanged.

```python
e.standards.materials(code="NEC")          # -> e.define.material(...) ×N
e.standards.seismic_patterns(...)          # -> e.define.load_pattern(...) ×N
e.standards.spectrum(code="NEC-SE-DS", ...)# -> e.define.response_spectrum_function(...)
e.standards.combos(code="NEC")             # -> e.define.combo(...) ×N
e.standards.mass_source(...)               # -> e.define.mass_source(...)
```

### 2. The primitives stay neutral (and gain the missing ones)

`e.standards` is sugar; the engine is still `define`/`assign`. The following
neutral primitives are the compile targets and must exist:

- `e.define.response_spectrum_function()` — `cFunctionRS` (NEW)
- `e.define.load_case()` incl. response-spectrum cases — `cLoadCases` /
  `cCaseResponseSpectrum` (NEW)
- `e.define.mass_source()` — mass-source API (NEW)
- `e.define.combo()` — `cCombo` (finish the existing stub)
- `e.assign.loads()` — `c*Obj.SetLoad*` (finish the existing stub)
- `e.define.material*()`, `e.define.load_pattern()` — already shipped.

### 3. Presets are code-keyed

Every `e.standards.*` method is parameterized by a design code (NEC, ASCE/ACI,
…), mirroring `IrregularityCriteria`/`ASCE7` (ADR 0004 follow-on). Code-specific
constants live with the preset, not the primitive. NEC-15 is the first target.

### 4. Spectra: a producer/consumer boundary

A response spectrum has two sides: **producing** ordinates `(periods, accels)`
— from a code formula or from an external library we own — and **defining** the
function in ETABS. The consumer is the neutral primitive
`e.define.response_spectrum_function(name, periods, accels)`. The producer
(code formula / external-library adapter) lives **in `e.standards`**, and any
external dependency is imported **lazily/optionally** (as matplotlib is in the
plotting layer). Native and external spectra share the one Define sink.

### 5. Relationship to `ModelSpec`

`e.standards` does not replace or pre-empt the deferred declarative tier.
Standards presets are imperative building blocks; when `ModelSpec` is realized
it may *reference* them (a spec node "use the NEC standard materials"), but it
compiles to the same `define`/`assign` primitives. `e.standards` is the
opinionated-imperative middle, between the neutral builders and the declarative
front door.

## Consequences

- One small new composite; the builder tier stays neutral and code-agnostic.
- A single discoverable home (`e.standards`) for conventions, easy to extend
  per code/region.
- Optional external dependencies (spectrum libraries) are isolated to the
  standards layer and lazily imported — they never enter the core import path.
- Net new public surface is additive; nothing in ADR 0006 changes (this ADR
  extends it).
