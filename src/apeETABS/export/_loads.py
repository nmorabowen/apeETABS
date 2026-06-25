"""Load-pattern assembly — nodal / frame-distributed / area-uniform loads.

Object-API backend: each ``GetLoad*`` getter, called per object, returns that
object's load items across *all* patterns. We iterate the objects, bucket the
items by load-pattern name, and build the schema's per-pattern load lists.

Only the load types the schema models are emitted: joint forces/moments,
uniform frame distributed *forces* (moment-per-length is skipped), and uniform
area pressures. ETABS direction codes are mapped to the schema's
``1|2|3 | X|Y|Z|gravity`` vocabulary.
"""

from __future__ import annotations

from ..errors import ok
from .StructuralModel import AreaLoad, FrameLoad, LoadPattern, NodalLoad

# ETABS load direction codes -> schema direction. 1-3 are local axes (kept as
# ints); 4-6 are global X/Y/Z; 10/11 are gravity / projected gravity.
_DIRECTION = {4: "X", 5: "Y", 6: "Z", 10: "gravity", 11: "gravity"}

# GetLoadDistributed MyType: 1 = force/length, 2 = moment/length.
_FORCE_PER_LENGTH = 1


def read_loads(sap, point_names, frame_names, area_names) -> list[LoadPattern]:
    """Assemble load patterns (only patterns that carry at least one load)."""
    nodal: dict[str, list[NodalLoad]] = {}
    frame: dict[str, list[FrameLoad]] = {}
    area: dict[str, list[AreaLoad]] = {}

    for name in point_names:
        _read_point_force(sap, str(name), nodal)
    for name in frame_names:
        _read_frame_distributed(sap, str(name), frame)
    for name in area_names:
        _read_area_uniform(sap, str(name), area)

    pattern_names: dict[str, None] = {}
    for bucket in (nodal, frame, area):
        for pat in bucket:
            pattern_names[pat] = None

    return [
        LoadPattern(
            name=pat,
            nodal=tuple(nodal.get(pat, ())),
            frame=tuple(frame.get(pat, ())),
            area=tuple(area.get(pat, ())),
        )
        for pat in pattern_names
    ]


def _read_point_force(sap, name: str, out: dict[str, list[NodalLoad]]) -> None:
    # GetLoadForce out: NumberItems, PointName, LoadPat, LcStep, CSys,
    # F1, F2, F3, M1, M2, M3.
    n, _pn, pats, _lc, _cs, f1, f2, f3, m1, m2, m3 = ok(
        sap.PointObj.GetLoadForce(name, 0, [], [], [], [], [], [], [], [], [], []),
        "GetLoadForce",
    )
    for k in range(int(n)):
        out.setdefault(str(pats[k]), []).append(
            NodalLoad(
                node=name,
                force_xyz=(float(f1[k]), float(f2[k]), float(f3[k])),
                moment_xyz=(float(m1[k]), float(m2[k]), float(m3[k])),
            )
        )


def _read_frame_distributed(sap, name: str, out: dict[str, list[FrameLoad]]) -> None:
    # GetLoadDistributed out: NumberItems, FrameName, LoadPat, MyType, CSys,
    # Dir, RD1, RD2, Dist1, Dist2, Val1, Val2.
    n, _fn, pats, mytype, _cs, dirs, _rd1, _rd2, _d1, _d2, v1, _v2 = ok(
        sap.FrameObj.GetLoadDistributed(
            name, 0, [], [], [], [], [], [], [], [], [], []
        ),
        "GetLoadDistributed",
    )
    for k in range(int(n)):
        if int(mytype[k]) != _FORCE_PER_LENGTH:
            continue  # moment-per-length: not modeled by the schema
        out.setdefault(str(pats[k]), []).append(
            FrameLoad(
                frame=name,
                direction=_direction(int(dirs[k])),
                value=float(v1[k]),
            )
        )


def _read_area_uniform(sap, name: str, out: dict[str, list[AreaLoad]]) -> None:
    # GetLoadUniform out: NumberItems, AreaName, LoadPat, CSys, Dir, Value.
    # (GetLoadUniformToFrame is NOT a usable getter — it returns ret=-100 on
    # real models; the OAPI reference marks it "NOT APPLICABLE". Load-set /
    # shell-distributed gravity has no working object-API getter — see the
    # Phase-4 loads limitation note.)
    n, _an, pats, _cs, dirs, vals = ok(
        sap.AreaObj.GetLoadUniform(name, 0, [], [], [], []),
        "GetLoadUniform",
    )
    for k in range(int(n)):
        out.setdefault(str(pats[k]), []).append(
            AreaLoad(
                area=name,
                direction=_direction(int(dirs[k])),
                value=float(vals[k]),
            )
        )


def _direction(code: int):
    """Map an ETABS direction code to a schema-valid direction."""
    if code in (1, 2, 3):
        return code  # local axis
    return _DIRECTION.get(code, "gravity")
