"""Point (joint) enumeration — coordinates in present units.

Object-API backend (``cPointObj``), bulk where ETABS offers it. ``points()``
returns one record per joint; coordinates come from the single bulk
``GetAllPoints`` call (``GetCoordCartesian`` is the per-point fallback). IDs are
the ETABS point names, carried verbatim (ADR 0009 traceability key).
"""

from __future__ import annotations

from ..errors import ok


def read_points(sap) -> list[dict]:
    """All joints as ``[{id, x, y, z}]`` in the model's present length units."""
    # GetAllPoints out order: NumberNames, MyName, X, Y, Z.
    _n, names, xs, ys, zs = ok(
        sap.PointObj.GetAllPoints(0, [], [], [], [], "Global"),
        "GetAllPoints",
    )
    return [
        {"id": str(name), "x": float(x), "y": float(y), "z": float(z)}
        for name, x, y, z in zip(names, xs, ys, zs)
    ]
