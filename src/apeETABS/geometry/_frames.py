"""Frame (line member) enumeration — connectivity, section, releases, kind.

``GetAllFrames`` returns names, section (``PropName``), end joints
(``PointName1/2``), end coordinates, and the local-axis angle in one bulk
call — it subsumes the per-object ``GetPoints``/``GetSection``/``GetLocalAxes``
getters. ``GetReleases`` has no bulk form, so it is queried per frame. ``kind``
(beam/column/brace) is derived from the end coordinates the same call returns.
"""

from __future__ import annotations

import math

from ..errors import ok


def read_frames(sap) -> list[dict]:
    """All frames as ``[{id, i, j, section, rotation, kind, releases_*}]``."""
    # GetAllFrames out order: NumberNames, MyName, PropName, StoryName,
    # PointName1, PointName2, Point1X/Y/Z, Point2X/Y/Z, Angle, then 6 offsets +
    # CardinalPoint (unused here).
    (_n, names, props, _stories, p1, p2,
     x1, y1, z1, x2, y2, z2, angle, *_rest) = ok(
        sap.FrameObj.GetAllFrames(
            0, [], [], [], [], [], [], [], [], [], [], [], [],
            [], [], [], [], [], [], [], "Global",
        ),
        "GetAllFrames",
    )

    frames: list[dict] = []
    for k, name in enumerate(names):
        name = str(name)
        rec = {
            "id": name,
            "i": str(p1[k]),
            "j": str(p2[k]),
            "section": str(props[k]),
            "rotation": float(angle[k]),
            "kind": _classify(x1[k], y1[k], z1[k], x2[k], y2[k], z2[k]),
        }
        rel_i, rel_j = _read_releases(sap, name)
        if any(rel_i):
            rec["releases_i"] = rel_i
        if any(rel_j):
            rec["releases_j"] = rel_j
        frames.append(rec)
    return frames


def _read_releases(sap, name: str) -> tuple[list[int], list[int]]:
    """End-release masks ``(II, JJ)`` as 6-int 0/1 lists (Ux..Rz)."""
    # GetReleases out order: II, JJ, StartValue, EndValue.
    ii, jj, _sv, _ev = ok(
        sap.FrameObj.GetReleases(name, [], [], [], []), "GetReleases"
    )
    return [int(bool(v)) for v in ii], [int(bool(v)) for v in jj]


def _classify(x1, y1, z1, x2, y2, z2) -> str:
    """Beam (horizontal), column (vertical), or brace (inclined)."""
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length == 0.0:
        return "beam"
    vertical = abs(dz) / length
    if vertical > 0.999:
        return "column"
    if vertical < 0.001:
        return "beam"
    return "brace"
