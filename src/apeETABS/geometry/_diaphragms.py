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

ETABS reuses one diaphragm *name* (e.g. ``D1``) across every story, so grouping
by name alone merges all floors into a single non-planar constraint. Each named
group is therefore split by elevation — one planar rigid diaphragm per floor
(``D1@<z>`` when a name spans more than one level).
"""

from __future__ import annotations

from ..enums import eDiaphragmOption
from ..errors import ok

# Joints within this vertical tolerance are treated as one floor.
_ELEV_TOL = 3  # decimal places (present length units)


def read_diaphragms(sap, points, areas) -> list[dict]:
    """Named diaphragms as ``[{name, nodes}]``, one planar group per floor."""
    z_of = {p["id"]: p["z"] for p in points}
    groups: dict[str, dict[str, None]] = {}  # name -> ordered-unique node set

    def add(dia: str, node: str) -> None:
        groups.setdefault(str(dia), {}).setdefault(str(node), None)

    for p in points:
        name = p["id"]
        # GetDiaphragm out order: DiaphragmOption, DiaphragmName.
        option, dia_name = ok(
            sap.PointObj.GetDiaphragm(name, 0, ""), "GetDiaphragm"
        )
        if int(option) != eDiaphragmOption.Disconnect and dia_name:
            add(dia_name, name)

    for area in areas:
        # AreaObj.GetDiaphragm out: DiaphragmName (empty = none).
        dia_name = ok(sap.AreaObj.GetDiaphragm(area["id"], ""), "AreaObj.GetDiaphragm")
        if dia_name:
            for node in area["nodes"]:
                add(dia_name, node)

    diaphragms: list[dict] = []
    for name, nodes in groups.items():
        by_elev: dict[float, list[str]] = {}
        for nid in nodes:
            by_elev.setdefault(round(z_of.get(nid, 0.0), _ELEV_TOL), []).append(nid)
        if len(by_elev) == 1:
            diaphragms.append({"name": name, "nodes": list(nodes)})
        else:
            for z in sorted(by_elev):
                diaphragms.append({"name": f"{name}@{z:g}", "nodes": by_elev[z]})
    return diaphragms
