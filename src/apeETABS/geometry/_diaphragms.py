"""Diaphragm enumeration — joints grouped by their assigned named diaphragm.

``cPointObj.GetDiaphragm`` returns, per joint, a :class:`eDiaphragmOption` and
the diaphragm name. A joint participates in a diaphragm both when it is
*explicitly* assigned one (``DefinedDiaphragm``) and when it inherits one from
the shell object it connects to (``FromShellObject``) — the common case for
slab joints under a rigid floor. Both are grouped by name; only
``Disconnect`` joints are skipped. Each group becomes a rigid-diaphragm
constraint downstream.
"""

from __future__ import annotations

from ..enums import eDiaphragmOption
from ..errors import ok


def read_diaphragms(sap, point_names) -> list[dict]:
    """Named diaphragms as ``[{name, nodes}]`` (nodes ordered by joint name)."""
    groups: dict[str, list[str]] = {}
    for name in point_names:
        name = str(name)
        # GetDiaphragm out order: DiaphragmOption, DiaphragmName.
        option, dia_name = ok(
            sap.PointObj.GetDiaphragm(name, 0, ""), "GetDiaphragm"
        )
        if int(option) != eDiaphragmOption.Disconnect and dia_name:
            groups.setdefault(str(dia_name), []).append(name)
    return [{"name": dia, "nodes": nodes} for dia, nodes in groups.items()]
