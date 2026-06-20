# ADR 0007 — Agentic workflow: specs as the agent interface, one gated pipeline

**Status:** Proposed (scaffolding — fine details deferred)

## Context

apeETABS will be driven by LLM agents for three jobs:

1. **Report creation** — attach to a model, extract results, assemble figures
   and tables into a report (read-only).
2. **Model creation** — build a model from a high-level intent (greenfield).
3. **Model editing** — modify an existing model (mutating, potentially
   destructive).

An agent driving raw composites/COM is unsafe and unreviewable: it can trip
the lock/results interaction (ADR 0005), make destructive edits with no
preview, and leave no record. This ADR sets the **architecture and skeleton**
for agentic use now; the field-level details (exact spec schemas, the gating
UX, any MCP/tool server) are deferred to later ADRs. We only commit the
shape so the rest of the build doesn't foreclose it.

This rests on prior decisions: declarative specs compile to the imperative
core (ADR 0001); `ReportSpec` (ADR 0003) and `ModelSpec` with
`validate()/plan()/run()` (ADR 0006); explicit, consent-based unlock
(ADR 0005); the ETABS skill family as the agent's knowledge layer.

## Decision

### 1. The declarative spec layer IS the agent interface

Agents author and edit **serializable specs** — `ReportSpec`, `ModelSpec`,
`EditSpec` — never raw composites or COM. The spec is simultaneously the
agent's output, the human review surface, and the safety boundary. Anything
an agent can do, it does by producing a spec that the engine executes.

### 2. One gated execution pipeline

Every agentic action flows through the same pipeline:

```
propose(spec) → validate() → plan() → [approval gate] → run() → record
```

- **validate** — references, units, and invariants checked *before any ETABS
  call* (generalizes ADR 0006 §5).
- **plan** — a dry-run: the ordered list of operations / a diff, as data, with
  nothing applied.
- **approval gate** — policy-controlled (below).
- **run** — execute via the imperative builders/editors/results.
- **record** — persist `{spec, plan, outcome}` for reproducibility/audit.

The same four verbs exist for all three spec types; only `run` dispatches to
results / creation / editing.

### 3. Risk tiers and gating policy (scaffold)

A single `AgentPolicy` object governs the gate by risk tier:

| Tier | Workflow | Default gate |
|---|---|---|
| **read** | report creation (read-only) | auto-run |
| **create** | greenfield model | validate + plan; run allowed, approval optional |
| **edit** | mutate existing model | **require explicit approval + plan preview** |
| **destructive** | delete / unlock-with-results-loss | **never auto; always confirmed** |

`AgentPolicy(allow_edit=..., require_approval=..., dry_run_default=True)`.
Destructive operations (delete, the ADR 0005 unlock that discards results)
are never auto-approved regardless of policy.

### 4. Structured I/O for self-correction

`validate/plan/run` return **typed, JSON-serializable result objects**, not
bare exceptions: success flag, the operation/diff list, and **structured
errors carrying a machine code + remediation hint** (e.g.
`UNKNOWN_SECTION`, "define section 'R1' before member 'C1'"). This lets an
agent read the outcome and self-correct instead of parsing prose.

### 5. Capability manifest + schemas (reserved seam)

Specs expose **JSON schemas** and a small **capability registry** enumerating
the available spec types and fields. This is the grounding surface for a
future function-calling / MCP tool server — reserved now (so specs are built
schema-first), implemented later.

### 6. Knowledge layer = the ETABS skill family

Agents ground on `.claude/skills/etabs*` (OAPI surface, design, analysis).
The library's specs and the skills are kept consistent so an agent reasons
about the same surface it can drive. No separate agent doc set.

### 7. Workflow scaffolds (named now, detailed later)

- **`ReportWorkflow`** — attach → `ReportSpec` → extract (ADR 0003) + plot
  (ADR 0004) → assemble (docx/pdf/markdown via the document skills). Read
  tier; the natural first agentic target.
- **`CreateWorkflow`** — `ModelSpec` → validate → plan → run → save. Create
  tier.
- **`EditWorkflow`** — target + `EditSpec` → diff/preview → approval →
  consented unlock if needed → apply → refresh. Edit/destructive tier.

All three are thin orchestrations over the pipeline in §2; they share
validate/plan/record and differ only in `run`.

## Alternatives considered

1. **Agents call composites/COM directly.** Rejected: no review surface, no
   dry-run, exposed to the lock/results footgun, unreproducible. The spec
   boundary exists precisely to prevent this.
2. **Bespoke agent code per task.** Rejected: not auditable or reproducible;
   the uniform `propose→validate→plan→gate→run→record` pipeline is the value.
3. **Full edit autonomy (no gates).** Rejected: editing is destructive in
   ETABS; the tiered policy with mandatory confirmation on destructive ops is
   non-negotiable.
4. **Prose-only errors.** Rejected: agents self-correct far better on coded,
   structured errors; prose is for humans and kept as a `message` field
   alongside the code.
5. **Build the MCP/tool server now.** Deferred, not rejected: we reserve the
   schema/manifest seam but don't implement a server until the specs settle.

## Consequences

**Positive:**

- One safe, uniform, reviewable interface for all agentic work; the spec is
  both human- and agent-facing.
- Dry-run + tiered approval contain the destructive cases by construction.
- Structured outcomes enable agent self-correction; run records give audit
  and reproducibility.
- Report creation (read tier) can ship as the first agentic capability with
  minimal risk.

**Negative:**

- Agent reach is bounded by spec coverage — anything not expressible as a
  spec is not agent-drivable. Deliberate (it is the safety boundary), but it
  means specs must keep pace with the composites.
- The gating policy and structured-error plumbing add surface and ceremony
  beyond a bare imperative call.
- Schema/manifest work is real; deferred here, but the seam must be honored
  as specs are written.

## Reference

- ADR 0001 — declarative compiles to core (the spec boundary's basis).
- ADR 0003 — `ReportSpec`/extraction; ADR 0004 — plotting; ADR 0005 —
  editing + consent-based unlock; ADR 0006 — `ModelSpec` validate/plan/run.
- ETABS skill family (`.claude/skills/etabs*`) — the agent knowledge layer.
- Document skills (`docx`, `pdf`, `pptx`) — report assembly targets for
  `ReportWorkflow`.
