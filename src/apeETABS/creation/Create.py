"""``Create`` composite — geometry creation (points, frames).

The ``e.create`` surface (ADR 0006 §2): the *draw* half of creation — add
points (``cPointObj.AddCartesian``) and frame objects (``cFrameObj.AddByCoord``).
Areas/links/tendons are stubbed for a later slice.

Coordinates are **present-units-as-contract** (ADR 0006 §3): ``x/y/z`` and the
``i_xyz``/``j_xyz`` tuples are interpreted in the model's present length units;
author them with ``baseUnits`` for explicit intent.

Identity (ADR 0006 §4): ``point`` returns the program-assigned (or requested)
name. ETABS **reorders the I/J ends** when it adds a frame (see
``cFrameObj.AddByCoord`` remarks), so ``frame_by_coord`` re-queries
``cFrameObj.GetPoints`` after the add and returns a :class:`FrameHandle`
carrying the *resolved* I and J point names — not the order they were passed.

Every mutating method first calls ``self._parent._require_unlocked(...)`` (ADR
0005 §2) and routes each COM return through ``ok()`` (fail-loud, no rollback).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from ..errors import ok
from .FrameHandle import FrameHandle

if TYPE_CHECKING:
    from .._session import _SessionBase

# Coordinate triple (x, y, z) in present length units.
_XYZ = Sequence[float]


class Create:
    """Geometry creation (points, frames) returning ETABS names / handles."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Points
    # ------------------------------------------------------------------

    def point(
        self,
        x: float,
        y: float,
        z: float,
        *,
        name: str | None = None,
    ) -> str:
        """Add a point object via ``cPointObj.AddCartesian``.

        Args:
            x, y, z: Coordinates in the present length units (ADR 0006 §3).
            name: A requested name (``UserName``); if omitted ETABS assigns one
                and the assigned name is returned (ADR 0006 §4).

        Returns:
            The point's unique name (program-assigned unless ``name`` was given).
        """
        self._parent._require_unlocked("create point")
        # AddCartesian(X, Y, Z, ref Name, UserName, CSys, ...) -> [Name, ret].
        # The ref Name is both seed and output; pass "" and read it back. ok()
        # strips the trailing status and returns the lone Name output.
        assigned = ok(
            self._parent.SapModel.PointObj.AddCartesian(
                float(x), float(y), float(z), "", name or ""
            ),
            "AddCartesian",
        )
        if self._parent._verbose:
            print(f"Created point {assigned!r} at ({x}, {y}, {z}).")
        return assigned

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------

    def frame_by_coord(
        self,
        i_xyz: _XYZ,
        j_xyz: _XYZ,
        *,
        section: str = "Default",
        name: str | None = None,
    ) -> FrameHandle:
        """Add a frame object from end coordinates via ``cFrameObj.AddByCoord``.

        ETABS may swap the I/J ends on creation (``AddByCoord`` remarks), so
        after the add we call ``GetPoints`` to learn the *resolved* end-point
        names and return them in a :class:`FrameHandle` (ADR 0006 §4).

        Args:
            i_xyz: The I-end coordinates ``(x, y, z)`` (present length units).
            j_xyz: The J-end coordinates ``(x, y, z)`` (present length units).
            section: An existing frame section property name (``PropName``,
                default ``"Default"``).
            name: A requested name (``UserName``); ETABS assigns one when
                omitted.

        Returns:
            A :class:`FrameHandle` with the frame name and the resolved I/J
            point names.
        """
        xi, yi, zi = (float(c) for c in i_xyz)
        xj, yj, zj = (float(c) for c in j_xyz)
        self._parent._require_unlocked("create frame")
        # AddByCoord(XI,YI,ZI, XJ,YJ,ZJ, ref Name, PropName, UserName, CSys)
        #   -> [Name, ret]. ref Name is seed + output; pass "" and read back.
        #   ok() strips the status and returns the lone Name output.
        frame_name = ok(
            self._parent.SapModel.FrameObj.AddByCoord(
                xi, yi, zi, xj, yj, zj, "", section, name or ""
            ),
            "AddByCoord",
        )
        # ETABS reorders I/J — resolve the true end-point names via GetPoints.
        # GetPoints(Name, ref Point1, ref Point2) -> [Point1, Point2, ret];
        #   ok() returns the two outputs as a list.
        pi, pj = ok(
            self._parent.SapModel.FrameObj.GetPoints(frame_name, "", ""),
            f"GetPoints {frame_name!r}",
        )
        if self._parent._verbose:
            print(f"Created frame {frame_name!r} (i={pi!r}, j={pj!r}).")
        return FrameHandle(name=frame_name, i=pi, j=pj)

    # ------------------------------------------------------------------
    # Stubs — documented, not yet implemented (ADR 0006 §2).
    # ------------------------------------------------------------------

    def area(self, *args, **kwargs):
        """Add an area object (wraps ``cAreaObj.AddByCoord`` / ``AddByPoint``).

        Not implemented yet — P7 ships ``point`` and ``frame_by_coord`` only;
        areas/links/tendons land in a later slice.
        """
        raise NotImplementedError(
            "Create.area is not implemented yet (P7 ships point + frame_by_coord)."
        )
