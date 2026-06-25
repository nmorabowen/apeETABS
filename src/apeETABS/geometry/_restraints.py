"""Restraint enumeration — per-joint support conditions.

``cPointObj.GetRestraint`` returns a 6-bool mask (Ux,Uy,Uz,Rx,Ry,Rz) per
joint in the point local system. Only joints with at least one restrained DOF
are emitted, keeping the document lean.
"""

from __future__ import annotations

from ..errors import ok


def read_restraints(sap, point_names) -> list[dict]:
    """Restrained joints as ``[{node, dofs}]`` with 6-int 0/1 masks."""
    restraints: list[dict] = []
    for name in point_names:
        name = str(name)
        # GetRestraint out: Value (6 bools).
        value = ok(sap.PointObj.GetRestraint(name, []), "GetRestraint")
        dofs = [int(bool(v)) for v in value]
        if any(dofs):
            restraints.append({"node": name, "dofs": dofs})
    return restraints
