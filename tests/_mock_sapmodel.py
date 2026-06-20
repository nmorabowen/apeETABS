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
  ``FieldsKeysIncluded``. An empty ``rows`` list yields a zero-record table.
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

    def __init__(self, tables: dict[str, tuple[list[str], list[list]]]) -> None:
        self._tables = tables

    # GetTableForDisplayArray(key, FieldKeyList, group, TableVersion,
    #   FieldsKeysIncluded, NumberRecords, TableData)
    # -> [FieldKeyList, TableVersion, FieldsKeysIncluded, NumberRecords,
    #     TableData, ret]
    def GetTableForDisplayArray(self, key, _field_keys, _group, _ver, _fki, _nrec, _data):
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
    """Fake ``cSapModel.FrameObj`` recording ChangeName/Delete calls."""

    def __init__(self) -> None:
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, int]] = []

    # ChangeName(Name, NewName) -> ret
    def ChangeName(self, name, new_name):
        self.renamed.append((name, new_name))
        return 0

    # Delete(Name, ItemType) -> ret
    def Delete(self, name, item_type=0):
        self.deleted.append((name, int(item_type)))
        return 0


class _AreaObj(_FrameObj):
    """Fake ``cSapModel.AreaObj`` (same ChangeName/Delete contract)."""


class _PointObj:
    """Fake ``cSapModel.PointObj`` recording ChangeName/Delete/SetRestraint."""

    def __init__(self) -> None:
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, int]] = []
        self.restraints: list[tuple[str, list[bool], int]] = []

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


class _File:
    """Fake ``cSapModel.File``."""

    def __init__(self) -> None:
        self.opened: str | None = None

    def OpenFile(self, path):
        self.opened = path
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
    ) -> None:
        self._tables = tables or {}
        if isinstance(stories, dict):
            stories = StoriesSpec(**stories)
        self._units = list(units)
        self._locked = bool(locked)

        self.DatabaseTables = _DatabaseTables(self._tables)
        self.Story = _Story(stories) if stories is not None else None
        self.File = _File()

        # Editing collaborators (ADR 0005): record ChangeName/Delete/SetRestraint.
        self.FrameObj = _FrameObj()
        self.AreaObj = _AreaObj()
        self.PointObj = _PointObj()

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
