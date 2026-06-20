---
name: etabs-oapi
description: >-
  Drive the CSI ETABS Open API (OAPI) from code — primarily Python via comtypes
  (COM) or pythonnet (.NET), also VBA/C#. Use to connect to or launch ETABS,
  build models (points, frames, areas, links, tendons), define materials and
  sections, set loads/patterns/cases/combos, run analysis, and extract results,
  and to write or extend the apeETABS Python wrapper in this repo. Triggers on
  SapModel, cOAPI, cSapModel, cHelper, ETABSv1, comtypes.client, pythonnet,
  CreateObjectProgID, ApplicationStart, InitializeNewModel, RunAnalysis,
  Results.JointDispl, .edb, "ETABS API", or any cFrameObj/cAreaObj/cPropMaterial/
  cLoadPatterns/cAnalyze/cDesign* method. Bundles the full decompiled API
  reference (120 interfaces, ~1280 methods) and all enums.
---

# ETABS OAPI Automation

The ETABS Open API exposes the program through COM/.NET interfaces. From Python
you reach it two ways: **comtypes** (COM, late-bound) or **pythonnet** (.NET,
early-bound via `ETABSv1.dll`). COM is the most common for scripting; .NET gives
real type info and enum objects. This skill assumes ETABS v1 API (`ETABSv1`
namespace), the surface shipped with current ETABS (22/2x).

## The object model

```
comtypes.client.CreateObject('ETABSv1.Helper')   →  cHelper
  helper.CreateObjectProgID('CSI.ETABS.API.ETABSObject')  →  cOAPI   (myETABSObject)
    myETABSObject.SapModel                          →  cSapModel  (THE model)
      SapModel.File / FrameObj / AreaObj / PointObj / PropMaterial /
      PropFrame / LoadPatterns / LoadCases / RespCombo / Analyze /
      Results / Results.Setup / DesignSteel / DesignConcrete / Story / ...
```

Everything is done through `SapModel` and its child interfaces. The full map of
which interface does what, and the accessor on `SapModel`, is in
[`reference/interfaces.md`](reference/interfaces.md).

## Connecting — canonical Python (COM) pattern

```python
import os, sys, comtypes.client

AttachToInstance = False     # True = attach to an already-open ETABS
SpecifyPath      = False     # True = launch a specific ETABS.exe (not the latest)
ProgramPath = r'C:\Program Files\Computers and Structures\ETABS 22\ETABS.exe'

helper = comtypes.client.CreateObject('ETABSv1.Helper')
helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)

if AttachToInstance:
    myETABSObject = helper.GetObject("CSI.ETABS.API.ETABSObject")
elif SpecifyPath:
    myETABSObject = helper.CreateObject(ProgramPath)
else:
    myETABSObject = helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")

myETABSObject.ApplicationStart()          # REQUIRED before using SapModel
SapModel = myETABSObject.SapModel
SapModel.InitializeNewModel()             # or InitializeNewModel(eUnits value)
ret = SapModel.File.NewBlank()            # or NewBlank / NewSteelDeck / NewGridOnly / OpenFile
# ... build / analyze / read ...
myETABSObject.ApplicationExit(False)      # False = don't save
SapModel = None; myETABSObject = None
```

### Connecting — Python (.NET / pythonnet)

```python
import clr
clr.AddReference(r'C:\Program Files\Computers and Structures\ETABS 22\ETABSv1.dll')
from ETABSv1 import cHelper, Helper, cOAPI, cSapModel, eUnits
helper = cHelper(Helper())
myETABSObject = helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")
myETABSObject.ApplicationStart()
SapModel = myETABSObject.SapModel
SapModel.InitializeNewModel(eUnits.kip_in_F)   # enums are real objects in .NET
```

## Conventions that bite — read before writing API calls

These come from the API's VB/COM heritage (`reference/` → "Programming Concepts"):

1. **Option Base 0.** All ETABS arrays are 0-based. Use 0-based indexing.

2. **Return value is the LAST element.** Every API function returns an `int`
   status: `0` = success, nonzero = failure. In Python COM, functions with
   `ByRef`/output params return a **list** with the outputs first and the status
   last. Bind accordingly:
   ```python
   # C# sig: int AddByCoord(double XI,...,ref string Name, string PropName="Default", ...)
   name = ' '
   [name, ret] = SapModel.FrameObj.AddByCoord(0,0,0, 0,0,10, name, 'R1')
   if ret != 0: raise RuntimeError("AddByCoord failed")
   ```
   Always check `ret`. The number and order of returned items = the `ref`/`out`
   params in declaration order, then `ret`.

3. **Arrays are passed ByRef and resized by ETABS.** For "get" functions that
   fill arrays (results, lists), pass placeholders; ETABS returns the filled
   lists. The first output is usually `NumberResults`/`NumberItems`:
   ```python
   NumberResults=0; Obj=[]; Elm=[]; ACase=[]; StepType=[]; StepNum=[]
   U1=[];U2=[];U3=[];R1=[];R2=[];R3=[]
   [NumberResults,Obj,Elm,ACase,StepType,StepNum,
    U1,U2,U3,R1,R2,R3,ret] = SapModel.Results.JointDispl(
        pt, 0, NumberResults,Obj,Elm,ACase,StepType,StepNum,
        U1,U2,U3,R1,R2,R3)
   ```
   (The `0` is the `eItemTypeElm` selector: 0=ObjectElm, 1=Element, 2=GroupElm,
   3=SelectionElm.)

4. **Optional arguments** have defaults shown in the C# signature
   (`PropName = "Default"`, `CSys = "Global"`, etc.). In Python you may omit
   trailing optionals.

5. **Units.** Pass the integer `eUnits` value (Python COM) or `eUnits.<member>`
   (.NET). Set with `SapModel.SetPresentUnits(value)`. Parameter units in the
   docs use `[L]` length, `[F]` force, `[M]` mass, `[s]` time, `[T]` temp,
   `[deg]`/`[rad]` angle — combined as `[FL]` moment, `[F/L2]` stress.

   | Value | Units | | Value | Units |
   |---|---|---|---|---|
   | 1 | lb, in, °F | | 9 | N, mm, °C |
   | 2 | lb, ft, °F | | 10 | N, m, °C |
   | 3 | kip, in, °F | | 11 | Ton, mm, °C |
   | 4 | kip, ft, °F | | 12 | Ton, m, °C |
   | 5 | kN, mm, °C | | 13 | kN, cm, °C |
   | 6 | kN, m, °C | | 14 | kgf, cm, °C |
   | 7 | kgf, mm, °C | | 15 | N, cm, °C |
   | 8 | kgf, m, °C | | 16 | Ton, cm, °C |

6. **`eItemType`** (used by many assign functions): 0=Objects, 1=Group,
   2=SelectedObjects. **`eMatType`**: 1=Steel, 2=Concrete, 3=NoDesign,
   4=Aluminum, 5=ColdFormed, 6=Rebar, 7=Tendon, 8=Masonry. **`eLoadPatternType`**:
   1=Dead, 2=SuperDead, 3=Live, 4=ReduceLive, 5=Quake, 6=Wind, 7=Snow, 8=Other,
   11=RoofLive, 12=Notional. Full enum tables: [`reference/enums.md`](reference/enums.md).

## Typical build → analyze → results workflow

```python
SapModel.SetPresentUnits(4)                                   # kip, ft, F
SapModel.PropMaterial.SetMaterial('CONC', 2)                  # 2 = Concrete
SapModel.PropMaterial.SetMPIsotropic('CONC', 3600, 0.2, 5.5e-6)
SapModel.PropFrame.SetRectangle('R1', 'CONC', 1.0, 1.0)       # [L] in present units
nm=' '; [nm,ret] = SapModel.FrameObj.AddByCoord(0,0,0, 0,0,10, nm, 'R1')
p1=' ';p2=' '; [p1,p2,ret] = SapModel.FrameObj.GetPoints(nm, p1, p2)
SapModel.PointObj.SetRestraint(p1, [True,True,True,True,True,True])  # fixed base
SapModel.LoadPatterns.Add('LIVE', 3, 0, True)                 # type 3 = Live
SapModel.View.RefreshView(0, False)
SapModel.File.Save(r'C:\work\model.edb')                      # must save before run
SapModel.Analyze.RunAnalysis()
SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
SapModel.Results.Setup.SetCaseSelectedForOutput('LIVE')
# ... Results.JointDispl / FrameForce / BaseReact / StoryDrifts ...
```

Gotchas:
- `ApplicationStart()` before touching `SapModel`; `InitializeNewModel()` resets it.
- You must `File.Save(path)` before `RunAnalysis()` (analysis writes alongside the `.edb`).
- After analysis the model is **locked**. To edit again call
  `SapModel.SetModelIsLocked(False)` (this deletes results).
- `RefreshView` to make the GUI reflect programmatic changes.
- Select output cases/combos via `Results.Setup` before reading any results, or
  you get empty/zero arrays.

## Finding the exact method/signature you need

The full decompiled API reference is bundled — use it instead of guessing:

- **Which interface has a method?** grep the flat index:
  `reference/method-index.txt` (lines: `Interface.Method<TAB>summary`).
- **All methods of one interface, with C# signatures + summaries:**
  `reference/api/<InterfaceName>.md` (e.g. `reference/api/cFrameObj.md`,
  `reference/api/cAnalysisResults.md`, `reference/api/cDesignSteel.md`).
- **Interface overview / categories / `SapModel` accessor:**
  `reference/interfaces.md`.
- **Enums and their integer values:** `reference/enums.md`.

Signatures in the reference are C#. Translate to the Python COM call by moving
every `ref`/`out` param (and the `int` return) into the returned list, last
element = status, as shown above.

## Building apeETABS (the wrapper in this repo)

When extending the wrapper, mirror these reference groupings (objects, props,
loads, analysis, results, design) into cohesive Python modules/classes; wrap the
`[outputs..., ret]` convention behind functions that raise on `ret != 0` and
return clean Python values; expose enums as Python `IntEnum`s seeded from
`reference/enums.md`. Match the surrounding apeETABS code style.
