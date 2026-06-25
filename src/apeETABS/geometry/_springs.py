"""Spring-support enumeration — per-joint uncoupled support stiffness.

``cPointObj.GetSpring`` returns the six diagonal terms of a joint's 6x6 spring
matrix [Kux,Kuy,Kuz,Krx,Kry,Krz] in the point local system — the soil/elastic
support case that ``GetRestraint`` (rigid only) does not capture. Only joints
with at least one nonzero stiffness are emitted.

Coupled springs (off-diagonal terms via ``GetSpringCoupled``) are out of scope
for v1; the uncoupled diagonal is the common support idealization.
"""

from __future__ import annotations

from ..errors import ETABSError, ok


def read_springs(sap, point_names) -> list[dict]:
    """Sprung joints as ``[{node, k}]`` with 6 diagonal stiffnesses.

    ``GetSpring`` (uncoupled) errors on joints whose spring is coupled or
    assigned via a named property; those are skipped (coupled/named springs
    are out of v1 scope) rather than aborting the enumeration.
    """
    springs: list[dict] = []
    for name in point_names:
        name = str(name)
        try:
            # GetSpring out: K (6 diagonal stiffnesses).
            k = ok(sap.PointObj.GetSpring(name, []), "GetSpring")
        except ETABSError:
            continue
        values = [float(v) for v in k]
        if any(values):
            springs.append({"node": name, "k": values})
    return springs
