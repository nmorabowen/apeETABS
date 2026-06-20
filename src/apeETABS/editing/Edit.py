"""``Edit`` composite — geometry/topology edits on an existing model.

The ``e.edit`` surface (ADR 0005 §5): identity and topology mutations that
wrap ``c*Obj.ChangeName`` / ``c*Obj.Delete`` and (later) ``cEditFrame`` /
``cEditGeneral``. Objects are referenced by their ETABS **unique name**
(ADR 0005 §3); operations that change identity return the new state.

Every mutating method first calls ``self._parent._require_unlocked(...)``:
ETABS locks the model after analysis and we never unlock implicitly (ADR
0005 §2). The user must call ``e.unlock()`` — which discards results — by
hand. Each COM return is routed through ``ok()`` (ADR 0005 §6, fail-loud,
no auto-rollback).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import ok

if TYPE_CHECKING:
    from .._session import _SessionBase

# Object kinds -> the SapModel collaborator exposing ChangeName/Delete.
_KIND_ATTR = {
    "frame": "FrameObj",
    "point": "PointObj",
    "area": "AreaObj",
}


class Edit:
    """Geometry/topology edits (rename, delete, …) on existing objects."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _obj(self, kind: str):
        """Return the SapModel ``*Obj`` collaborator for an object ``kind``."""
        try:
            attr = _KIND_ATTR[kind]
        except KeyError:
            raise ValueError(
                f"Unknown object kind {kind!r}; expected one of "
                f"{sorted(_KIND_ATTR)}."
            ) from None
        return getattr(self._parent.SapModel, attr)

    # ------------------------------------------------------------------
    # Implemented edits
    # ------------------------------------------------------------------

    def rename(self, old: str, new: str, *, kind: str = "frame") -> str:
        """Rename an object's unique name via ``c*Obj.ChangeName``.

        Args:
            old: The object's current unique name.
            new: The desired new unique name.
            kind: ``"frame"`` (default), ``"point"`` or ``"area"``.

        Returns:
            The new name (ADR 0005 §3: identity-changing ops return new state).
        """
        self._parent._require_unlocked(f"rename {kind} {old!r}")
        ok(self._obj(kind).ChangeName(old, new), f"ChangeName {kind} {old!r}")
        return new

    def delete(self, target: str, *, kind: str = "frame") -> None:
        """Delete an object via ``c*Obj.Delete``, invalidating its name.

        Args:
            target: The unique name of the object to delete.
            kind: ``"frame"`` (default), ``"point"`` or ``"area"``.
        """
        self._parent._require_unlocked(f"delete {kind} {target!r}")
        # eItemType defaults to Objects (0) — a single named object.
        ok(self._obj(kind).Delete(target, 0), f"Delete {kind} {target!r}")

    # ------------------------------------------------------------------
    # Stubs — documented, not yet implemented (ADR 0005 §5).
    # ------------------------------------------------------------------

    def move(self, *args, **kwargs):
        """Translate object(s) by a vector (wraps ``cEditGeneral.Move``).

        Not implemented yet — P6 ships rename/delete only; the geometric
        edits (``cEditFrame`` / ``cEditGeneral``) land in a later slice.
        """
        raise NotImplementedError(
            "Edit.move is not implemented yet (P6 ships rename/delete only)."
        )

    def divide(self, *args, **kwargs):
        """Split a frame/area into pieces, returning the new names.

        Not implemented yet — wraps ``cEditFrame.DivideAtIntersections`` /
        ``DivideAtDistance``; returns the produced names (ADR 0005 §3).
        """
        raise NotImplementedError(
            "Edit.divide is not implemented yet (P6 ships rename/delete only)."
        )

    def replicate(self, *args, **kwargs):
        """Copy object(s) (linear/radial/mirror), returning the new names.

        Not implemented yet — wraps ``cEditGeneral.ReplicateLinear`` etc.;
        returns the produced names (ADR 0005 §3).
        """
        raise NotImplementedError(
            "Edit.replicate is not implemented yet (P6 ships rename/delete only)."
        )
