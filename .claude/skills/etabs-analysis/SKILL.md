---
name: etabs-analysis
description: >-
  ETABS analysis and modeling behavior — element formulations (frame, shell/area,
  link, tendon), load cases (static linear/nonlinear, modal eigen/Ritz, response
  spectrum, time history direct/modal, nonlinear staged construction, hyperstatic,
  buckling), automatic lateral loads (seismic & wind per code), P-Delta, modal
  participation, diaphragms, constraints, meshing, mass source, materials &
  hinges, and soil-structure springs. Use to explain WHY ETABS produces a result
  or how a modeling feature behaves. Triggers on "load case", modal/Ritz,
  response spectrum, time history, P-Delta, staged construction, auto seismic,
  auto wind, diaphragm, hinge, nonlinear, damping, mass source, eigenvalue,
  story drift behavior, meshing, or rigid/semi-rigid. Points into the CSI
  Analysis Reference Manual, Lateral Loads Manual, and technical notes in
  reference/.
---

# ETABS Analysis & Modeling

This skill explains how ETABS models and analyzes structures — the theory and
documented behavior behind results. The authoritative sources are the vendor
manuals in [`reference/`](reference/) at the repo root. Cite the specific manual
+ section rather than answering from general FEM knowledge, since ETABS has
documented formulations and defaults.

## Primary references (paths under `reference/`)

- **`CSI Analysis Reference Manual.pdf`** — the main reference. Element
  formulations (frame, shell/area, link/support, tendon, cable), coordinate
  systems & joints, constraints (diaphragm, body, equal), materials, sections,
  load patterns vs load cases, all analysis case types (linear/nonlinear static,
  modal eigen & Ritz, response spectrum, direct & modal time history, nonlinear
  staged construction, buckling, hyperstatic, moving load), P-Delta & large
  displacement, damping, mass source, modal participation, and output
  conventions. This is the first place to look for *why ETABS does X*.
- **`Lateral Loads Manual.pdf`** — automatic lateral load generation: seismic
  (auto base shear, story forces per ASCE 7, IBC, Eurocode 8, NBCC, IS 1893,
  NTC, etc.) and wind (ASCE 7, etc.), including auto load pattern parameters.
  Pairs with the OAPI `cAutoSeismic` interface and the wind auto-load functions.
- **`Introductory Tutorial.pdf`**, **`User's Guide.pdf`**,
  **`Welcome to ETABS.pdf`** — workflow orientation and menu-level behavior.
- **`CSiXRevit Manual.pdf`** — ETABS ↔ Revit interoperability (BIM round-trip).

## Technical notes (`reference/Technical Notes/`)

Focused deep-dives — read the matching one for these topics:

| File | Topic |
|---|---|
| `S-TN-MAT-001.pdf` | Material stress-strain curves (all material types) |
| `S-TN-MAT-002.pdf` | Modified Darwin-Pecknold 2-D reinforced concrete material model |
| `S-TN-ECS-001.pdf` | Material time-dependent properties (creep/shrinkage/aging) |
| `S-TN-HNG-001.pdf` | Parametric P-M2-M3 (interacting) plastic hinge model |
| `S-TN-WHM-001.pdf` | ETABS wall hinge models (nonlinear shear wall hinges) |
| `S-TN-LNK-001.pdf` | High-damping rubber isolator link property |
| `S-TN-LNK-002.pdf` | Sumitomo viscoelastic damper link property |
| `S-TN-SSI-001.pdf` | Auto point-spring supports from soil profiles & column footprints |
| `S-TN-VIB-001.pdf` | Floor vibration analysis |
| `S-TN-IFC-001.pdf` | IFC4 import and export |

## Verification examples (`reference/Verification/Analysis/`)

`Example 01.pdf` … `Example 15.pdf` — closed-form / textbook problems solved in
ETABS with the independent solution, to validate analysis features. Use to
confirm a formulation or reproduce expected results.

## Mapping behavior to the API

Each analysis concept has an OAPI counterpart (drive it via the **etabs-oapi**
skill; method lists in `.claude/skills/etabs-oapi/reference/api/`):
- Load cases: `cCaseStaticLinear`, `cCaseStaticNonlinear`,
  `cCaseStaticNonlinearStaged`, `cCaseModalEigen`, `cCaseModalRitz`,
  `cCaseResponseSpectrum`, `cCaseDirectHistoryLinear/Nonlinear`,
  `cCaseModalHistoryLinear/Nonlinear`, `cCaseHyperStatic`.
- Loads & functions: `cLoadPatterns`, `cLoadCases`, `cCombo`, `cAutoSeismic`,
  `cFunction`, `cFunctionRS`.
- Run & read: `cAnalyze`, `cAnalysisResults`, `cAnalysisResultsSetup`.
- Modeling: `cConstraint`, `cDiaphragm`, `cGenDispl`, `cPropLink`, `cPropMaterial`.

## How to answer an analysis question

1. Pin down the feature (which load case type / element / modeling option).
2. Read the relevant **CSI Analysis Reference Manual** section (target the
   chapter — it's a large PDF; use the `pdf` skill / Read with a page range), or
   the matching technical note / Lateral Loads Manual.
3. If a number must be reproduced, use a Verification example.
4. If it must be scripted, hand the *driving* to **etabs-oapi**.

## Related skills

For FEM theory from first principles, `anthropic-skills:fem-mechanics-expert`.
For nonlinear/seismic modeling and OpenSees comparison,
`anthropic-skills:quake-research` and `anthropic-skills:opensees-expert`.
