---
name: etabs-design
description: >-
  How ETABS performs code-based design and what the results mean — steel frame,
  concrete frame, composite beam, composite column, shear wall, concrete slab,
  steel connection, and steel joist design. Covers the supported design codes
  (AISC 360-05/10/16/22, ACI 318-08/11/14/19, Eurocode 2/3/4, CSA S16 & A23.3,
  AS 3600 & 4100, NZS 3101/3404, IS 456/800/11384, NTC, BS, HK CP, TS 500, KBC,
  SP 16, Chinese) — design preferences/overwrites, D-C (demand-capacity) ratios,
  capacity/seismic provisions, and how to read or script design through the OAPI.
  Triggers on design code names, "design check", "utilization", "D/C ratio",
  "overwrites", "auto-select section", cDesignSteel/cDesignConcrete/
  cDesignShearWall/cDesignCompositeBeam, or any cDSt*/cDCo*/cDComp*/cDConc* code
  interface. Points into the vendor design manuals in reference/.
---

# ETABS Design (code procedures)

ETABS implements each design code as a documented procedure. The authoritative
description of *what ETABS actually computes* for a given code is the vendor
design manual PDF in [`reference/`](reference/) at the repo root. Always cite the
specific manual + code edition rather than answering from general code knowledge,
because ETABS makes documented interpretations and defaults.

## Two layers, keep them distinct

1. **The procedure** — the manual PDFs below describe assumptions, applied
   clauses, classification, capacity/seismic provisions, and the D-C ratio
   formulation ETABS uses per code.
2. **Driving/reading it via the API** — the OAPI design interfaces start/stop
   design, set preferences & overwrites, pick the code, and return results. See
   the **etabs-oapi** skill and these interfaces (full method lists in
   `.claude/skills/etabs-oapi/reference/api/`):
   - `cDesignSteel`, `cDesignConcrete`, `cDesignShearWall`,
     `cDesignCompositeBeam`, `cDesignCompositeColumn`, `cDesignConcreteSlab`,
     `cDesignStrip`, `cDesignForces`, `cDesignResults`, `cDetailing`.
   - Per-code preference/overwrite interfaces: steel `cDStAISC360_22` etc.
     (prefix `cDSt*`), concrete `cDCoACI318_19` etc. (`cDCo*`), composite column
     `cDCompCol*`, concrete shell/slab `cDConc*`.

Typical OAPI design flow: select code via the design driver → set prefs/overwrites
→ `StartDesign()` → query results (`cDesignResults`, summary tables) → read D-C
ratios / chosen sections. Look up exact method names in the etabs-oapi reference.

## Design manuals by type and code (paths under `reference/`)

**Steel Frame Design** — `reference/Steel Frame Design/`
AISC 360-22/16/10/05 (`SFD-AISC-360-*.pdf`), AISC ASD-89 & LRFD-93 & BS 5950-2000
(`SFD-OlderCodes.pdf`), AS 4100-2020/1998, CSA S16-24/19/14, Eurocode EN 1993-1-1:2005
(`SFD-EN 1993-1-1 2005.pdf`), IS 800-2007, KBC 2016/2009, NTC 2018/2008,
NZS 3404-1997, SP 16.13330.2017 (`SFD SP-16-13330-2017.pdf`).

**Concrete Frame Design** — `reference/Concrete Frame Design/`
ACI 318-19/14/11/08 (`CFD-ACI-318-*.pdf`), AS 3600-2018/09, BS 8110-97, CP 65-99,
CSA A23.3-24/19/14, Eurocode 2 2004 (`CFD-EC-2-2004.pdf`), HK CP-2013, IS 456-2000,
KBC 2016/2009, NTC 2008, NZS 3101-2006, RCDF 2017/2004, TS 500-2000 (& R2018).

**Composite Beam Design** — `reference/Composite Beam Design/`
AISC 360-22/16/10/05, BS 5950-90, CSA S16-24/19/14, EC-4-2004, IS 11384-2022.

**Composite Column Design** — `reference/Composite Column Design/`
AISC 360-22/16/10, CSA S16-24/19, EC-4-2004, IS 11384-2022.

**Shear Wall Design** — `reference/Shear Wall Design/`
ACI 318-19/14/11/08 (`SWD-ACI-318-*.pdf`), ACI 530-11 (masonry), AISC 360-22
composite (`CSWD-AISC-360-22.pdf`), AS 3600-2018/09, BS 8110-97, CP 65-99,
CSA A23.3-14, EC-2-2004, HK CP-2013, IS 456-2000, KBC 2016/2009, NZS 3101-2006,
RCDF 2017/2004, TS 500-2000 (& R2018).

**Concrete Slab Design** — `reference/Concrete Slab Design/`
`ETABS RC Slab Design.pdf`, `ETABS PT Slab Design.pdf` (post-tensioned).

**Steel Connection Design** — `reference/Steel Connection Design/`
AISC 360-22/16/10 (`SCD-AISC-360-*.pdf`).

**Steel Joist Design** — `reference/Steel Joist Design/SJD-SJI-2020.pdf`.

## Verification examples (hand-calc vs ETABS)

Worked examples that validate each procedure are under
`reference/Verification/Design/<Type>/` — e.g.
`reference/Verification/Design/Concrete Frame/ACI 318-19 Example 001.pdf`,
`.../Composite Column/AISC-360-22 Example 003.pdf`. Use these to confirm an
interpretation or to reproduce a check by hand.

## How to answer a design question

1. Identify the **design type** and **code edition** (ask if ambiguous — ETABS
   behavior differs across editions).
2. Read the matching manual PDF section in `reference/` (use the `pdf` skill /
   Read tool with a page range; these manuals are long — target the relevant
   chapter: classification, flexure, shear, combined, seismic, D-C).
3. If a hand-check is needed, cross-reference the Verification example.
4. If it must be scripted, hand off the *driving* part to **etabs-oapi** and the
   *interpretation* stays here.

## Related skills

For first-principles code design beyond ETABS's interpretation, use
`anthropic-skills:aisc-steel-design` (AISC 360/341/358 + Design Guides). For
concrete/seismic theory feeding the model, `anthropic-skills:quake-research`.
