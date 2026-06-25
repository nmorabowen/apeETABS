"""Diaphragm enumeration — joints grouped by their assigned named diaphragm.

Membership comes from two sources, unioned by diaphragm name:

* **Joint-level** — ``cPointObj.GetDiaphragm`` returns a joint's
  :class:`eDiaphragmOption` and diaphragm name. Joints participate both when
  explicitly assigned (``DefinedDiaphragm``) and when inheriting from a shell
  (``FromShellObject``); only ``Disconnect`` is skipped.
* **Area-level** — ``cAreaObj.GetDiaphragm`` returns the diaphragm assigned to
  a slab/area; *its boundary joints* join that diaphragm. This is the common
  case for a rigid floor (verified live: a real model assigns the diaphragm on
  the slabs, not per joint), and joint-level capture alone misses it.

Each named group becomes a rigid-diaphragm constraint downstream.
"""

from __future__ import annotations

from ..enums import eDiaphragmOption
from ..errors import ok


def read_diaphragms(sap, point_names, areas) -> list[dict]:
    """Named diaphragms as ``[{name, nodes}]`` (joint + area-level membership)."""
    groups: dict[str, dict[str, None]] = {}  # name -> ordered-unique node set

    def add(dia: str, node: str) -> None:
        groups.setdefault(str(dia), {}).setdefault(str(node), None)

    for name in point_names:
        # GetDiaphragm out order: DiaphragmOption, DiaphragmName.
        option, dia_name = ok(
            sap.PointObj.GetDiaphragm(str(name), 0, ""), "GetDiaphragm"
        )
        if int(option) != eDiaphragmOption.Disconnect and dia_name:
            add(dia_name, name)

    for area in areas:
        # AreaObj.GetDiaphragm out: DiaphragmName (empty = none).
        dia_name = ok(sap.AreaObj.GetDiaphragm(area["id"], ""), "AreaObj.GetDiaphragm")
        if dia_name:
            for node in area["nodes"]:
                add(dia_name, node)

    return [{"name": dia, "nodes": list(nodes)} for dia, nodes in groups.items()]
