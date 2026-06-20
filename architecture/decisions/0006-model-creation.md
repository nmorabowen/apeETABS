# ADR 0006 — Model creation: imperative builders + a declarative ModelSpec

**Status:** Proposed

## Context

This ADR covers building an ETABS model **from scratch**; ADR 0005 covers
editing an existing one. Creation is the phase where, per ADR 0001,
**declarative pays off**: a model is a desired end-state with a natural
dependency order, and a serializable description of it buys reproducibility,
validation, dry-run, and diffing.

Creation in ETABS has a fixed shape: *define* the dictionary (materials,
sections, load patterns/cases/combos, grids/stories), *draw* geometry
(points, frames, areas, links, tendons), then *assign* (restraints, loads,
modifiers, …). Coordinates and section dimensions are expressed in the
model's present units. Names are program-assigned unless the user supplies
one (`ref string Name`).

## Decision

### 1. Two tiers: imperative builders (engine) + declarative ModelSpec (sugar)

Per ADR 0001's layering:

- **Builder composites are the engine** — imperative, discoverable, the
  thing everything else compiles to.
- **`ModelSpec` is a declarative `@dataclass` tree** describing the model;
  `ModelSpec.run(e)` *executes the builders*. It is the front door, not a
  second engine.

```python
# Imperative:
e.define.material("C30", type="Concrete", fc=30*u.MPa)
e.define.frame_rect("R1", material="C30", depth=0.6, width=0.3)
col = e.create.frame_by_coord((0,0,0), (0,0,3), section="R1", name="C1")
e.assign.restraint(col.i, dofs=(1,1,1,1,1,1))

# Declarative (compiles to the same calls):
spec = ModelSpec(
    template=Blank(units=("kN","m")),
    materials=[Concrete("C30", fc=30*u.MPa)],
    sections=[FrameRect("R1", material="C30", depth=0.6, width=0.3)],
    members=[Frame("C1", i=(0,0,0), j=(0,0,3), section="R1")],
    assigns=[Restraint(at=(0,0,0), dofs=(1,1,1,1,1,1))],
)
spec.run(e)              # or spec.plan(e) / spec.validate()
```

### 2. Builder composite map (define → create → assign)

Following ADR 0002's Parent Contract:

- **`e.define`** — model dictionary: materials, frame/area/link/rebar/tendon
  properties, load patterns/cases/combos, functions, diaphragms,
  grids/stories (`cPropMaterial`, `cPropFrame`, `cPropArea`, `cPropLink`,
  `cLoadPatterns`, `cLoadCases`, `cCombo`, `cStory`, `cGridSys`).
- **`e.create`** — geometry: `point`, `frame_by_coord`/`frame_by_point`,
  `area`, `link`, `tendon` (`c*Obj.Add*`).
- **`e.assign`** — restraints/loads/modifiers/labels/groups. **Same
  composite as ADR 0005** — there is no separate "assign on create".

### 3. Inbound units — symmetric to the reporting bridge

Creation values are in the model's **present units**, and the **baseUnits
library is the recommended way to author them** so intent is explicit:

```python
e.units.set("kN", "m")
e.define.frame_rect("R1", material="C30", depth=0.6, width=0.3)   # metres
e.define.material("C30", type="Concrete", fc=30*u.MPa)            # 30*u.MPa
```

This is the inbound twin of ADR 0003's outbound report bridge: outbound
divides by a baseUnits unit, inbound multiplies (`30*u.MPa` evaluates to the
number in the active baseUnits system, which the user keeps aligned with
present units). A future `ModelSpec` may carry an explicit input system and
convert per field; v1 keeps present-units-as-contract for simplicity.

### 4. Identity: builders return the assigned name (and a small handle)

`create.*` returns the **program-assigned name**; `name=`/`label=` request a
specific one. Frame creation returns a tiny handle exposing the object name
and its end-point names (since ETABS reorders I/J on creation — see
`AddByCoord` remarks):

```python
col = e.create.frame_by_coord((0,0,0),(0,0,3), section="R1")
col.name, col.i, col.j      # resolved via GetPoints
```

Handles are thin value objects, not live proxies; renames/deletes (ADR 0005)
invalidate them.

### 5. ModelSpec earns the declarative benefits

`ModelSpec` provides what only a declarative description can:

- `validate()` — check references (a member's `section` exists, etc.) and
  units **before touching ETABS**.
- `plan(e)` — return the ordered list of builder calls (dry-run) without
  executing.
- `run(e)` — execute in dependency order (materials → sections → grids →
  geometry → assigns → loads), so the user need not order things by hand.
- Serialization (`to_dict`/`from_dict`) for reproducible, version-controlled
  models and diffing two revisions.

Imperative users own ordering themselves; `ModelSpec` solves it.

### 6. Templates as starting points

Creation starts from a template wrapping `cFile`: `Blank`, `GridOnly`,
`SteelDeck`. `ModelSpec.template` selects one; imperative users call
`e.new.blank()` / `e.new.grid_only(...)` etc. A new model is unlocked, so
the ADR 0005 lock guard is satisfied; `e.create`/`e.define` still assert
unlocked to stay safe on reused sessions.

### 7. Failure handling

Builders fail loud via `ok()` (no COM rollback). `ModelSpec.validate()` is
the primary defense against partial builds — catch reference/unit errors
before any ETABS call. `run()` may optionally stop-on-first-error (default)
or collect-and-report.

## Alternatives considered

1. **Declarative-only creation (no imperative builders).** Rejected: it
   would violate ADR 0001's one-engine rule and remove the interactive,
   discoverable path; `ModelSpec` must compile to *something*.
2. **Imperative-only creation (no `ModelSpec`).** Rejected: creation is the
   exact case where idempotency/serialization/validation pay off; omitting
   the spec forgoes the main Phase-3 benefit. Builders ship first, spec
   follows, but the architecture reserves the seam now.
3. **Auto-managing present units per field (set/restore around each call).**
   Rejected for v1: churns ETABS state and surprises; present-units-as-
   contract + baseUnits authoring is simpler and symmetric with reporting.
   Revisit as a `ModelSpec` input-system feature.
4. **Rich live object proxies instead of name+handle.** Rejected (as in ADR
   0005): proxies invite stale-state bugs; thin value handles match the API.

## Consequences

**Positive:**

- Interactive build path *and* a reproducible, validatable, diffable spec —
  both over one engine.
- Inbound units mirror outbound reporting: one mental model for units.
- `validate()/plan()` move most failures to before any ETABS mutation.

**Negative:**

- `ModelSpec` field sets duplicate builder signatures (the apeGmsh/OpenSees
  trade-off again); accept hand-written for v1, consider code-gen later.
- Present-units-as-contract means the user must keep baseUnits authoring and
  present units aligned; the spec's future input-system removes this.
- Frame I/J reordering forces the handle to re-query `GetPoints`; minor cost
  for correctness.

## Reference

- ADR 0001 — declarative as compile-to-core (the basis for the two tiers).
- ADR 0002 — composites/layers; ADR 0003 — outbound unit bridge (this ADR is
  its inbound twin); ADR 0005 — editing (shares `e.assign`, identity, lock).
- `.claude/skills/etabs-oapi/reference/api/` — `cPropMaterial`, `cPropFrame`,
  `cPropArea`, `cFrameObj` (`AddByCoord` I/J remarks), `cLoadPatterns`,
  `cStory`, `cGridSys`, `cFile`.
