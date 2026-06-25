"""Diaphragm enumeration — joints grouped by their assigned named diaphragm.

``cPointObj.GetDiaphragm`` returns, per joint, a :class:`eDiaphragmOption` and
the diaphragm name. Joints explicitly assigned to a *defined* diaphragm are
grouped by name; each group becomes a rigid-diaphragm constraint downstream.
Joints that are disconnected or take their diaphragm from a shell object are
not grouped here.
"""

from __future__ import annotations

from ..enums import eDiaphragmOption
from ..errors import ok


def read_diaphragms(sap, point_names) -> list[dict]:
    """Defined diaphragms as ``[{name, nodes}]`` (nodes ordered by joint name)."""
    groups: dict[str, list[str]] = {}
    for name in point_names:
        name = str(name)
        # GetDiaphragm out order: DiaphragmOption, DiaphragmName.
        option, dia_name = ok(
            sap.PointObj.GetDiaphragm(name, 0, ""), "GetDiaphragm"
        )
        if int(option) == eDiaphragmOption.DefinedDiaphragm and dia_name:
            groups.setdefault(str(dia_name), []).append(name)
    return [{"name": dia, "nodes": nodes} for dia, nodes in groups.items()]
