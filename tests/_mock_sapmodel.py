"""In-memory fake ``cSapModel`` (+ ``cOAPI`` app) for testing without ETABS.

The ETABS OAPI marshals ``ref``/``out`` parameters into Python as a list
``[out1, out2, ..., ret]`` — outputs first, integer status last. Every method
here reproduces that exact convention for the calls apeETABS makes, so the real
``Units`` / ``Tables`` / ``Stories`` composites run unmodified against the mock.

Public construction contract
----------------------------
``MockSapModel(tables=..., stories=..., units=..., locked=...)`` where:

* ``tables``  : ``{table_key: (headers: list[str], rows: list[list])}``.
  Rows are flattened row-major into ``TableData``; ``headers`` becomes
  ``FieldsKeysIncluded``. An empty ``rows`` list yields a zero-record table
  (headers still returned).
* ``empty_tables`` : optional set of table keys that simulate a *truly* empty
  real-ETABS table — the call succeeds (``ret 0``) but returns an empty
  ``FieldsKeysIncluded`` and no data, exercising ``Tables.get``'s "no headers"
  branch (which returns a bare ``DataFrame``).
* ``stories`` : a :class:`StoriesSpec` (or the kwargs to build one) describing
  the ``Story.GetStories_2`` payload. ``base_elevation``/``base_name`` feed the
  fallback path; per-story ``names``/``elevations``/``heights``/``is_master``
  are returned top-story-first to match ETABS.
* ``units``   : ``(force_code, length_code, temp_code)`` integers (defaults
  ``(4, 6, 2)`` = kN, m, C). Mutated by ``SetPresentUnits_2``.
* ``locked``  : initial model-locked flag (``GetModelIsLocked`` /
  ``SetModelIsLocked``). The ``FrameObj`` / ``AreaObj`` / ``PointObj``
  collaborators record ``ChangeName`` / ``Delete`` / ``SetRestraint`` calls
  for the editing layer (ADR 0005).

Use :class:`MockETABS` as the application object exposing ``.SapModel`` plus the
lifecycle stubs (``ApplicationStart`` / ``ApplicationExit`` / ``Visible`` /
``Hide``) the session touches.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StoriesSpec:
    """Fixture spec for ``Story.GetStories_2`` (stories are top-first)."""

    names: list[str]
    elevations: list[float]
    heights: list[float]
    base_name: str = "Base"
    base_elevation: float = 0.0
    is_master: list[bool] = field(default_factory=list)
    similar_to: list[str] = field(default_factory=list)
    splice_above: list[bool] = field(default_factory=list)
    splice_height: list[float] = field(default_factory=list)
    color: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        n = len(self.names)
        if not self.is_master:
            self.is_master = [False] * n
        if not self.similar_to:
            self.similar_to = [""] * n
        if not self.splice_above:
            self.splice_above = [False] * n
        if not self.splice_height:
            self.splice_height = [0.0] * n
        if not self.color:
            self.color = [0] * n


class _DatabaseTables:
    """Fake ``cSapModel.DatabaseTables``."""

    def __init__(
        self,
        tables: dict[str, tuple[list[str], list[list]]],
        empty_tables: set[str] | None = None,
    ) -> None:
        self._tables = tables
        # Table keys that simulate a truly empty real-ETABS table: the call
        # succeeds (ret 0) but returns no FieldsKeysIncluded and no data, so
        # the "no headers" branch in Tables.get is exercised.
        self._empty = empty_tables or set()

    # GetTableForDisplayArray(key, FieldKeyList, group, TableVersion,
    #   FieldsKeysIncluded, NumberRecords, TableData)
    # -> [FieldKeyList, TableVersion, FieldsKeysIncluded, NumberRecords,
    #     TableData, ret]
    def GetTableForDisplayArray(self, key, _field_keys, _group, _ver, _fki, _nrec, _data):
        if key in self._empty:
            return [[], 1, [], 0, [], 0]  # success, but empty FieldsKeysIncluded
        if key not in self._tables:
            return [[], 1, [], 0, [], 1]  # nonzero ret: unknown table
        headers, rows = self._tables[key]
        flat: list = []
        for row in rows:
            flat.extend(str(c) for c in row)
        return [list(headers), 1, list(headers), len(rows), flat, 0]

    # GetAvailableTables(NumberTables, TableKey, TableName, ImportType)
    # -> [NumberTables, TableKey, TableName, ImportType, ret]
    def GetAvailableTables(self, _n, _keys, _names, _import):
        keys = list(self._tables.keys())
        names = list(keys)  # human label == key in the mock
        return [len(keys), keys, names, [1] * len(keys), 0]


class _Story:
    """Fake ``cSapModel.Story``."""

    def __init__(self, spec: StoriesSpec) -> None:
        self._spec = spec

    # GetStories_2(BaseElevation, NumberStories, StoryNames, StoryElevations,
    #   StoryHeights, IsMasterStory, SimilarToStory, SpliceAbove, SpliceHeight,
    #   color)
    # -> [BaseElevation, NumberStories, StoryNames, StoryElevations,
    #     StoryHeights, IsMasterStory, SimilarToStory, SpliceAbove,
    #     SpliceHeight, color, ret]
    def GetStories_2(self, *_args):
        s = self._spec
        return [
            float(s.base_elevation),
            len(s.names),
            list(s.names),
            [float(e) for e in s.elevations],
            [float(h) for h in s.heights],
            list(s.is_master),
            list(s.similar_to),
            list(s.splice_above),
            [float(h) for h in s.splice_height],
            list(s.color),
            0,
        ]


class _FrameObj:
    """Fake ``cSapModel.FrameObj`` recording ChangeName/Delete/Add calls."""

    def __init__(self) -> None:
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, int]] = []
        # Creation (ADR 0006): record AddByCoord and serve GetPoints.
        self.added: list[dict] = []
        self._auto = 0
        # frame name -> (i_point_name, j_point_name) served by GetPoints.
        self._points: dict[str, tuple[str, str]] = {}
        # Loadings (ADR 0008 assign primitive): record distributed loads.
        self.dist_loads: list[dict] = []

    # ChangeName(Name, NewName) -> ret
    def ChangeName(self, name, new_name):
        self.renamed.append((name, new_name))
        return 0

    # Delete(Name, ItemType) -> ret
    def Delete(self, name, item_type=0):
        self.deleted.append((name, int(item_type)))
        return 0

    # AddByCoord(XI,YI,ZI, XJ,YJ,ZJ, ref Name, PropName, UserName, CSys)
    #   -> [Name, ret]
    def AddByCoord(self, xi, yi, zi, xj, yj, zj, _name, prop="Default",
                   user="", csys="Global"):
        self._auto += 1
        name = user or f"F{self._auto}"
        self.added.append(
            {"i": (xi, yi, zi), "j": (xj, yj, zj), "prop": prop, "name": name}
        )
        # ETABS reorders I/J; the mock simulates that by naming end points
        # deterministically from the frame name (the production code must read
        # these back from GetPoints rather than assume the input order).
        self._points[name] = (f"~{name}-I", f"~{name}-J")
        return [name, 0]

    # GetPoints(Name, ref Point1, ref Point2) -> [Point1, Point2, ret]
    def GetPoints(self, name, _p1, _p2):
        pi, pj = self._points.get(name, ("", ""))
        return [pi, pj, 0]

    # SetLoadDistributed(Name, LoadPat, MyType, Dir, Dist1, Dist2, Val1, Val2,
    #   CSys, RelDist, Replace, ItemType) -> ret
    def SetLoadDistributed(self, name, pat, my_type, direction, d1, d2, v1, v2,
                           csys="Global", rel=True, replace=True, item_type=0):
        self.dist_loads.append({
            "name": name, "pat": pat, "type": int(my_type), "dir": int(direction),
            "d1": float(d1), "d2": float(d2), "v1": float(v1), "v2": float(v2),
            "csys": csys, "rel": bool(rel), "replace": bool(replace),
            "item_type": int(item_type),
        })
        return 0


class _AreaObj(_FrameObj):
    """Fake ``cSapModel.AreaObj`` recording SetLoadUniform (+ FrameObj contract)."""

    def __init__(self) -> None:
        super().__init__()
        self.uniform_loads: list[dict] = []

    # SetLoadUniform(Name, LoadPat, Value, Dir, Replace, CSys, ItemType) -> ret
    def SetLoadUniform(self, name, pat, value, direction, replace=True,
                       csys="Global", item_type=0):
        self.uniform_loads.append({
            "name": name, "pat": pat, "value": float(value), "dir": int(direction),
            "replace": bool(replace), "csys": csys, "item_type": int(item_type),
        })
        return 0


class _PointObj:
    """Fake ``cSapModel.PointObj`` recording ChangeName/Delete/SetRestraint/Add."""

    def __init__(self) -> None:
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, int]] = []
        self.restraints: list[tuple[str, list[bool], int]] = []
        # Creation (ADR 0006): record AddCartesian calls.
        self.added: list[dict] = []
        self._auto = 0
        # Loadings (ADR 0008 assign primitive): record point forces.
        self.forces: list[dict] = []

    # ChangeName(Name, NewName) -> ret
    def ChangeName(self, name, new_name):
        self.renamed.append((name, new_name))
        return 0

    # Delete(Name, ItemType) -> ret
    def Delete(self, name, item_type=0):
        self.deleted.append((name, int(item_type)))
        return 0

    # SetRestraint(Name, Value, ItemType) -> ret
    def SetRestraint(self, name, value, item_type=0):
        self.restraints.append((name, [bool(v) for v in value], int(item_type)))
        return 0

    # SetLoadForce(Name, LoadPat, Value, Replace, CSys, ItemType) -> ret
    def SetLoadForce(self, name, pat, value, replace=False, csys="Global",
                     item_type=0):
        self.forces.append({
            "name": name, "pat": pat, "value": [float(v) for v in value],
            "replace": bool(replace), "csys": csys, "item_type": int(item_type),
        })
        return 0

    # AddCartesian(X, Y, Z, ref Name, UserName, CSys, ...) -> [Name, ret]
    def AddCartesian(self, x, y, z, _name, user="", csys="Global", *_rest):
        self._auto += 1
        name = user or f"P{self._auto}"
        self.added.append({"xyz": (x, y, z), "name": name})
        return [name, 0]


class _PropMaterial:
    """Fake ``cSapModel.PropMaterial`` recording SetMaterial/SetMPIsotropic."""

    def __init__(self) -> None:
        self.materials: list[tuple[str, int]] = []
        self.isotropic: list[tuple[str, float, float, float]] = []
        # Catalog adds (ADR 0006): record AddMaterial calls.
        self.catalog: list[dict] = []
        # Mass source (ADR 0008 define primitive): record SetMassSource_1.
        self.mass_source: dict | None = None

    # SetMaterial(Name, MatType, Color, Notes, GUID) -> ret
    def SetMaterial(self, name, mat_type, *_rest):
        self.materials.append((name, int(mat_type)))
        return 0

    # AddMaterial(ref Name, MatType, Region, Standard, Grade, UserName)
    #   -> [Name, ret]
    def AddMaterial(self, _name, mat_type, region, standard, grade, user=""):
        # ETABS assigns the name; the mock returns the UserName when given,
        # else falls back to the grade (or "Mat1"). The production code must
        # read this back rather than assume the input Name.
        name = user or grade or "Mat1"
        self.catalog.append(
            {
                "type": int(mat_type),
                "region": region,
                "standard": standard,
                "grade": grade,
                "user": user,
                "name": name,
            }
        )
        return [name, 0]

    # SetMPIsotropic(Name, E, U, A, Temp) -> ret
    def SetMPIsotropic(self, name, E, U, A, temp=0.0):
        self.isotropic.append((name, float(E), float(U), float(A)))
        return 0

    # SetMassSource_1(IncludeElements, IncludeAddedMass, IncludeLoads,
    #   NumberLoads, LoadPat, sf) -> ret
    def SetMassSource_1(self, elements, added, loads, n, load_pat, sf):
        self.mass_source = {
            "elements": bool(elements),
            "added": bool(added),
            "loads": bool(loads),
            "n": int(n),
            "pats": list(load_pat),
            "sf": [float(s) for s in sf],
        }
        return 0


class _FuncRS:
    """Fake ``cSapModel.Func.FuncRS`` recording SetUser."""

    def __init__(self) -> None:
        self.user: list[dict] = []

    # SetUser(Name, NumberItems, Period, Value, DampRatio) -> ret
    def SetUser(self, name, n, period, value, damp):
        self.user.append({
            "name": name, "n": int(n),
            "period": [float(p) for p in period],
            "value": [float(v) for v in value],
            "damp": float(damp),
        })
        return 0


class _Func:
    """Fake ``cSapModel.Func`` exposing the FuncRS sub-interface."""

    def __init__(self) -> None:
        self.FuncRS = _FuncRS()


class _CaseModalEigen:
    """Fake ``cSapModel.LoadCases.ModalEigen`` recording SetCase/SetNumberModes."""

    def __init__(self) -> None:
        self.cases: list[str] = []
        self.modes: dict[str, tuple[int, int]] = {}

    def SetCase(self, name):
        self.cases.append(name)
        return 0

    def SetNumberModes(self, name, max_modes, min_modes):
        self.modes[name] = (int(max_modes), int(min_modes))
        return 0


class _CaseResponseSpectrum:
    """Fake ``cSapModel.LoadCases.ResponseSpectrum`` recording SetCase/Loads/Modal."""

    def __init__(self) -> None:
        self.cases: list[str] = []
        self.loads: dict[str, dict] = {}
        self.modal: dict[str, str] = {}

    def SetCase(self, name):
        self.cases.append(name)
        return 0

    # SetLoads(Name, NumberLoads, LoadName, Func, SF, CSys, Ang) -> ret
    def SetLoads(self, name, n, load_name, func, sf, csys, ang):
        self.loads[name] = {
            "n": int(n), "dirs": list(load_name), "funcs": list(func),
            "sf": [float(s) for s in sf], "csys": list(csys),
            "ang": [float(a) for a in ang],
        }
        return 0

    def SetModalCase(self, name, modal_case):
        self.modal[name] = modal_case
        return 0


class _LoadCases:
    """Fake ``cSapModel.LoadCases`` exposing ModalEigen + ResponseSpectrum."""

    def __init__(self) -> None:
        self.ModalEigen = _CaseModalEigen()
        self.ResponseSpectrum = _CaseResponseSpectrum()


class _RespCombo:
    """Fake ``cSapModel.RespCombo`` recording Add + SetCaseList_1."""

    def __init__(self) -> None:
        self.added: list[tuple[str, int]] = []
        # name -> list of (cname_type, cname, mode, sf)
        self.case_lists: dict[str, list[tuple[int, str, int, float]]] = {}

    # Add(Name, ComboType) -> ret
    def Add(self, name, combo_type):
        self.added.append((name, int(combo_type)))
        self.case_lists.setdefault(name, [])
        return 0

    # SetCaseList_1(Name, CNameType, CName, ModeNumber, SF) -> ret
    def SetCaseList_1(self, name, cname_type, cname, mode, sf):
        self.case_lists.setdefault(name, []).append(
            (int(cname_type), str(cname), int(mode), float(sf))
        )
        return 0


class _PropFrame:
    """Fake ``cSapModel.PropFrame`` recording SetRectangle."""

    def __init__(self) -> None:
        self.rectangles: list[tuple[str, str, float, float]] = []

    # SetRectangle(Name, MatProp, T3, T2, Color, Notes, GUID) -> ret
    def SetRectangle(self, name, mat, t3, t2, *_rest):
        self.rectangles.append((name, mat, float(t3), float(t2)))
        return 0


class _LoadPatterns:
    """Fake ``cSapModel.LoadPatterns`` recording Add."""

    def __init__(self) -> None:
        self.added: list[tuple[str, int, float, bool]] = []

    # Add(Name, MyType, SelfWTMultiplier, AddAnalysisCase) -> ret
    def Add(self, name, my_type, self_wt=0.0, add_case=True):
        self.added.append((name, int(my_type), float(self_wt), bool(add_case)))
        return 0


class _File:
    """Fake ``cSapModel.File`` recording OpenFile + the template New* calls."""

    def __init__(self) -> None:
        self.opened: str | None = None
        self.new_calls: list[tuple[str, tuple]] = []

    def OpenFile(self, path):
        self.opened = path
        return 0

    # NewBlank() -> ret
    def NewBlank(self):
        self.new_calls.append(("blank", ()))
        return 0

    # NewGridOnly(NumberStorys, TypicalStoryHeight, BottomStoryHeight,
    #   NumberLinesX, NumberLinesY, SpacingX, SpacingY) -> ret
    def NewGridOnly(self, *args):
        self.new_calls.append(("grid_only", tuple(args)))
        return 0

    # NewSteelDeck(...) same signature as NewGridOnly -> ret
    def NewSteelDeck(self, *args):
        self.new_calls.append(("steel_deck", tuple(args)))
        return 0


class MockSapModel:
    """In-memory ``cSapModel`` reproducing the ``[outputs..., ret]`` contract."""

    def __init__(
        self,
        *,
        tables: dict[str, tuple[list[str], list[list]]] | None = None,
        stories: StoriesSpec | dict | None = None,
        units: tuple[int, int, int] = (4, 6, 2),  # kN, m, C
        locked: bool = False,
        empty_tables: set[str] | None = None,
    ) -> None:
        self._tables = tables or {}
        if isinstance(stories, dict):
            stories = StoriesSpec(**stories)
        self._units = list(units)
        self._locked = bool(locked)

        self.DatabaseTables = _DatabaseTables(self._tables, empty_tables)
        self.Story = _Story(stories) if stories is not None else None
        self.File = _File()

        # Editing collaborators (ADR 0005): record ChangeName/Delete/SetRestraint.
        # They also serve the creation Add* calls (ADR 0006).
        self.FrameObj = _FrameObj()
        self.AreaObj = _AreaObj()
        self.PointObj = _PointObj()

        # Creation collaborators (ADR 0006): record the define/* calls.
        self.PropMaterial = _PropMaterial()
        self.PropFrame = _PropFrame()
        self.LoadPatterns = _LoadPatterns()
        self.RespCombo = _RespCombo()
        self.Func = _Func()
        self.LoadCases = _LoadCases()

    # ---- units --------------------------------------------------------
    # GetPresentUnits_2(force, length, temp) -> [force, length, temp, ret]
    def GetPresentUnits_2(self, _f, _l, _t):
        f, ln, t = self._units
        return [f, ln, t, 0]

    # SetPresentUnits_2(force, length, temp) -> ret
    def SetPresentUnits_2(self, force, length, temp):
        self._units = [int(force), int(length), int(temp)]
        return 0

    # ---- lock ---------------------------------------------------------
    # GetModelIsLocked() -> [locked, ret]
    def GetModelIsLocked(self):
        return [self._locked, 0]

    # SetModelIsLocked(locked) -> ret
    def SetModelIsLocked(self, locked):
        self._locked = bool(locked)
        return 0


class MockETABS:
    """In-memory ``cOAPI`` application exposing ``.SapModel`` + lifecycle stubs."""

    def __init__(self, sap_model: MockSapModel | None = None) -> None:
        self.SapModel = sap_model or MockSapModel()
        self.started = False
        self.exited = False
        self.saved_on_exit: bool | None = None
        self.visible = True

    def ApplicationStart(self, *_args):
        self.started = True
        return 0

    def ApplicationExit(self, save):
        self.exited = True
        self.saved_on_exit = bool(save)
        return 0

    def Visible(self):
        self.visible = True
        return 0

    def Hide(self):
        self.visible = False
        return 0
