---
name: etabs
description: >-
  Router/orchestrator for working with CSI ETABS. Use whenever the user works
  with ETABS — building or scripting models through the OAPI (Python comtypes/
  pythonnet, .NET, VBA), interpreting how ETABS applies a design code (AISC,
  ACI, Eurocode, CSA, AS, NZS, IS, NTC, BS, TS, KBC, SP), or understanding
  ETABS analysis/modeling behavior (element formulations, load cases, modal,
  auto seismic/wind, P-Delta). Also triggers on apeETABS (the Python wrapper
  being built in this repo), .edb files, SapModel, cOAPI/cSapModel, ETABSv1,
  "ETABS API". This skill points to the right specialized sub-skill.
---

# ETABS

ETABS (CSI, Computers and Structures Inc.) is a structural analysis and design
program for buildings. This repository (`apeETABS`) is building a **Python
wrapper around the ETABS Open API (OAPI)**, in the same spirit as `apeGmsh`.

The full vendor documentation set lives in [`reference/`](reference/) at the repo
root: the OAPI help (decompiled into the sub-skills), design-code manuals, the
CSI Analysis Reference Manual, the Lateral Loads Manual, technical notes, and
verification examples.

## Pick the sub-skill

This is a hub. Route to the specialized skill that matches the task, read its
`SKILL.md`, then act:

| If the task is about… | Use skill | Lives at |
|---|---|---|
| Scripting/automating ETABS — connect, build a model, run analysis, pull results; writing or extending `apeETABS`; any `SapModel.*` / `cOAPI` / comtypes / pythonnet question | **etabs-oapi** | `.claude/skills/etabs-oapi/` |
| How ETABS performs **design** to a code (AISC 360, ACI 318, Eurocode, CSA, AS, NZS, IS, NTC, BS, TS, KBC, SP) — steel/concrete frame, composite beam/column, shear wall, slab, steel connection/joist | **etabs-design** | `.claude/skills/etabs-design/` |
| ETABS **analysis & modeling** theory — element formulations, load cases (modal, response spectrum, time history, nonlinear staged), auto lateral loads, P-Delta, diaphragms, meshing behavior | **etabs-analysis** | `.claude/skills/etabs-analysis/` |

Many real tasks span two of these. Example: "script a code check of a steel
frame" = **etabs-oapi** (how to drive `SapModel.DesignSteel` and read results)
+ **etabs-design** (what the code clauses mean). Read both; lead with whichever
the user is actually blocked on.

## Fast routing heuristics

- Mentions code/symbols (`SapModel`, `cFrameObj`, `AddByCoord`, `comtypes`,
  `pythonnet`, `.edb`, `RunAnalysis`, `Results.JointDispl`) → **etabs-oapi**.
- Mentions a design code or design check / utilization / D-C ratio /
  overstrength → **etabs-design** (and **etabs-oapi** if it must be scripted).
- Asks *why ETABS does X* / formulation / convergence / load generation →
  **etabs-analysis**.

## Related skills already on this system

Use these alongside the ETABS sub-skills when the work crosses tools:
- `anthropic-skills:aisc-steel-design` — AISC 360/341/358 first-principles steel
  design (pairs with **etabs-design** for steel).
- `anthropic-skills:apegmsh-helper`, `anthropic-skills:opensees-expert`,
  `anthropic-skills:fem-mechanics-expert`, `anthropic-skills:quake-research` —
  for FEM/OpenSees work this ETABS model may feed into or be compared against.
