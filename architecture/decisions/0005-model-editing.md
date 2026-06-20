# ADR 0005 — Model editing: imperative mutations, lock guard, name identity

**Status:** Proposed

## Context

Phase 3 adds write access. This ADR covers **editing an existing model**
(including models apeETABS did not create); ADR 0006 covers **creating** one
from scratch. They share machinery (the `assign` surface, object identity,
inbound units) defined where first needed and cross-referenced.

ETABS imposes hard realities on any editor:

- **Post-analysis lock.** After `RunAnalysis`, the model is locked. Editing
  requires `SapModel.SetModelIsLocked(False)`, **which deletes all analysis
  results**. Silent unlock would silently destroy a user's results.
- **Immediate, non-transactional COM mutations.** Each call applies at once;
  there is no rollback. A partial failure leaves partial state.
- **Name-based identity.** Objects are keyed by a unique program-assigned
  name; users may set their own names/labels; renames change the key.
- **Bulk via item type.** Many assign/edit calls take `eItemType`
  (Objects / Group / SelectedObjects).

The owner's constraints from ADR 0002 carry over: composition (no mixins),
typed data, human-centric, no hidden global state.

## Decision

### 1. Editing is imperative (no auto-reconcile in v1)

Editing is a set of explicit mutating operations on the live model.
Declarative "reconcile the model to this desired state" (diff + converge) is
**out of scope for v1** — it is the most complex form and belongs, if ever,
on top of the imperative editors via a future `ModelSpec.reconcile()`
(ADR 0006). Greenfield desired-state authoring is served by ADR 0006's
`ModelSpec`; editing stays direct.

### 2. The lock cycle is explicit, never silent

Mutating operations check `GetModelIsLocked` and, if locked, raise
`ModelLockedError` telling the user to call `e.unlock()`.

```python
e.unlock()         # SetModelIsLocked(False); WARNS that results are deleted
e.lock()           # SetModelIsLocked(True)
e.is_locked        # property
```

`e.unlock()` emits a warning (and, when `verbose`, prints) that analysis
results are being discarded. We never unlock implicitly inside an edit — the
destruction of results must be a decision the user makes.

### 3. Objects are referenced by name; labels resolve to names

Edit/assign operations take the ETABS **unique name** (a `str`). Helpers
resolve user labels / groups / selections to names. Operations that change
identity return the new state:

- `e.edit.rename(old, new) -> new_name`
- `e.edit.delete(target)` invalidates that name.
- Operations that split/replicate (`divide`, `replicate`) return the names
  they produced.

A thin handle object may be introduced later; v1 uses names to stay close to
the API and avoid a stale-handle abstraction.

### 4. Targeting: name, group, or selection (eItemType)

Bulk operations accept a **target** that maps to `eItemType`:

```python
e.assign.frame_modifiers("B12", ...)               # a single object (Objects)
e.assign.frame_modifiers(group="Beams", ...)       # eItemType=Group
e.assign.frame_modifiers(selected=True, ...)       # eItemType=SelectedObjects
```

Exactly one targeting form per call; ambiguous combinations raise.

### 5. Composite map for editing

Two composites, following ADR 0002's Parent Contract:

- **`e.edit`** — geometry/topology edits: `rename`, `delete`, `move`,
  `divide`, `join`/`merge`, `replicate`, `mirror` (wrapping `cEditFrame`,
  `cEditGeneral`, and `c*Obj.ChangeName`/`Delete`).
- **`e.assign`** — property/load assignments on existing objects:
  restraints, releases, end offsets, section/property changes, modifiers,
  point/frame/area loads, masses, pier/spandrel labels, group membership
  (wrapping `cPointObj`/`cFrameObj`/`cAreaObj` setters, `cGroup`).

`e.assign` is **shared with creation** (ADR 0006) — same surface whether the
object was just created or already existed.

### 6. Mutation safety: fail-loud, no auto-rollback

Every call routes its return through `ok()` (ADR 0002) and raises on
failure. There is no automatic rollback (COM has none). For multi-step
greenfield work, the declarative `ModelSpec` (ADR 0006) is recommended
because it validates up front and reduces partial-failure surface;
ad-hoc editing is the user's responsibility, made safe by loud failures.

### 7. View refresh is explicit

Edits do not auto-refresh the ETABS view. `e.refresh()` wraps
`View.RefreshView`; bulk edits run silently and the user refreshes once.

## Alternatives considered

1. **Silent unlock on first edit.** Rejected outright — it would delete
   results without consent. The explicit `e.unlock()` with a warning is the
   safe contract.
2. **Declarative reconcile/diff editing in v1.** Rejected as premature: it
   is the hardest write mode (state diffing across an object graph we don't
   fully own) and unjustified before the imperative editors and `ModelSpec`
   exist. Left as a possible `ModelSpec.reconcile()` later.
3. **Handle objects instead of names.** Rejected for v1: handles add a
   stale-on-rename/delete problem; names match the API and are simple.
   Revisit if name-tracking proves error-prone.
4. **Auto-refresh after every edit.** Rejected: slow for bulk edits; one
   explicit `e.refresh()` is cheaper and predictable.

## Consequences

**Positive:**

- The dangerous lock/results interaction is explicit and consent-based.
- One `assign` surface serves both new and existing objects.
- Loud failures + `ok()` keep partial edits diagnosable.

**Negative:**

- No rollback means a failed multi-step edit can leave partial state; the
  mitigation (use `ModelSpec` for greenfield, fail loud for ad-hoc) is a
  process answer, not a technical guarantee.
- Name-based identity puts the burden of tracking renames on the caller.

## Reference

- ADR 0001 — declarative is the Phase-3 win (informs the `ModelSpec` split).
- ADR 0002 — composites/Parent Contract; ADR 0006 — model creation (shares
  `e.assign`, identity, inbound units).
- `.claude/skills/etabs-oapi/reference/api/` — `cEditFrame`, `cEditGeneral`,
  `cFrameObj`, `cAreaObj`, `cPointObj`, `cGroup`, `cSapModel`
  (`SetModelIsLocked`).
