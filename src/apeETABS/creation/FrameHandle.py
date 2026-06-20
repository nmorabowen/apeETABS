"""``FrameHandle`` — a thin value handle for a just-created frame object.

ADR 0006 §4: ``create.*`` returns the program-assigned name; frame creation
additionally returns the names of the frame's two end points. ETABS **reorders
I/J on creation** (see ``cFrameObj.AddByCoord`` remarks), so the only reliable
way to know which point is the I end and which is the J end is to re-query
``cFrameObj.GetPoints`` after the add — :class:`Create` does exactly that and
packs the result here.

The handle is a *thin value object*, not a live proxy (ADR 0006 §4 / ADR 0005):
it carries the resolved names at creation time. Renaming or deleting the frame
or its points (ADR 0005) invalidates the handle — re-query if in doubt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameHandle:
    """Names of a created frame object and its (reordered) I/J end points.

    Attributes:
        name: The frame object's ETABS unique name.
        i: The unique name of the point at the frame's I end.
        j: The unique name of the point at the frame's J end.
    """

    name: str
    i: str
    j: str
