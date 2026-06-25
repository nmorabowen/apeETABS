"""Area (shell) enumeration — boundary joints, section, local axis, opening.

Object-API backend (``cAreaObj``): ``GetNameList`` enumerates the objects;
per area ``GetPoints`` gives the ordered boundary joints, ``GetProperty`` the
section name, ``GetLocalAxes`` the local-1 angle, and ``GetOpening`` flags
opening objects (holes, handled downstream — carried through as ``is_opening``).
"""

from __future__ import annotations

from ..errors import ok


def read_areas(sap) -> list[dict]:
    """All areas as ``[{id, nodes, section, local_axis_deg, is_opening}]``."""
    # GetNameList out order: NumberNames, MyName.
    _n, names = ok(sap.AreaObj.GetNameList(0, []), "AreaObj.GetNameList")

    areas: list[dict] = []
    for name in names:
        name = str(name)
        # GetPoints out order: NumberPoints, Point.
        _np, pts = ok(sap.AreaObj.GetPoints(name, 0, []), "AreaObj.GetPoints")
        section = ok(sap.AreaObj.GetProperty(name, ""), "AreaObj.GetProperty")
        # GetLocalAxes out order: Ang, Advanced.
        ang, _adv = ok(sap.AreaObj.GetLocalAxes(name, 0.0, False), "AreaObj.GetLocalAxes")
        is_opening = bool(ok(sap.AreaObj.GetOpening(name, False), "AreaObj.GetOpening"))
        areas.append(
            {
                "id": name,
                "nodes": [str(p) for p in pts],
                "section": str(section),
                "local_axis_deg": float(ang),
                "is_opening": is_opening,
            }
        )
    return areas
